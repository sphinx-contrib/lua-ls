"""
Autodoc directives for lua.

"""

from __future__ import annotations

import contextlib
import functools
import math
from typing import Any, Callable, ClassVar, Type

import docutils.nodes
import docutils.statemachine
import sphinx.addnodes
import sphinx.util.docutils
import sphinx.util.nodes
from docutils.parsers.rst import directives
from sphinx.util.docutils import SphinxDirective

import sphinx_lua_ls.domain
from sphinx_lua_ls.doctree import Kind, Object, Visibility


def _parse_members(value: str):
    if not value:
        return True
    elif "," in value:
        return {s for m in value.split(",") if (s := m.strip())}
    else:
        return set(value.split())


class AutodocUtilsMixin(SphinxDirective):
    """
    Provides facilities for rendering automatically generated documentation.

    """

    option_spec: ClassVar[dict[str, Callable[[str], Any]]] = {  # type: ignore
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
        "protected-members": _parse_members,
        "package-members": _parse_members,
        "special-members": _parse_members,
        "inherited-members": _parse_members,
        "exclude-members": _parse_members,
        "recursive": lambda x: directives.flag(x) or True,
        "member-order": lambda x: directives.choice(
            x, ("alphabetical", "groupwise", "bysource")
        ),
    }

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
        if root.parsed_doctype:
            objtype = root.parsed_doctype
            if objtype not in ["module"]:
                raise ValueError(f"incorrect doctype {objtype} for a module")
        else:
            objtype = "module"

        modname = self.env.ref_context.get("lua:module")
        classname = self.env.ref_context.get("lua:classname")
        fullname = ".".join(filter(None, [modname, classname, name]))

        with self.save_context():
            nodes = list(
                self._create_directive(
                    fullname,
                    sphinx_lua_ls.domain.LuaModule,
                    "lua:" + objtype,
                    pass_through,
                ).run()
            )

            container = docutils.nodes.container()
            nodes.append(container)

            if root.parsed_docstring:
                self.render_docs(
                    str(root.file or f"<docstring for {self.arguments[0]}>"),
                    root.line or 0,
                    root.parsed_docstring,
                    container,
                    titles=True,
                )

            for name, child in self.get_children(root):
                nodes.extend(self.render(child, name))

            return nodes

    def render_data(self, root: Object, name: str, pass_through: bool = False):
        if root.parsed_doctype:
            objtype = root.parsed_doctype
            if objtype not in ["data", "const", "attribute"]:
                raise ValueError(f"incorrect doctype {objtype} for a data")
        else:
            objtype = "data"

        with self.save_context():
            return self._create_directive(
                name,
                LuaData,
                "lua:" + objtype,
                pass_through,
                root=root,
            ).run()

    def render_function(self, root: Object, name: str, pass_through: bool = False):
        assert isinstance(root, sphinx_lua_ls.doctree.Function)
        if root.parsed_doctype:
            objtype = root.parsed_doctype
            if objtype not in ["function", "method", "staticmethod", "classmethod"]:
                raise ValueError(f"incorrect doctype {objtype} for a function")
        elif self.parent and self.parent.kind == Kind.Class:
            if not root.params or root.params[0].name != "self":
                objtype = "staticmethod"
            else:
                objtype = "method"
        else:
            objtype = "function"

        with self.save_context():
            return self._create_directive(
                name,
                LuaFunction,
                "lua:" + objtype,
                pass_through,
                root=root,
            ).run()

    def render_class(self, root: Object, name: str, pass_through: bool = False):
        if root.parsed_doctype:
            objtype = root.parsed_doctype
            if objtype not in ["class"]:
                raise ValueError(f"incorrect doctype {objtype} for a class")
        else:
            objtype = "class"

        with self.save_context():
            return self._create_directive(
                name,
                LuaClass,
                "lua:" + objtype,
                pass_through,
                root=root,
            ).run()

    def render_alias(self, root: Object, name: str, pass_through: bool = False):
        if root.parsed_doctype:
            objtype = root.parsed_doctype
            if objtype not in ["alias"]:
                raise ValueError(f"incorrect doctype {objtype} for a alias")
        else:
            objtype = "alias"

        with self.save_context():
            return self._create_directive(
                name,
                LuaAlias,
                "lua:" + objtype,
                pass_through,
                root=root,
            ).run()

    def render_docs(self, path: str, line: int, docs: str, node, titles=False):
        pass

        lines = docs.splitlines()

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
            options = {}
            for key in [
                "member-order",
                "recursive",
                "no-index",
            ]:
                if key in self.options:
                    options[key] = self.options[key]
            for key in [
                "members",
                "undoc-members",
                "private-members",
                "protected-members",
                "package-members",
                "special-members",
                "inherited-members",
            ]:
                if key in self.options and self.options[key] is True:
                    options[key] = self.options[key]

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
        return getattr(self.env, "lua_ls_doc_root")

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
            and isinstance(parent, sphinx_lua_ls.doctree.Class)
        ):
            for basename in parent.bases:
                base = self.objtree.find(basename)
                if base:
                    inherited_names.update(base.children.keys())

        include_normal = False
        include_undoc = False
        include_private = False
        include_protected = False
        include_package = False
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
        if protected := self.options.get("protected-members"):
            if protected is True:
                include_protected = True
            else:
                include.update(protected)
        if package := self.options.get("package-members"):
            if package is True:
                include_package = True
            else:
                include.update(package)
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
                is_undoc = not child.parsed_docstring
                if is_undoc and not include_undoc:
                    continue
                is_private = child.visibility == Visibility.Private
                if is_private and not include_private:
                    continue
                is_protected = child.visibility == Visibility.Protected
                if is_protected and not include_protected:
                    continue
                is_package = child.visibility == Visibility.Package
                if is_package and not include_package:
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
                    and not is_protected
                    and not is_package
                    and not is_special
                    and not is_inherited
                    and not include_normal
                ):
                    continue
            yield name, child


