"""
Autodoc directives for lua.

"""

from __future__ import annotations

import dataclasses
import functools
import math
import os
from typing import Any, Callable, ClassVar, Type, cast

import docutils.nodes
import docutils.statemachine
import sphinx.addnodes
import sphinx.util
from docutils.parsers.rst import directives
from sphinx.util.docutils import SphinxDirective
from sphinx.util.parsing import nested_parse_to_nodes

import sphinx_lua_ls.autoindex
import sphinx_lua_ls.domain
import sphinx_lua_ls.inherited
import sphinx_lua_ls.objtree
from sphinx_lua_ls import utils
from sphinx_lua_ls.objtree import Kind, Object, Visibility

# Dirty hack =(
# Alias files and types are not properly reported sometimes.
_FIX_FLAKY_ALIAS_TESTS = "_LUA_LS_FIX_FLAKY_ALIAS_TESTS" in os.environ


def _iter_children(
    obj: Object,
    objtree: Object,
    parent: Object | None,
    options: dict[str, Any],
    include_globals: bool = True,
):
    children = list(obj.children.items())

    if obj.kind == Kind.Module and (globals := options.get("globals")):
        if globals is True:
            filter_globals = lambda _: True
        else:
            filter_globals = lambda name: name in globals

        if include_globals and obj.kind == Kind.Module:
            for name, child in objtree.children.items():
                if (
                    not child.is_foreign
                    and child.kind != Kind.Module
                    and filter_globals(name)
                    and obj.files & child.files
                ):
                    children.append((name, child))

    if obj.kind == Kind.Module:
        order = (
            options.get("module-member-order")
            or options.get("member-order")
            or "bysource"
        )
    else:
        order = options.get("member-order") or "bysource"
    match order:
        case "alphabetical":
            children.sort(key=lambda ch: ch[0].lower())
        case "groupwise":
            children.sort(
                key=lambda ch: (
                    -ch[1].is_toplevel,
                    (ch[1].kind or Kind.Data).order,
                    ch[0],
                )
            )
        case "bysource":
            children.sort(
                key=lambda ch: (
                    (
                        str(ch[1].docstring_file or "~")
                        if not _FIX_FLAKY_ALIAS_TESTS
                        else ""
                    ),
                    ch[1].line or math.inf,
                    ch[0],
                )
            )
        case _:
            raise RuntimeError(f"unknown member order {order}")

    inherited_names = set()

    if (
        parent
        and parent.kind == Kind.Class
        and isinstance(parent, sphinx_lua_ls.objtree.Class)
    ):
        for base in objtree.find_all_bases(parent):
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
        if name not in include and not child.is_toplevel:
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
        "members": utils.parse_list_option_or_true,
        "undoc-members": utils.parse_list_option_or_true,
        "private-members": utils.parse_list_option_or_true,
        "protected-members": utils.parse_list_option_or_true,
        "package-members": utils.parse_list_option_or_true,
        "special-members": utils.parse_list_option_or_true,
        "inherited-members": utils.parse_list_option_or_true,
        "exclude-members": utils.parse_list_option_or_true,
        "title": directives.unchanged,
        "index-title": directives.unchanged,
        "recursive": directives.flag,
        "index-table": directives.flag,
        "inherited-members-table": directives.flag,
        "member-order": lambda x: directives.choice(
            x, ("alphabetical", "groupwise", "bysource")
        ),
        "module-member-order": lambda x: directives.choice(
            x, ("alphabetical", "groupwise", "bysource")
        ),
        "globals": utils.parse_list_option_or_true,
        "class-doc-from": lambda x: directives.choice(
            x, ("class", "both", "ctor", "separate", "none")
        ),
        "class-signature": lambda x: directives.choice(
            x, ("bases", "both", "ctor", "minimal")
        ),
        "annotate-require": lambda x: directives.choice(
            x, ("always", "never", "auto", "force")
        ),
        "require-function-name": directives.unchanged,
        "require-separator": directives.unchanged,
    }
    option_spec.update(
        {
            f"no-{key}": directives.flag
            for key in sphinx_lua_ls.domain.GLOBAL_OPTIONS & set(option_spec)
        }
    )
    option_spec.update(sphinx_lua_ls.domain.LuaObject.option_spec)

    def render(
        self,
        root: Object,
        name: str,
        top_level: bool = False,
        kind_override: Kind | None = None,
        doctype_override: str | None = None,
        signature_override: list[str] | None = None,
    ):
        if root.kind is None:
            what = root.__class__.__name__.lower()
            modname = self.env.ref_context.get("lua:module")
            classname = self.env.ref_context.get("lua:classname")
            fullname = ".".join(filter(None, [modname, classname, name]))
            raise self.error(
                f"{what} {fullname} can't have !doctype {root.parsed_doctype}"
            )
        if kind_override and (
            (kind_override != root.kind)
            or (root.parsed_doctype and doctype_override != root.parsed_doctype)
        ):
            what = root.parsed_doctype or root.kind.value
            modname = self.env.ref_context.get("lua:module")
            classname = self.env.ref_context.get("lua:classname")
            fullname = ".".join(filter(None, [modname, classname, name]))
            msg = f"lua:auto{doctype_override} can't be used on {what} {fullname}. please, "
            if root.get_kind(doctype_override) is not None:
                msg += f"either set !doctype {doctype_override} for {fullname}, or "
            msg += f"use lua:auto{what} instead"
            raise self.error(msg)

        match root.kind:
            case Kind.Data:
                return self._render_data(
                    root, name, top_level, doctype_override, signature_override
                )
            case Kind.Table:
                return self._render_table(
                    root, name, top_level, doctype_override, signature_override
                )
            case Kind.Module:
                return self._render_module(
                    root, name, top_level, doctype_override, signature_override
                )
            case Kind.Function:
                return self._render_function(
                    root, name, top_level, doctype_override, signature_override
                )
            case Kind.Class:
                return self._render_class(
                    root, name, top_level, doctype_override, signature_override
                )
            case Kind.Alias:
                return self._render_alias(
                    root, name, top_level, doctype_override, signature_override
                )
            case Kind.Enum:
                return self._render_enum(
                    root, name, top_level, doctype_override, signature_override
                )

    def _render_module(
        self,
        root: Object,
        name: str,
        top_level: bool = False,
        doctype_override: str | None = None,
        signature_override: list[str] | None = None,
    ):
        if top_level:
            modname = self.env.ref_context.get("lua:module")
            classname = self.env.ref_context.get("lua:classname")
            fullname = ".".join(filter(None, [modname, classname, name]))

            return self._create_directive(
                fullname, LuaModule, "lua:module", root, top_level, signature_override
            ).run()
        else:
            # Non-toplevel modules are rendered as tables.
            # They still have objtype "module", though.
            return self._create_directive(
                name, LuaTable, "lua:module", root, top_level, signature_override
            ).run()

    def _render_table(
        self,
        root: Object,
        name: str,
        top_level: bool = False,
        doctype_override: str | None = None,
        signature_override: list[str] | None = None,
    ):
        return self._create_directive(
            name,
            LuaTable,
            "lua:" + (doctype_override or root.parsed_doctype or "table"),
            root,
            top_level,
            signature_override,
        ).run()

    def _render_data(
        self,
        root: Object,
        name: str,
        top_level: bool = False,
        doctype_override: str | None = None,
        signature_override: list[str] | None = None,
    ):
        return self._create_directive(
            name,
            LuaData,
            "lua:" + (doctype_override or root.parsed_doctype or "data"),
            root,
            top_level,
            signature_override,
        ).run()

    def _render_function(
        self,
        root: Object,
        name: str,
        top_level: bool = False,
        doctype_override: str | None = None,
        signature_override: list[str] | None = None,
    ):
        assert isinstance(root, sphinx_lua_ls.objtree.Function)
        if doctype := doctype_override or root.parsed_doctype:
            objtype = doctype
        elif self.parent and self.parent.kind == Kind.Class:
            if not root.params or root.params[0].name != "self":
                objtype = "staticmethod"
            else:
                objtype = "method"
        else:
            objtype = "function"

        return self._create_directive(
            name, LuaFunction, "lua:" + objtype, root, top_level, signature_override
        ).run()

    def _render_class(
        self,
        root: Object,
        name: str,
        top_level: bool = False,
        doctype_override: str | None = None,
        signature_override: list[str] | None = None,
    ):
        assert isinstance(root, sphinx_lua_ls.objtree.Class)
        return self._create_directive(
            name,
            LuaClass,
            "lua:" + (doctype_override or root.parsed_doctype or "class"),
            root,
            top_level,
            signature_override,
        ).run()

    def _render_alias(
        self,
        root: Object,
        name: str,
        top_level: bool = False,
        doctype_override: str | None = None,
        signature_override: list[str] | None = None,
    ):
        return self._create_directive(
            name,
            LuaAlias,
            "lua:" + (doctype_override or root.parsed_doctype or "alias"),
            root,
            top_level,
            signature_override,
        ).run()

    def _render_enum(
        self,
        root: Object,
        name: str,
        top_level: bool = False,
        doctype_override: str | None = None,
        signature_override: list[str] | None = None,
    ):
        return self._create_directive(
            name,
            LuaAlias,
            "lua:" + (doctype_override or root.parsed_doctype or "enum"),
            root,
            top_level,
            signature_override,
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
        top_level: bool,
        signature_override: list[str] | None,
    ) -> SphinxDirective:
        if top_level:
            options = self.orig_options.copy()
            options.pop("module", None)
        else:
            options = {}
            for key in [
                "member-order",
                "no-member-order",
                "module-member-order",
                "no-module-member-order",
                "recursive",
                "no-recursive",
                "no-index",
                "no-no-index",
                "no-index-entry",
                "no-no-index-entry",
                "no-contents-entry",
                "no-no-contents-entry",
                "inherited-members-table",
                "no-inherited-members-table",
                "class-doc-from",
                "no-class-doc-from",
                "class-signature",
                "no-class-signature",
                "annotate-require",
                "no-annotate-require",
                "require-function-name",
                "no-require-function-name",
                "require-separator",
                "no-require-separator",
            ]:
                if key in self.orig_options:
                    options[key] = self.orig_options[key]
            if "recursive" in self.orig_options:
                for key in [
                    "members",
                    "globals",
                    "undoc-members",
                    "private-members",
                    "protected-members",
                    "package-members",
                    "special-members",
                    "inherited-members",
                    "using",
                ]:
                    if key in self.orig_options:
                        if self.orig_options[key] is True:
                            options[key] = self.orig_options[key]
                        elif (
                            self.orig_options[key] and self.orig_options[key][0] == "+"
                        ):
                            options[key] = self.orig_options[key]
                            if f"no-{key}" in self.orig_options:
                                options[f"no-{key}"] = self.orig_options[f"no-{key}"]

        match root.visibility:
            case Visibility.Private:
                options["private"] = ""
            case Visibility.Protected:
                options["protected"] = ""
            case Visibility.Package:
                options["package"] = ""
            case _:
                pass
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

        if root.using:
            options.setdefault("using", []).extend(
                map(utils.normalize_type, root.using)
            )

        if root.is_toplevel:
            options["module"] = ""
            if not top_level:
                options["global"] = ""

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
            signature_override=signature_override,
        )

    @property
    def objtree(self) -> Object:
        return self.lua_domain.objtree

    @functools.cached_property
    def parent(self):
        modname = self.env.ref_context.get("lua:module", None)
        classname = self.env.ref_context.get("lua:class", None)
        if classname:
            basepath = ".".join(filter(None, [modname, classname]))
            return self.objtree.find(basepath)


