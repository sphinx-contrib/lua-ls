"""
Autodoc directives for lua.

"""

from __future__ import annotations

import contextlib
import functools
import math
import re
import textwrap
from typing import Any, Callable, ClassVar, Type

import docutils.nodes
import docutils.statemachine
import sphinx.addnodes
import sphinx.util.docutils
import sphinx.util.nodes
from docutils.parsers.rst import directives
from sphinx.util.docutils import SphinxDirective

import sphinx_luals.domain
from sphinx_luals.doctree import Kind, Object, Visibility


class AutodocUtilsMixin(SphinxDirective):
    """
    Provides facilities for rendering automatically generated documentation.

    """

    # Override type of `option_spec` to make it compatible with `ObjectDescription`.
    option_spec: ClassVar[dict[str, Callable[[str], Any]]]  # type: ignore

    def push_context(self, modname: str, classname: str):
        classes = self.env.ref_context.setdefault("lua:classes", [])
        classes.append(self.env.ref_context.get("lua:class"))
        self.env.ref_context["lua:class"] = classname

        modules = self.env.ref_context.setdefault("lua:modules", [])
        modules.append(self.env.ref_context.get("lua:module"))
        self.env.ref_context["lua:module"] = modname

    def pop_context(self):
        classes = self.env.ref_context.setdefault("lua:classes", [])
        if classes:
            self.env.ref_context["lua:class"] = classes.pop()
        else:
            self.env.ref_context.pop("lua:class")

        modules = self.env.ref_context.setdefault("lua:modules", [])
        if modules:
            self.env.ref_context["lua:module"] = modules.pop()
        else:
            self.env.ref_context.pop("lua:module")

    @contextlib.contextmanager
    def save_context(self):
        modname = self.env.ref_context.get("lua:module")
        classname = self.env.ref_context.get("lua:classname")
        try:
            yield
        finally:
            self.env.ref_context["lua:module"] = modname
            self.env.ref_context["lua:classname"] = classname

    def render(self, root: Object, name: str, pass_through: bool = False):
        if not self.env.ref_context.get("lua:class") and root.kind == Kind.Module:
            # This is a module.
            return self.render_module(root, name, pass_through)
        elif root.kind == Kind.Module:
            # This is a module inside of a class. We will render it as a class.
            return self.render_class(root, name, pass_through)
        elif root.kind == Kind.Data:
            return self.render_data(root, name, pass_through)
        elif root.kind == Kind.Function:
            return self.render_function(root, name, pass_through)
        elif root.kind == Kind.Class:
            return self.render_class(root, name, pass_through)
        elif root.kind == Kind.Alias:
            return self.render_alias(root, name, pass_through)
        else:
            raise RuntimeError(f"unknown lua object kind {root.kind}")

    def render_module(self, root: Object, name: str, pass_through: bool = False):
        with self.save_context():
            nodes = list(
                self._create_directive(
                    name, sphinx_luals.domain.LuaModule, "lua:module", pass_through
                ).run()
            )

            container = docutils.nodes.container()
            nodes.append(container)

            if root.docstring:
                self.render_docs(
                    str(root.file or f"<docstring for {self.arguments[0]}>"),
                    root.line or 0,
                    root.docstring,
                    container,
                )

            for name, child in self.get_children(root):
                nodes.extend(self.render(child, name))

            return nodes

    def render_data(self, root: Object, name: str, pass_through: bool = False):
        with self.save_context():
            return self._create_directive(
                name,
                LuaData,
                "lua:data",
                pass_through,
                root=root,
            ).run()

    def render_function(self, root: Object, name: str, pass_through: bool = False):
        with self.save_context():
            return self._create_directive(
                name,
                LuaFunction,
                "lua:function",
                pass_through,
                root=root,
            ).run()

    def render_class(self, root: Object, name: str, pass_through: bool = False):
        with self.save_context():
            return self._create_directive(
                name,
                LuaClass,
                "lua:class",
                pass_through,
                root=root,
            ).run()

    def render_alias(self, root: Object, name: str, pass_through: bool = False):
        with self.save_context():
            return self._create_directive(
                name,
                LuaAlias,
                "lua:alias",
                pass_through,
                root=root,
            ).run()

    def render_docs(self, path: str, line: int, docs: str, node, titles=False):
        docs = re.sub(r"^\@\*\w+\*.*$", "", docs, flags=re.MULTILINE)
        docs = re.sub(r"^```lua\n.*?\n```", "", docs, flags=re.MULTILINE | re.DOTALL)
        see_sections = list(re.finditer(r"^See:\n", docs, flags=re.MULTILINE))
        if see_sections:
            match = see_sections[-1]
            see_section = docs[match.span()[1] :]
            docs = docs[: match.span()[0]]
        else:
            see_section = ""

        see_lines = []
        rejected_see_lines = []
        for see_line in see_section.splitlines():
            if match := re.match(
                r"""
                ^[ ][ ]\*[ ]
                (?:
                    ~(?P<rejected_type>.+?)~ (?P<rejected_doc>.*)
                    |
                    \[(?P<type>.+?)\]\(.*?\) (?P<doc>.*)
                )
                $
                """,
                see_line,
                flags=re.VERBOSE,
            ):
                typ = match.group("type") or match.group("rejected_type")
                doc = match.group("doc") or match.group("rejected_doc") or ""
                if doc:
                    doc = ": " + doc
                see_lines.append(f":lua:obj:`{typ}`{doc}")
            else:
                rejected_see_lines.append(see_line)

        if rejected_see_lines:
            docs += "\n\nSee:\n" + "\n".join(rejected_see_lines)

        docs = textwrap.dedent(docs)

        if len(see_lines) > 1:
            see_lines = ["", "See:", ""] + [
                nl for l in see_lines for nl in (f"- {l}", "")
            ]
        else:
            see_lines = [""] + [f"See: {l}" for l in see_lines]

        lines = docs.splitlines() + see_lines

        items = [(path, line)] * len(lines)

        content = docutils.statemachine.StringList(lines, items=items)

        with sphinx.util.docutils.switch_source_input(self.state, content):
            if titles:
                sphinx.util.nodes.nested_parse_with_titles(self.state, content, node)
            else:
                self.state.nested_parse(content, 0, node)

    def _create_directive(
        self,
        name: str,
        cls: Type[SphinxDirective],
        directive_name: str,
        pass_through: bool = False,
        **kwargs,
    ) -> SphinxDirective:
        if pass_through:
            options = self.options.copy()
            options.pop("module", None)
        else:
            recursive = self.options.get("recursive", False)
            members_map = lambda x: x if recursive and x is True else None
            options = {
                "members": members_map(self.options.get("members")),
                "undoc-members": members_map(self.options.get("undoc-members")),
                "private-members": members_map(self.options.get("private-members")),
                "special-members": members_map(self.options.get("special-members")),
                "inherited-members": members_map(self.options.get("inherited-members")),
                "member-order": self.options.get("member-order", None),
                "recursive": recursive,
            }
            if "no-index" in self.options:
                # NB: `no-index` should not be present in `options` if it wasn't present
                # in `self.options`.
                options["no-index"] = self.options["no-index"]

        return cls(
            directive_name,
            [name],
            options,
            self.content if pass_through else docutils.statemachine.StringList(),
            self.lineno if pass_through else 0,
            self.content_offset if pass_through else 0,
            self.block_text if pass_through else "",
            self.state,
            self.state_machine,
            **kwargs,
        )

    @property
    def objtree(self) -> Object:
        return getattr(self.env, "luals_doc_root")

    @functools.cached_property
    def parent(self):
        modname = self.env.ref_context.get("lua:module", None)
        classname = self.env.ref_context.get("lua:class", None)
        if classname:
            basepath = ".".join(filter(None, [modname, classname]))
            return self.objtree.find(basepath)

    _GROUPS = {
        Kind.Module: 0,
        Kind.Data: 1,
        Kind.Function: 2,
        Kind.Class: 3,
        Kind.Alias: 4,
    }

    def get_children(self, root: Object):
        children = list(root.children.items())

        order = self.options.get("member-order") or "bysource"
        if order == "alphabetical":
            children.sort(key=lambda ch: ch[0].lower())
        elif order == "groupwise":
            children.sort(key=lambda ch: (self._GROUPS[ch[1].kind], ch[0].lower()))
        elif order == "bysource":
            children.sort(
                key=lambda ch: (
                    str(ch[1].file or "@"),
                    ch[1].line or math.inf,
                    ch[0].lower(),
                )
            )
        else:
            raise RuntimeError(f"unknown member order {order}")

        inherited_names = set()

        parent = self.parent
        if (
            parent
            and parent.kind == Kind.Class
            and isinstance(parent, sphinx_luals.doctree.Class)
        ):
            for basename in parent.bases:
                base = self.objtree.find(basename)
                if base:
                    inherited_names.update(base.children.keys())

        include_normal = False
        include_undoc = False
        include_private = False
        include_special = False
        include_inherited = False

        include = set()
        exclude = self.options.get("exclude-members", set())

        if exclude is True:
            exclude = set()

        if members := self.options.get("members"):
            if members is True:
                include_normal = True
            else:
                include.update(members)
        if undoc := self.options.get("undoc-members"):
            if undoc is True:
                include_undoc = True
            else:
                include.update(undoc)
        if private := self.options.get("private-members"):
            if private is True:
                include_private = True
            else:
                include.update(private)
        if special := self.options.get("special-members"):
            if special is True:
                include_special = True
            else:
                include.update(special)
        if inherited := self.options.get("inherited-members"):
            if inherited is True:
                include_inherited = True
            else:
                include.update(inherited)

        for name, child in children:
            if name in exclude:
                continue
            if name not in include:
                is_undoc = not child.docstring
                if is_undoc and not include_undoc:
                    continue
                is_private = child.visibility != Visibility.Public
                if is_private and not include_private:
                    continue
                is_special = name.startswith("__")
                if is_special and not include_special:
                    continue
                is_inherited = name in inherited_names
                if is_inherited and not include_inherited:
                    continue
                if (
                    not is_undoc
                    and not is_private
                    and not is_special
                    and not is_inherited
                    and not include_normal
                ):
                    continue
            yield name, child


