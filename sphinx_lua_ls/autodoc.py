"""
Autodoc directives for lua.

"""

from __future__ import annotations

import functools
import math
import os
from typing import Any, Callable, ClassVar, Type

import docutils.nodes
import docutils.statemachine
import sphinx.addnodes
import sphinx.util
from docutils.parsers.rst import directives
from sphinx.util.docutils import SphinxDirective
from sphinx.util.parsing import nested_parse_to_nodes

import sphinx_lua_ls.autoindex
import sphinx_lua_ls.domain
import sphinx_lua_ls.objtree
from sphinx_lua_ls.objtree import Kind, Object, Visibility

# Dirty hack =(
# Alias files and types are not properly reported sometimes.
_FIX_FLAKY_ALIAS_TESTS = "_LUA_LS_FIX_FLAKY_ALIAS_TESTS" in os.environ


def _parse_members(value: str):
    if not value:
        return True
    elif "," in value:
        return {s for m in value.split(",") if (s := m.strip())}
    else:
        return set(value.split())


def _iter_children(
    obj: Object, objtree: Object, parent: Object | None, options: dict[str, Any]
):
    children = list(obj.children.items())

    if obj.kind == Kind.Module:
        order = (
            options.get("module-member-order")
            or options.get("member-order")
            or "bysource"
        )
    else:
        order = options.get("member-order") or "bysource"
    if order == "alphabetical":
        children.sort(key=lambda ch: ch[0].lower())
    elif order == "groupwise":
        children.sort(key=lambda ch: ((ch[1].kind or Kind.Data).order, ch[0]))
    elif order == "bysource":
        children.sort(
            key=lambda ch: (
                str(ch[1].docstring_file or "~") if not _FIX_FLAKY_ALIAS_TESTS else "",
                ch[1].line or math.inf,
                ch[0],
            )
        )
    else:
        raise RuntimeError(f"unknown member order {order}")

    inherited_names = set()

    if (
        parent
        and parent.kind == Kind.Class
        and isinstance(parent, sphinx_lua_ls.objtree.Class)
    ):
        for basename in parent.bases:
            base = objtree.find(basename)
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
    exclude = options.get("exclude-members", set())

    if exclude is True:
        exclude = set()

    if members := options.get("members"):
        if members is True:
            include_normal = True
        else:
            include.update(members)
    if undoc := options.get("undoc-members"):
        if undoc is True:
            include_undoc = True
        else:
            include.update(undoc)
    if private := options.get("private-members"):
        if private is True:
            include_private = True
        else:
            include.update(private)
    if protected := options.get("protected-members"):
        if protected is True:
            include_protected = True
        else:
            include.update(protected)
    if package := options.get("package-members"):
        if package is True:
            include_package = True
        else:
            include.update(package)
    if special := options.get("special-members"):
        if special is True:
            include_special = True
        else:
            include.update(special)
    if inherited := options.get("inherited-members"):
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
            is_private = (
                child.visibility == Visibility.Private
                or "private" in child.parsed_options
            )
            if is_private and not include_private:
                continue
            is_protected = (
                child.visibility == Visibility.Protected
                or "protected" in child.parsed_options
            )
            if is_protected and not include_protected:
                continue
            is_package = (
                child.visibility == Visibility.Package
                or "package" in child.parsed_options
            )
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