class AutodocDirectiveMixin(AutodocUtilsMixin):
    def __init__(self, *args, root: Object, signature_override: list[str] | None):
        super().__init__(*args)
        self.root = root
        self.signature_override = signature_override

    def run(self) -> list[docutils.nodes.Node]:
        for file in self.root.files:
            self.state.document.settings.record_dependencies.add(str(file))
        return super().run()  # type: ignore

    def render_root_docstring(
        self, content_node: sphinx.addnodes.desc_content, fullname: str | None
    ) -> None:
        if self.root.parsed_docstring:
            nodes = self.render_docs(
                str(self.root.docstring_file or f"<docstring for {fullname}>"),
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
                if fullname in self.lua_domain.objects:
                    data = self.lua_domain.objects[fullname]
                    if not data.synopsis:
                        self.lua_domain.objects[fullname] = dataclasses.replace(
                            data, synopsis=nodes[0].astext()
                        )

            content_node += nodes

        if self.root.see:
            node = sphinx.addnodes.seealso()
            content_node += node

            p = docutils.nodes.paragraph()
            node += p

            sep = ""
            for see in self.root.see:
                if sep:
                    p += docutils.nodes.Text(sep)
                ref_nodes, warn_nodes = sphinx_lua_ls.domain.LuaXRefRole()(
                    "lua:obj", see, see, 0, self.state.inliner
                )
                p += ref_nodes
                p += warn_nodes
                sep = ", "

        annotate_require = self.options.get("annotate-require", "auto")
        if (
            self.name == "lua:module"
            and annotate_require != "never"
            and (annotate_require == "force" or self.root.require_type is not None)
        ):
            require_function_name = (
                utils.normalize_type(
                    self.options.get(
                        "require-function-name", self.root.require_function or ""
                    ).strip()
                )
                or "require"
            )

            require_separator = (
                self.options.get(
                    "require-separator", self.root.require_separator or "."
                ).strip()
                or "."
            )

            require_path: str = self.env.ref_context["lua:module"]
            if require_separator != ".":
                require_path = require_path.replace(".", require_separator)

            if self.root.require_type:
                typ = utils.normalize_type(self.root.require_type)
                ref_nodes, warn_nodes = sphinx_lua_ls.domain.LuaXRefRole()(
                    "lua:obj", typ, typ, 0, self.state.inliner
                )
                content_node += docutils.nodes.paragraph(
                    "",
                    "",
                    docutils.nodes.strong("", "Require: "),
                    docutils.nodes.literal(
                        "",
                        f"{require_function_name}" f'("{require_path}"): ',
                        *ref_nodes,
                        *warn_nodes,
                    ),
                )
            elif annotate_require in ("always", "force"):
                content_node += docutils.nodes.paragraph(
                    "",
                    "",
                    docutils.nodes.strong("", "Require: "),
                    docutils.nodes.literal(
                        "",
                        f"{require_function_name}" f'("{require_path}")',
                    ),
                )


class AutodocObjectMixin(AutodocDirectiveMixin, sphinx_lua_ls.domain.LuaObject[Any]):
    def get_signatures(self) -> list[str]:
        if self.signature_override is not None:
            return self.signature_override
        else:
            return self.make_signatures()

    def make_signatures(self) -> list[str]:
        return self.arguments

    def parse_signature(self, sig: str) -> tuple[str, Any]:
        if self.signature_override is not None:
            return super().parse_signature(sig)
        else:
            return self.parse_made_signature(sig)

    def parse_made_signature(self, sig: str) -> tuple[str, Any]:
        raise NotImplementedError()

    def transform_content(self, content_node: sphinx.addnodes.desc_content) -> None:
        fullname = self.names[-1][0] if self.names else None
        self.render_root_docstring(content_node, fullname)
        if self.allow_nesting:
            for name, child in _iter_children(
                self.root, self.objtree, self.parent, self.options
            ):
                content_node += self.render(child, name)


class LuaFunction(AutodocObjectMixin, sphinx_lua_ls.domain.LuaFunction):
    def make_signatures(self) -> list[str]:
        assert isinstance(self.root, sphinx_lua_ls.objtree.Function)
        return super().make_signatures() + self.root.overloads

    def parse_made_signature(self, sig):
        if sig == self.arguments[0]:
            assert isinstance(self.root, sphinx_lua_ls.objtree.Function)
            return (
                sig,
                (
                    [(p.name or "", p.type or "") for p in self.root.generics],
                    [(p.name or "", p.type or "") for p in self.root.params],
                    [(p.name or "", p.type or "") for p in self.root.returns],
                ),
            )
        else:
            return (
                self.arguments[0],
                sphinx_lua_ls.domain.LuaFunction.parse_signature(self, sig)[1],
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
    def parse_made_signature(self, sig):
        return (
            self.arguments[0],
            self.root.type if isinstance(self.root, sphinx_lua_ls.objtree.Data) else "",
        )


class LuaTable(AutodocObjectMixin, sphinx_lua_ls.domain.LuaTable):
    def parse_made_signature(self, sig):
        return (self.arguments[0], None)


class LuaAlias(AutodocObjectMixin, sphinx_lua_ls.domain.LuaAlias):
    def parse_made_signature(self, sig):
        if isinstance(self.root, sphinx_lua_ls.objtree.Alias):
            if _FIX_FLAKY_ALIAS_TESTS:
                return self.arguments[0], ([], "__alias_base_type")
            return self.arguments[0], (
                [(p.name or "", p.type or "") for p in self.root.generics],
                self.root.type,
            )
        elif isinstance(self.root, sphinx_lua_ls.objtree.Enum):
            return self.arguments[0], (
                [(p.name or "", p.type or "") for p in self.root.generics],
                "",
            )
        else:
            assert False


class LuaClass(AutodocObjectMixin, sphinx_lua_ls.domain.LuaClass):
    def make_signatures(self) -> list[str]:
        assert isinstance(self.root, sphinx_lua_ls.objtree.Class)

        self.collected_bases = self.root.bases

        if self.root.constructor:
            self.constructor_sig = self.root.constructor
        else:
            for base in self.objtree.find_all_bases(self.root):
                if isinstance(base, sphinx_lua_ls.objtree.Class) and base.constructor:
                    self.constructor_sig = base.constructor
                    break
            else:
                self.constructor_sig = None

        if self.constructor_sig is not None and self.constructor_sig.is_async:
            self.options["async"] = True

        signatures = []

        class_signature_from = self.options.get("class-signature", "both")

        if self.options.get("class-doc-from", "both") == "separate":
            signatures.append(self.arguments[0])
            self.print_bases = class_signature_from != "ctor"
        else:
            if class_signature_from in ("both", "bases") or (
                class_signature_from == "minimal"
                and (self.root.bases or not self.constructor_sig)
            ):
                signatures.append(self.arguments[0])
                self.print_bases = True

            if class_signature_from == "ctor" or (
                class_signature_from in ("minimal", "both") and self.constructor_sig
            ):
                if self.constructor_sig:
                    signatures.append("")
                    signatures.extend(
                        str(i) for i in range(len(self.constructor_sig.overloads))
                    )
                else:
                    signatures.append("")

        return signatures

    def parse_made_signature(self, sig):
        assert isinstance(self.root, sphinx_lua_ls.objtree.Class)

        if sig == self.arguments[0]:
            # Bases
            return sig, (
                [(p.name or "", p.type or "") for p in self.root.generics],
                self.root.bases if self.print_bases else [],
                None,
                None,
            )
        elif not sig:
            # Ctor
            if not self.constructor_sig:
                return self.arguments[0], ([], None, [], [])
            else:
                return self.arguments[0], (
                    [
                        (p.name or "", p.type or "")
                        for p in self.constructor_sig.generics
                    ],
                    None,
                    [(p.name or "", p.type or "") for p in self.constructor_sig.params],
                    [
                        (p.name or "", p.type or "")
                        for p in self.constructor_sig.returns
                    ],
                )
        else:
            # Ctor overload
            assert self.constructor_sig
            i = int(sig)  # What a dirty hack =(
            overload = self.constructor_sig.overloads[i]
            _, (
                generics,
                params,
                returns,
            ) = sphinx_lua_ls.domain.LuaFunction.parse_function_signature(overload)
            return self.arguments[0], (generics, None, params, returns)

    def transform_content(self, content_node: sphinx.addnodes.desc_content):
        assert isinstance(self.root, sphinx_lua_ls.objtree.Class)

        fullname = self.names[-1][0] if self.names else None

        class_doc_from = self.options.get("class-doc-from", "both")

        if class_doc_from not in ("ctor", "none"):
            self.render_root_docstring(content_node, fullname)

        if self.root.constructor:
            if class_doc_from == "separate":
                content_node += self.render(
                    self.root.constructor, self.root.constructor_name or "__call", False
                )
            elif class_doc_from not in ("class", "none"):
                directive = cast(
                    LuaFunction,
                    self._create_directive(
                        self.root.constructor_name or "__call",
                        LuaFunction,
                        "lua:function",
                        self.root.constructor,
                        False,
                        None,
                    ),
                )

                directive.options["no-index"] = ""

                ctor_nodes = directive.run()
                for node in ctor_nodes:
                    if isinstance(node, sphinx.addnodes.desc):
                        content_node.extend(node.children[-1].children)

        if self.allow_nesting:
            for name, child in _iter_children(
                self.root, self.objtree, self.parent, self.options
            ):
                content_node += self.render(child, name)

        if "inherited-members-table" in self.options:
            content_node += sphinx_lua_ls.inherited.InheritedMethodsNode(
                target=fullname
            )


class LuaModule(AutodocDirectiveMixin, sphinx_lua_ls.domain.LuaModule):
    option_spec: ClassVar[dict[str, Callable[[str], Any]]]

    def run(self) -> list[docutils.nodes.Node]:
        if self.signature_override is not None:
            raise self.error("modules can't have signature overrides")

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

        prev_title = None
        for name, child in _iter_children(
            self.root, self.objtree, self.parent, self.options
        ):
            if groupwise:
                kind = child.kind or Kind.Data
                if child.is_toplevel:
                    title = "Global"
                else:
                    title = self.lua_domain.object_types[kind.value].lname.title()

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
    final_argument_whitespace = True
    has_content = True

    kind_override: Kind | None = None
    doctype_override: str | None = None

    def run(self):
        self.prepare_options()

        signatures: list[str] = []
        has_signature_overrides = False
        name = None
        for sig in self.get_signatures():
            sig_name, sig_rest = utils.separate_name_prefix(sig)
            signatures.append(sig_rest)
            if sig_rest:
                has_signature_overrides = True
            if name is not None and sig_name != name:
                raise self.error(
                    f"got multiple different names for a single autodoc directive: "
                    f"{name!r} and {sig_name!r}"
                )
            name = sig_name

        if not name:
            raise self.error(f"got an empty object name")

        found = self.get_root(name)
        if not found:
            raise self.error(f"unknown lua object {name}")

        root, modname, classname, objname = found

        if has_signature_overrides:
            signature_override = [f"{objname}{sig}" for sig in signatures]
        else:
            signature_override = None

        if root.is_toplevel:
            # Preserve parent modname so that globals can link to their modules.
            modname = self.env.ref_context.get("lua:module")
            self.push_context(modname or "", "", root.using)
        else:
            self.push_context(modname, classname, root.using)

        try:
            return self.render(
                root,
                objname,
                top_level=True,
                kind_override=self.kind_override,
                doctype_override=self.doctype_override,
                signature_override=signature_override,
            )
        finally:
            self.pop_context()

    def get_signatures(self) -> list[str]:
        return sphinx_lua_ls.domain.LuaObject.get_signatures(self)  # type: ignore

    def get_root(self, name: str) -> tuple[Object, str, str, str] | None:
        modname = self.options.get("module", self.env.ref_context.get("lua:module"))
        if "module" in self.options:
            classname = ""
        else:
            classname = self.env.ref_context.get("lua:class", "")

        candidates = [
            ".".join(filter(None, [modname, classname, name])),
            ".".join(filter(None, [modname, name])),
            ".".join(filter(None, [name])),
        ]

        for candidate in candidates:
            if found := self.objtree.find_path(candidate):
                return found


class AutoFunctionDirective(AutoObjectDirective):
    kind_override = Kind.Function
    doctype_override = "function"


class AutoDataDirective(AutoObjectDirective):
    kind_override = Kind.Data
    doctype_override = "data"


class AutoConstDirective(AutoObjectDirective):
    kind_override = Kind.Data
    doctype_override = "const"


class AutoClassDirective(AutoObjectDirective):
    kind_override = Kind.Class
    doctype_override = "class"


class AutoAliasDirective(AutoObjectDirective):
    kind_override = Kind.Alias
    doctype_override = "alias"


class AutoEnumDirective(AutoObjectDirective):
    kind_override = Kind.Enum
    doctype_override = "enum"


class AutoMethodDirective(AutoObjectDirective):
    kind_override = Kind.Function
    doctype_override = "method"


class AutoClassmethodDirective(AutoObjectDirective):
    kind_override = Kind.Function
    doctype_override = "classmethod"


class AutoStaticmethodDirective(AutoObjectDirective):
    kind_override = Kind.Function
    doctype_override = "staticmethod"


class AutoAttributeDirective(AutoObjectDirective):
    kind_override = Kind.Data
    doctype_override = "attribute"


class AutoTableDirective(AutoObjectDirective):
    kind_override = Kind.Table
    doctype_override = "table"


class AutoModuleDirective(AutoObjectDirective):
    kind_override = Kind.Module
    doctype_override = "module"