class AutodocObjectMixin(sphinx_luals.domain.LuaObject[Any], AutodocUtilsMixin):
    def __init__(self, *args, root: Object):
        super().__init__(*args)
        self.root = root

        if self.root.visibility == Visibility.Private:
            self.options["private"] = True
        elif self.root.visibility == Visibility.Protected:
            self.options["protected"] = True
        elif self.root.visibility == Visibility.Package:
            self.options["package"] = True
        if self.root.is_async:
            self.options["async"] = True
        if self.root.is_deprecated:
            self.options["deprecated"] = True

    def run(self) -> list[docutils.nodes.Node]:
        if self.root.file:
            self.state.document.settings.record_dependencies.add(str(self.root.file))
        return super().run()

    def transform_content(self, content_node: sphinx.addnodes.desc_content) -> None:
        if self.root.docstring:
            self.render_docs(
                str(self.root.file or f"<docstring for {self.arguments[0]}>"),
                self.root.line or 0,
                self.root.docstring,
                content_node,
            )
        if self.allow_nesting:
            for name, child in self.get_children(self.root):
                content_node += self.render(child, name)


class LuaFunction(sphinx_luals.domain.LuaFunction, AutodocObjectMixin):
    @functools.cached_property
    def is_method(self):
        assert isinstance(self.root, sphinx_luals.doctree.Function)

        return self.parent and self.parent.kind == Kind.Class

    @functools.cached_property
    def is_staticmethod(self):
        assert isinstance(self.root, sphinx_luals.doctree.Function)

        return (
            self.parent
            and self.parent.kind == Kind.Class
            and (not self.root.params or self.root.params[0].name != "self")
        )

    @property
    def objtype(self):
        if self.is_staticmethod:
            return "staticmethod"
        elif self.is_method:
            return "method"
        else:
            return "function"

    @objtype.setter
    def objtype(self, value):  # type: ignore
        assert value == "function"

    def parse_signature(self, sig):
        assert isinstance(self.root, sphinx_luals.doctree.Function)
        return (
            self.arguments[0],
            (
                [(p.name or "", p.type or "") for p in self.root.params],
                [(p.name or "", p.type or "") for p in self.root.returns],
            ),
        )

    def transform_content(self, content_node: sphinx.addnodes.desc_content) -> None:
        assert isinstance(self.root, sphinx_luals.doctree.Function)

        if self.root.docstring:
            self.render_docs(
                str(self.root.file or f"<docstring for {self.arguments[0]}>"),
                self.root.line or 0,
                self.root.docstring,
                content_node,
            )

        for child in content_node:
            if isinstance(child, docutils.nodes.field_list):
                field_list = child
                break
        else:
            field_list = docutils.nodes.field_list()
            content_node += field_list

        for i, param in enumerate(self.root.params):
            if param.docstring and not (i == 0 and param.name == "self"):
                # if param.type:
                #     objtree: Object = getattr(self.env, "luals_doc_root")
                #     obj = objtree.find(param.type)
                #     if obj and obj.docstring == param.docstring:
                #         continue

                field_body = docutils.nodes.field_body("")
                self.render_docs(
                    str(
                        self.root.file
                        or f"<docstring for {self.arguments[0]}, param {param.name}>"
                    ),
                    self.root.line or 0,
                    param.docstring,
                    field_body,
                )
                field_list += docutils.nodes.field(
                    "",
                    docutils.nodes.field_name("", "param " + (param.name or "_")),
                    field_body,
                )
            if param.type:
                field_list += docutils.nodes.field(
                    "",
                    docutils.nodes.field_name(
                        "", "type " + (param.name or f"_{i + 1}")
                    ),
                    docutils.nodes.field_body("", docutils.nodes.Text(param.type)),
                )

        for i, param in enumerate(self.root.returns):
            if param.docstring:
                # if param.type:
                #     objtree: Object = getattr(self.env, "luals_doc_root")
                #     obj = objtree.find(param.type)
                #     if obj and obj.docstring == param.docstring:
                #         continue

                field_body = docutils.nodes.field_body("")
                self.render_docs(
                    str(
                        self.root.file
                        or f"<docstring for {self.arguments[0]}, param {param.name}>"
                    ),
                    self.root.line or 0,
                    param.docstring,
                    field_body,
                )
                field_list += docutils.nodes.field(
                    "",
                    docutils.nodes.field_name(
                        "", "return " + (param.name or f"_{i + 1}")
                    ),
                    field_body,
                )
            if param.type:
                field_list += docutils.nodes.field(
                    "",
                    docutils.nodes.field_name(
                        "", "rtype " + (param.name or f"_{i + 1}")
                    ),
                    docutils.nodes.field_body("", docutils.nodes.Text(param.type)),
                )

        if self.allow_nesting:
            for name, child in self.get_children(self.root):
                content_node += self.render(child, name)