class AutodocUtilsMixin(sphinx_lua_ls.domain.LuaContextManagerMixin):
    """
    Provides facilities for rendering automatically generated documentation.

    """

    option_spec: ClassVar[dict[str, Callable[[str], Any]]] = {  # type: ignore
        "members": _parse_members,
        "undoc-members": _parse_members,
        "private-members": _parse_members,
        "protected-members": _parse_members,
        "package-members": _parse_members,
        "special-members": _parse_members,
        "inherited-members": _parse_members,
        "exclude-members": _parse_members,
        "title": directives.unchanged,
        "index-title": directives.unchanged,
        "recursive": directives.flag,
        "index-table": directives.flag,
        "member-order": lambda x: directives.choice(
            x, ("alphabetical", "groupwise", "bysource")
        ),
        "module-member-order": lambda x: directives.choice(
            x, ("alphabetical", "groupwise", "bysource")
        ),
        **sphinx_lua_ls.domain.LuaObject.option_spec,
    }

    def render(self, root: Object, name: str, top_level: bool = False):
        if root.kind is None:
            what = root.__class__.__name__.lower()
            modname = self.env.ref_context.get("lua:module")
            classname = self.env.ref_context.get("lua:classname")
            fullname = ".".join(filter(None, [modname, classname, name]))
            raise self.error(
                f"incorrect !doctype for {what} {fullname}: {root.parsed_doctype}"
            )

        with self.save_context():
            if root.kind == Kind.Data:
                return self.render_data(root, name, top_level)
            elif root.kind == Kind.Table:
                return self.render_table(root, name, top_level)
            elif root.kind == Kind.Module:
                return self.render_module(root, name, top_level)
            elif root.kind == Kind.Function:
                return self.render_function(root, name, top_level)
            elif root.kind == Kind.Class:
                return self.render_class(root, name, top_level)
            elif root.kind == Kind.Alias:
                return self.render_alias(root, name, top_level)
            else:
                raise RuntimeError(f"unknown lua object kind {root.kind}")

    def render_module(self, root: Object, name: str, top_level: bool = False):
        if top_level:
            modname = self.env.ref_context.get("lua:module")
            classname = self.env.ref_context.get("lua:classname")
            fullname = ".".join(filter(None, [modname, classname, name]))

            return self._create_directive(
                fullname,
                LuaModule,
                "lua:module",
                root,
                top_level,
            ).run()
        else:
            # Non-toplevel modules are rendered as tables.
            # They still have objtype "module", though.
            return self._create_directive(
                name,
                LuaTable,
                "lua:module",
                root,
                top_level,
            ).run()

    def render_table(self, root: Object, name: str, top_level: bool = False):
        return self._create_directive(
            name,
            LuaTable,
            "lua:" + (root.parsed_doctype or "table"),
            root,
            top_level,
        ).run()

    def render_data(self, root: Object, name: str, top_level: bool = False):
        return self._create_directive(
            name,
            LuaData,
            "lua:" + (root.parsed_doctype or "data"),
            root,
            top_level,
        ).run()

    def render_function(self, root: Object, name: str, top_level: bool = False):
        assert isinstance(root, sphinx_lua_ls.objtree.Function)
        if root.parsed_doctype:
            objtype = root.parsed_doctype
        elif self.parent and self.parent.kind == Kind.Class:
            if not root.params or root.params[0].name != "self":
                objtype = "staticmethod"
            else:
                objtype = "method"
        else:
            objtype = "function"

        return self._create_directive(
            name,
            LuaFunction,
            "lua:" + objtype,
            root,
            top_level,
        ).run()

    def render_class(self, root: Object, name: str, top_level: bool = False):
        return self._create_directive(
            name,
            LuaClass,
            "lua:" + (root.parsed_doctype or "class"),
            root,
            top_level,
        ).run()

    def render_alias(self, root: Object, name: str, top_level: bool = False):
        return self._create_directive(
            name,
            LuaAlias,
            "lua:" + (root.parsed_doctype or "alias"),
            root,
            top_level,
        ).run()

    def render_docs(
        self, path: str, line: int, docs: str, titles=False
    ) -> list[docutils.nodes.Node]:
        lines = docs.splitlines()
        items = [(path, line)] * len(lines)
        content = docutils.statemachine.StringList(lines, items=items, source=path)
        with sphinx.util.docutils.switch_source_input(self.state, content):
            return nested_parse_to_nodes(
                self.state,
                content,
                allow_section_headings=titles,
            )

    def _create_directive(
        self,
        name: str,
        cls: Type[AutodocDirectiveMixin],
        directive_name: str,
        root: Object,
        top_level: bool = False,
    ) -> SphinxDirective:
        if top_level:
            options = self.options.copy()
            options.pop("module", None)
        else:
            options = {}
            for key in [
                "member-order",
                "module-member-order",
                "recursive",
                "no-index",
            ]:
                if key in self.options:
                    options[key] = self.options[key]
            if "recursive" in self.options:
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

        if root.visibility == Visibility.Private:
            options["private"] = ""
        elif root.visibility == Visibility.Protected:
            options["protected"] = ""
        elif root.visibility == Visibility.Package:
            options["package"] = ""
        if root.is_async:
            options["async"] = ""
        if root.is_deprecated:
            options["deprecated"] = ""

        for option, value in root.parsed_options.items():
            if option in AutoObjectDirective.option_spec:
                try:
                    options[option] = AutoObjectDirective.option_spec[option](value)
                except ValueError as e:
                    raise self.error(
                        f"invalid !doc option {option} in object {self.arguments[0]}: {e}"
                    ) from None
            else:
                raise self.error(
                    f"unknown !doc option {option} in object {self.arguments[0]}"
                )

        return cls(
            directive_name,
            [name],
            options,
            self.content if top_level else docutils.statemachine.StringList(),
            self.lineno if top_level else 0,
            self.content_offset if top_level else 0,
            self.block_text if top_level else "",
            self.state,
            self.state_machine,
            root=root,
        )

    @property
    def objtree(self) -> Object:
        return self.env.domaindata["lua"]["objtree"]

    @functools.cached_property
    def parent(self):
        modname = self.env.ref_context.get("lua:module", None)
        classname = self.env.ref_context.get("lua:class", None)
        if classname:
            basepath = ".".join(filter(None, [modname, classname]))
            return self.objtree.find(basepath)