class AutodocObjectMixin(sphinx_lua_ls.domain.LuaObject[Any], AutodocUtilsMixin):
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

        for name, value in self.root.parsed_options.items():
            if name in AutoObjectDirective.option_spec:
                try:
                    self.options[name] = AutoObjectDirective.option_spec[name](value)
                except ValueError as e:
                    raise ValueError(
                        f"invalid !doc option {name} in object {self.arguments[0]}: {e}"
                    ) from None
            else:
                raise ValueError(
                    f"unknown !doc option {name} in object {self.arguments[0]}"
                )

    def run(self) -> list[docutils.nodes.Node]:
        if self.root.file:
            self.state.document.settings.record_dependencies.add(str(self.root.file))
        return super().run()

    def transform_content(self, content_node: sphinx.addnodes.desc_content) -> None:
        if self.root.parsed_docstring:
            self.render_docs(
                str(self.root.file or f"<docstring for {self.arguments[0]}>"),
                self.root.line or 0,
                self.root.parsed_docstring,
                content_node,
                titles=True,
            )
        if self.allow_nesting:
            for name, child in self.get_children(self.root):
                content_node += self.render(child, name)


class LuaFunction(sphinx_lua_ls.domain.LuaFunction, AutodocObjectMixin):
    def parse_signature(self, sig):
        assert isinstance(self.root, sphinx_lua_ls.doctree.Function)
        return (
            self.arguments[0],
            (
                [(p.name or "", p.type or "") for p in self.root.params],
                [(p.name or "", p.type or "") for p in self.root.returns],
            ),
        )

    def transform_content(self, content_node: sphinx.addnodes.desc_content) -> None:
        assert isinstance(self.root, sphinx_lua_ls.doctree.Function)

        if self.root.parsed_docstring:
            self.render_docs(
                str(self.root.file or f"<docstring for {self.arguments[0]}>"),
                self.root.line or 0,
                self.root.parsed_docstring,
                content_node,
                titles=True,
            )

        for child in content_node:
            if isinstance(child, docutils.nodes.field_list):
                field_list = child
                break
        else:
            field_list = docutils.nodes.field_list()
            content_node += field_list

        for i, param in enumerate(self.root.params):
            if param.parsed_docstring and not (i == 0 and param.name == "self"):
                if param.type:
                    obj = self.objtree.find(param.type)
                    if obj and obj.docstring == param.docstring:
                        continue

                field_body = docutils.nodes.field_body("")
                self.render_docs(
                    str(
                        self.root.file
                        or f"<docstring for {self.arguments[0]}, param {param.name}>"
                    ),
                    self.root.line or 0,
                    param.parsed_docstring,
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
            if param.parsed_docstring:
                if param.type:
                    obj = self.objtree.find(param.type)
                    if obj and obj.docstring == param.docstring:
                        continue

                field_body = docutils.nodes.field_body("")
                self.render_docs(
                    str(
                        self.root.file
                        or f"<docstring for {self.arguments[0]}, param {param.name}>"
                    ),
                    self.root.line or 0,
                    param.parsed_docstring,
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


class LuaData(sphinx_lua_ls.domain.LuaData, AutodocObjectMixin):
    def parse_signature(self, sig):
        assert isinstance(self.root, sphinx_lua_ls.doctree.Data)
        return self.arguments[0], self.root.type


class LuaAlias(sphinx_lua_ls.domain.LuaAlias, AutodocObjectMixin):
    def parse_signature(self, sig):
        assert isinstance(self.root, sphinx_lua_ls.doctree.Alias)
        return self.arguments[0], self.root.type


class LuaClass(sphinx_lua_ls.domain.LuaClass, AutodocObjectMixin):
    def parse_signature(self, sig):
        if self.root.kind == Kind.Class:
            bases = (
                self.root.bases
                if isinstance(self.root, sphinx_lua_ls.doctree.Class)
                else []
            )
            return self.arguments[0], bases
        else:
            return self.arguments[0], []

    def get_signature_prefix(self, signature: str):
        if self.root.kind == Kind.Class:
            return super().get_signature_prefix(signature)
        else:
            return sphinx_lua_ls.domain.LuaObject.get_signature_prefix(self, signature)


class AutoObjectDirective(AutodocUtilsMixin):
    required_arguments = 1

    has_content = True

    def run(self):
        for name, option in self.env.config["lua_ls_default_options"].items():
            if name not in self.options:
                self.options[name] = option

        name = self.arguments[0].strip()

        if not name:
            raise self.error(f"got an empty object name")

        found = self.get_root(name, getattr(self.env, "lua_ls_doc_root"))
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