class LuaData(sphinx_luals.domain.LuaData, AutodocObjectMixin):
    def parse_signature(self, sig):
        assert isinstance(self.root, sphinx_luals.doctree.Data)
        return self.arguments[0], self.root.type


class LuaAlias(sphinx_luals.domain.LuaAlias, AutodocObjectMixin):
    def parse_signature(self, sig):
        assert isinstance(self.root, sphinx_luals.doctree.Alias)
        return self.arguments[0], self.root.type


class LuaClass(sphinx_luals.domain.LuaClass, AutodocObjectMixin):
    def parse_signature(self, sig):
        if self.root.kind == Kind.Class:
            bases = (
                self.root.bases
                if isinstance(self.root, sphinx_luals.doctree.Class)
                else []
            )
            return self.arguments[0], bases
        else:
            return self.arguments[0], []

    def get_signature_prefix(self, signature: str):
        if self.root.kind == Kind.Class:
            return super().get_signature_prefix(signature)
        else:
            return sphinx_luals.domain.LuaObject.get_signature_prefix(self, signature)


def _parse_members(value: str):
    if not value:
        return True
    elif "," in value:
        return {s for m in value.split(",") if (s := m.strip())}
    else:
        return set(value.split())


class AutoObjectDirective(AutodocUtilsMixin):
    required_arguments = 1
    option_spec = {
        "no-index": directives.flag,
        "annotation": directives.unchanged,
        "virtual": directives.flag,
        "private": directives.flag,
        "protected": directives.flag,
        "package": directives.flag,
        "abstract": directives.flag,
        "async": directives.flag,
        "global": directives.flag,
        "deprecated": directives.flag,
        "members": _parse_members,
        "undoc-members": _parse_members,
        "private-members": _parse_members,
        "special-members": _parse_members,
        "inherited-members": _parse_members,
        "exclude-members": _parse_members,
        "recursive": lambda x: directives.flag(x) or True,
        "member-order": lambda x: directives.choice(
            x, ("alphabetical", "groupwise", "bysource")
        ),
    }

    has_content = True

    def run(self):
        for name, option in self.env.config["luals_default_options"].items():
            if name not in self.options:
                self.options[name] = option

        name = self.arguments[0].strip()

        if not name:
            raise self.error(f"got an empty object name")

        found = self.get_root(name, getattr(self.env, "luals_doc_root"))
        if not found:
            raise self.error(f"unknown lua object {name}")

        root, modname, classname, objname = found

        self.push_context(modname, classname)
        try:
            return self.render(root, objname, pass_through=True)
        finally:
            self.pop_context()

    def get_root(self, name: str, root: Object) -> tuple[Object, str, str, str] | None:
        modname = self.options.get("module", self.env.ref_context.get("lua:module"))
        classname = self.env.ref_context.get("lua:class", None)

        candidates = [
            ".".join(filter(None, [modname, classname, name])),
            ".".join(filter(None, [modname, name])),
            ".".join(filter(None, [name])),
        ]

        for candidate in candidates:
            if found := root.find_path(candidate):
                return found