class AutodocDirectiveMixin(AutodocUtilsMixin):
    def __init__(self, *args, root: Object):
        super().__init__(*args)
        self.root = root

    def run(self) -> list[docutils.nodes.Node]:
        for file in self.root.files:
            self.state.document.settings.record_dependencies.add(str(file))
        return super().run()  # type: ignore

    def render_root_docstring(
        self, content_node: sphinx.addnodes.desc_content, fullname: str | None
    ) -> None:
        if self.root.parsed_docstring:
            nodes = self.render_docs(
                str(self.root.docstring_file or f"<docstring for {self.arguments[0]}>"),
                self.root.line or 0,
                self.root.parsed_docstring,
                titles=True,
            )

            if (
                "synopsis" not in self.options
                and "no-index" not in self.options
                and fullname
                and nodes
                and isinstance(nodes[0], docutils.nodes.paragraph)
            ):
                objects = self.env.domaindata["lua"]["objects"]
                if fullname in objects:
                    docname, objtype, deprecated, prev_synopsis = objects[fullname]
                    if not prev_synopsis:
                        synopsis = nodes[0].astext()
                        objects[fullname] = docname, objtype, deprecated, synopsis

            content_node += nodes


class AutodocObjectMixin(AutodocDirectiveMixin, sphinx_lua_ls.domain.LuaObject[Any]):
    def transform_content(self, content_node: sphinx.addnodes.desc_content) -> None:
        fullname = self.names[-1][0] if self.names else None
        self.render_root_docstring(content_node, fullname)
        if self.allow_nesting:
            for name, child in _iter_children(
                self.root, self.objtree, self.parent, self.options
            ):
                content_node += self.render(child, name)


class LuaFunction(AutodocObjectMixin, sphinx_lua_ls.domain.LuaFunction):
    def parse_signature(self, sig):
        assert isinstance(self.root, sphinx_lua_ls.objtree.Function)
        return (
            self.arguments[0],
            (
                [(p.name or "", p.type or "") for p in self.root.params],
                [(p.name or "", p.type or "") for p in self.root.returns],
            ),
        )

    def transform_content(self, content_node: sphinx.addnodes.desc_content) -> None:
        assert isinstance(self.root, sphinx_lua_ls.objtree.Function)

        fullname = self.names[-1][0] if self.names else None
        self.render_root_docstring(content_node, fullname)

        for child in content_node:
            if isinstance(child, docutils.nodes.field_list):
                field_list = child
                break
        else:
            field_list = docutils.nodes.field_list()
            content_node += field_list

        for i, param in enumerate(self.root.params):
            if param.docstring and "\n" in param.docstring:
                continue
            if param.parsed_docstring and not (i == 0 and param.name == "self"):
                if param.type:
                    obj = self.objtree.find(param.type)
                    if obj and obj.docstring == param.docstring:
                        continue

                field_body = docutils.nodes.field_body("")
                field_body += self.render_docs(
                    str(
                        self.root.docstring_file
                        or f"<docstring for {self.arguments[0]}, param {param.name}>"
                    ),
                    self.root.line or 0,
                    param.parsed_docstring,
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
            if param.docstring and "\n" in param.docstring:
                continue
            if param.parsed_docstring:
                if param.type:
                    obj = self.objtree.find(param.type)
                    if obj and obj.docstring == param.docstring:
                        continue

                field_body = docutils.nodes.field_body("")
                field_body += self.render_docs(
                    str(
                        self.root.docstring_file
                        or f"<docstring for {self.arguments[0]}, param {param.name}>"
                    ),
                    self.root.line or 0,
                    param.parsed_docstring,
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


class LuaData(AutodocObjectMixin, sphinx_lua_ls.domain.LuaData):
    def parse_signature(self, sig):
        return (
            self.arguments[0],
            self.root.type if isinstance(self.root, sphinx_lua_ls.objtree.Data) else "",
        )


class LuaTable(AutodocObjectMixin, sphinx_lua_ls.domain.LuaTable):
    def parse_signature(self, sig):
        return (self.arguments[0], None)


class LuaAlias(AutodocObjectMixin, sphinx_lua_ls.domain.LuaAlias):
    def parse_signature(self, sig):
        assert isinstance(self.root, sphinx_lua_ls.objtree.Alias)
        if _FIX_FLAKY_ALIAS_TESTS:
            return self.arguments[0], "__alias_base_type"
        return self.arguments[0], self.root.type


class LuaClass(AutodocObjectMixin, sphinx_lua_ls.domain.LuaClass):
    def parse_signature(self, sig):
        assert isinstance(self.root, sphinx_lua_ls.objtree.Class)
        return self.arguments[0], self.root.bases


class LuaModule(AutodocDirectiveMixin, sphinx_lua_ls.domain.LuaModule):
    option_spec: ClassVar[dict[str, Callable[[str], Any]]]

    def run(self) -> list[docutils.nodes.Node]:
        nodes = super().run()

        nodes.extend(self.parse_content_to_nodes(allow_section_headings=True))

        content_node = sphinx.addnodes.desc_content()
        self.render_root_docstring(content_node, self.arguments[0])
        nodes.extend(content_node.children)

        if "index-table" in self.options or "index-title" in self.options:
            index = docutils.nodes.section("", names=[])
            nodes.append(index)

            title = self.options.get("index-title", None) or "Index"
            index["name"] = docutils.nodes.fully_normalize_name(title)
            index["names"].append(index["name"])
            index += docutils.nodes.title("", title)
            self.state.document.note_implicit_target(index, index)

            index += sphinx_lua_ls.autoindex.AutoIndexNode("", target=self.arguments[0])

        groupwise = (
            self.options.get("module-member-order")
            or self.options.get("member-order")
            or "bysource"
        ) == "groupwise"

        api_docs = docutils.nodes.section("", names=[])

        domain: sphinx_lua_ls.domain.LuaDomain = self.env.get_domain("lua")  # type: ignore
        prev_title = None
        for name, child in _iter_children(
            self.root, self.objtree, self.parent, self.options
        ):
            if groupwise:
                kind = child.kind or Kind.Data
                title = domain.object_types[kind.value].lname.title()

                if prev_title != title:
                    if api_docs.children:
                        nodes.append(api_docs)

                    api_docs = docutils.nodes.section("", names=[])

                    api_docs["name"] = docutils.nodes.fully_normalize_name(title)
                    api_docs["names"].append(api_docs["name"])
                    api_docs += docutils.nodes.title("", title)
                    self.state.document.note_implicit_target(api_docs, api_docs)

                    prev_title = title

            api_docs += self.render(child, name)

        if api_docs.children:
            if groupwise:
                nodes.append(api_docs)
            elif "index-table" in self.options or "title" in self.options:
                title = self.options.get("title", None) or "Api reference"
                api_docs["name"] = docutils.nodes.fully_normalize_name(title)
                api_docs["names"].append(api_docs["name"])
                api_docs.insert(0, docutils.nodes.title("", title))
                self.state.document.note_implicit_target(api_docs, api_docs)
                nodes.append(api_docs)
            else:
                # No title in section, add as a container instead.
                nodes.extend(api_docs.children)

        return nodes


class AutoObjectDirective(AutodocUtilsMixin):
    required_arguments = 1
    has_content = True

    def run(self):
        for name, option in self.env.domaindata["lua"]["config"][
            "default_options"
        ].items():
            if name not in self.options:
                self.options[name] = option

        name = self.arguments[0].strip()

        if not name:
            raise self.error(f"got an empty object name")

        found = self.get_root(name)
        if not found:
            raise self.error(f"unknown lua object {name}")

        root, modname, classname, objname = found

        self.push_context(modname, classname)
        try:
            return self.render(root, objname, top_level=True)
        finally:
            self.pop_context()

    def get_root(self, name: str) -> tuple[Object, str, str, str] | None:
        modname = self.options.get("module", self.env.ref_context.get("lua:module"))
        classname = self.env.ref_context.get("lua:class", None)

        candidates = [
            ".".join(filter(None, [modname, classname, name])),
            ".".join(filter(None, [modname, name])),
            ".".join(filter(None, [name])),
        ]

        for candidate in candidates:
            if found := self.objtree.find_path(candidate):
                return found
