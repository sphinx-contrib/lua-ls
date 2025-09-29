"""
Lua domain.

This code is based on ``sphinxcontrib.luadomain`` by Eliott Dumeix.

See the original code here: https://github.com/boolangery/sphinx-luadomain

"""

import dataclasses
import typing as _t
from collections.abc import Set
from dataclasses import dataclass
from typing import Any, Callable, ClassVar, Generic, Iterator, TypeVar

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.parsers.rst.states import Inliner
from sphinx import addnodes
from sphinx.builders import Builder
from sphinx.directives import ObjectDescription
from sphinx.domains import Domain, ObjType
from sphinx.environment import BuildEnvironment
from sphinx.locale import get_translation
from sphinx.roles import XRefRole
from sphinx.util import logging
from sphinx.util.docfields import TypedField
from sphinx.util.docutils import SphinxDirective
from sphinx.util.nodes import make_id, make_refnode

import sphinx_lua_ls.config
import sphinx_lua_ls.objtree
from sphinx_lua_ls import utils

T = TypeVar("T")

MESSAGE_CATALOG_NAME = "sphinx-lua-ls"
_ = get_translation(MESSAGE_CATALOG_NAME)


logger = logging.getLogger("sphinx_lua_ls")


class _SigWriter:
    def __init__(
        self,
        signode: addnodes.desc_signature,
        maximum_signature_line_length: int | None,
    ) -> None:
        self._signode = signode
        self._maximum_signature_line_length = maximum_signature_line_length
        signode["is_multiline"] = True

        self._line = addnodes.desc_signature_line(add_permalink=True)
        signode += self._line

    def br(self):
        self._line["add_permalink"] = False
        self._line = addnodes.desc_signature_line(add_permalink=True)
        self._signode += self._line

    def ident(self):
        self._line += addnodes.desc_sig_space("    ", "    ")

    def name(self, txt: str):
        self._line += addnodes.desc_sig_name(txt, txt)

    def space(self):
        self._line += addnodes.desc_sig_space()

    def operator(self, txt: str):
        self._line += addnodes.desc_sig_operator(txt, txt)

    def punctuation(self, txt: str):
        self._line += addnodes.desc_sig_punctuation(txt, txt)

    def keyword(self, txt: str):
        self._line += addnodes.desc_sig_keyword(txt, txt)

    def keyword_type(self, txt: str):
        self._line += addnodes.desc_sig_keyword_type(txt, txt)

    def literal_number(self, txt: str):
        self._line += addnodes.desc_sig_literal_number(txt, txt)

    def literal_string(self, txt: str):
        self._line += addnodes.desc_sig_literal_string(txt, txt)

    def literal_char(self, txt: str):
        self._line += addnodes.desc_sig_literal_char(txt, txt)

    def typ(self, txt: str, inliner):
        self._line += addnodes.desc_type("", "", *utils.type_to_nodes(txt, inliner))

    def ref(self, txt: str, inliner):
        ref_nodes, warn_nodes = LuaXRefRole()("lua:obj", txt, txt, 0, inliner)
        self._line += addnodes.desc_type("", "", *ref_nodes, *warn_nodes)

    def params(
        self,
        params: list[tuple[str, str]],
        parens: tuple[str, str] | None,
        handle_optionals: bool,
        inliner,
    ):
        estimated_len = sum(
            len(p[0]) + len(p[1]) + (1 if p[0] and p[1] else 0) for p in params
        ) + len(params)
        multiline = (
            self._maximum_signature_line_length is not None
            and estimated_len > self._maximum_signature_line_length
        )

        if multiline and not parens:
            parens = ("(", ")")

        if parens:
            self.punctuation(parens[0])

        for i, (arg, typ) in enumerate(params):
            if multiline:
                self.br()
                self.ident()

            if handle_optionals and arg and typ and typ.endswith("?"):
                arg, typ = arg + "?", typ[:-1]
                if typ.startswith("(") and typ.endswith(")"):
                    typ = typ[1:-1]

            if arg:
                self.name(arg or "_")
            if arg and typ:
                self.punctuation(":")
                self.space()
            if typ:
                self.typ(typ, inliner)
            if i + 1 < len(params):
                self.punctuation(",")
                self.space()

        if multiline:
            self.br()

        if parens:
            self.punctuation(parens[1])

    def list(
        self,
        params: list[str],
        parens: tuple[str, str] | None,
        inliner,
    ):
        estimated_len = sum(len(p) for p in params) + len(params)
        multiline = (
            self._maximum_signature_line_length is not None
            and estimated_len > self._maximum_signature_line_length
        )

        if multiline and not parens:
            parens = ("(", ")")

        if parens:
            self.punctuation(parens[0])

        for i, typ in enumerate(params):
            if multiline:
                self.br()
                self.ident()

            if typ:
                self.typ(typ, inliner)
            if i + 1 < len(params):
                self.punctuation(",")
                self.space()

        if multiline:
            self.br()

        if parens:
            self.punctuation(parens[1])


class LuaTypedField(TypedField):
    def make_field(
        self,
        types: dict[str, list[nodes.Node]],
        domain: str,
        items: list[tuple[str, list[nodes.Node]]],
        env: BuildEnvironment | None = None,
        inliner: Inliner | None = None,
        location: nodes.Element | None = None,
    ) -> nodes.field:
        # Process names and types in :param: and :return: flags.
        for i, (name, content) in enumerate(items):
            if name in types:
                fieldtype = types[name]
                if len(fieldtype) == 1 and isinstance(fieldtype[0], nodes.Text):
                    typename = fieldtype[0].astext()

                    if typename.endswith("?"):
                        new_name, new_typename = name + "?", typename[:-1]
                        if new_typename.startswith("(") and new_typename.endswith(")"):
                            new_typename = new_typename[1:-1]
                        items[i] = (new_name, content)
                        types.pop(name)
                        name, typename = new_name, new_typename

                    if inliner is None:
                        type_body: list[nodes.Node] = [nodes.Text(typename)]
                    else:
                        type_body = utils.type_to_nodes(typename, inliner)

                    types[name] = type_body

        return super().make_field(types, domain, items, env, inliner, location)


class LuaContextManagerMixin(SphinxDirective):
    @property
    def lua_domain(self) -> "LuaDomain":
        return _t.cast(LuaDomain, self.env.get_domain("lua"))

    def push_context(self, modname: str, classname: str, using: list[str] | None):
        classes = self.env.ref_context.setdefault("lua:classes", [])
        classes.append(self.env.ref_context.get("lua:class"))
        if classname:
            self.env.ref_context["lua:class"] = classname
        else:
            self.env.ref_context.pop("lua:class", None)

        modules = self.env.ref_context.setdefault("lua:modules", [])
        modules.append(self.env.ref_context.get("lua:module"))
        if modname:
            self.env.ref_context["lua:module"] = modname
        else:
            self.env.ref_context.pop("lua:module", None)

        usings = self.env.ref_context.setdefault("lua:usings", [])
        usings.append(self.env.ref_context.get("lua:using"))
        if using:
            self.env.ref_context["lua:using"] = using
        else:
            self.env.ref_context.pop("lua:using", None)

    def pop_context(self):
        classes = self.env.ref_context.setdefault("lua:classes", [])
        if classes:
            self.env.ref_context["lua:class"] = classes.pop()
        else:
            self.env.ref_context.pop("lua:class", None)

        modules = self.env.ref_context.setdefault("lua:modules", [])
        if modules:
            self.env.ref_context["lua:module"] = modules.pop()
        else:
            self.env.ref_context.pop("lua:module", None)

        usings = self.env.ref_context.setdefault("lua:usings", [])
        if usings:
            self.env.ref_context["lua:using"] = usings.pop()
        else:
            self.env.ref_context.pop("lua:using", None)

    def prepare_options(self):
        self.orig_options = self.options.copy()
        for name, option in self.lua_domain.config.default_options.items():
            if f"no-{name}" in self.options:
                continue
            if name not in self.options:
                self.options[name] = option
            else:
                given_option = self.options[name]
                if (
                    isinstance(given_option, list)
                    and given_option
                    and given_option[0] == "+"
                ):
                    if isinstance(option, list):
                        self.options[name] = option + given_option[1:]
                    else:
                        self.options[name] = given_option[1:]


GLOBAL_OPTIONS = {
    "no-index",
    "no-index-entry",
    "no-contents-entry",
    "using",
    "members",
    "undoc-members",
    "private-members",
    "protected-members",
    "package-members",
    "special-members",
    "inherited-members",
    "exclude-members",
    "title",
    "index-title",
    "recursive",
    "index-table",
    "inherited-members-table",
    "member-order",
    "module-member-order",
    "globals",
    "class-doc-from",
    "class-signature",
    "annotate-require",
    "require-function-name",
    "require-separator",
}


class LuaObject(
    ObjectDescription[tuple[str, str, str, str]], LuaContextManagerMixin, Generic[T]
):
    """
    Description of a general Lua object.

    Full object path consists of three parts:

    1. current module,
    2. current class,
    3. object name.

    For example, if there's a module ``app.log``, a class ``Logger`` within,
    and then ``LogLevel`` within ``Logger``, then a full name for ``LogLevel``
    is ``app.log.Logger.LogLevel``.

    """

    option_spec: ClassVar[dict[str, Callable[[str], Any]]] = {  # type: ignore
        "module": directives.unchanged,
        "annotation": directives.unchanged,
        "virtual": directives.flag,
        "private": directives.flag,
        "protected": directives.flag,
        "package": directives.flag,
        "abstract": directives.flag,
        "async": directives.flag,
        "global": directives.flag,
        "deprecated": directives.flag,
        "synopsis": directives.unchanged,
        "using": utils.parse_list_option,
        **ObjectDescription.option_spec,
    }
    option_spec.update(
        {f"no-{key}": directives.flag for key in GLOBAL_OPTIONS & set(option_spec)}
    )

    doc_field_types = [
        LuaTypedField(
            "parameter",
            label=_("Parameters"),
            names=(
                "param",
                "parameter",
                "arg",
                "argument",
            ),
            rolename="",
            typerolename="obj",
            typenames=("paramtype", "type"),
            can_collapse=True,
        ),
        LuaTypedField(
            "returnvalue",
            label=_("Returns"),
            names=("return", "returns"),
            rolename="",
            typerolename="obj",
            typenames=("returntype", "rtype"),
            can_collapse=True,
        ),
    ]

    allow_nesting = False

    collected_bases: list[str] | None = None

    def run(self) -> list[nodes.Node]:
        self.prepare_options()
        return super().run()

    def parse_signature(self, sig: str) -> tuple[str, T]:
        raise NotImplementedError()

    def use_colon_path(self) -> bool:
        return False

    def handle_signature_prefix(
        self, sig: str, signode: addnodes.desc_signature
    ) -> tuple[str, str, str, str, T]:
        name, sigdata = self.parse_signature(sig)

        modname = self.options.get("module", self.env.ref_context.get("lua:module", ""))
        if "module" in self.options:
            classname = ""
        else:
            classname = self.env.ref_context.get("lua:class", "")
        fullname = ".".join(filter(None, [modname, classname, name]))

        # Only display full path if we're not inside of a class.
        prefix = "" if classname else ".".join(filter(None, [modname, classname]))

        descname = name
        if self.use_colon_path():
            if "[" in descname:
                descname_components = utils.separate_sig(descname, ".")
            else:
                descname_components = descname.split(".")
            if len(descname_components) > 1:
                descname = (
                    f"{'.'.join(descname_components[:-1])}:{descname_components[-1]}"
                )
            elif prefix:
                prefix += ":"
        if prefix and not prefix.endswith((".", ":")):
            prefix += "."

        signode["module"] = modname
        signode["class"] = classname
        signode["fullname"] = fullname
        signode["lua:domain_name"] = prefix + descname

        sig_prefix = self.get_signature_prefix(sig, sigdata)
        if sig_prefix:
            signode += addnodes.desc_annotation("", "", *sig_prefix)

        if prefix:
            signode += addnodes.desc_addname(prefix, prefix)

        if descname.startswith("[") and descname.endswith("]"):
            signode += addnodes.desc_sig_punctuation("[", "[")
            signode += addnodes.desc_type(
                "", "", *utils.type_to_nodes(descname[1:-1], self.state.inliner)
            )
            signode += addnodes.desc_sig_punctuation("]", "]")
        else:
            signode += addnodes.desc_name(descname, descname)

        return fullname, modname, classname, name, sigdata

    def get_signature_prefix(
        self, signature: str, sigdata: T, filter_options: set[str] | None = None
    ) -> list[nodes.Node]:
        prefix = []

        annotation = self.options.get("annotation")
        if annotation:
            prefix.extend(
                [
                    addnodes.desc_sig_keyword(annotation, annotation),
                    addnodes.desc_sig_space(),
                ]
            )

        for option in [
            "global",
            "private",
            "protected",
            "package",
            "abstract",
            "virtual",
            "async",
        ]:
            if filter_options and option in filter_options:
                continue
            if option in self.options:
                prefix.extend(
                    [
                        addnodes.desc_sig_keyword(option, option),
                        addnodes.desc_sig_space(),
                    ]
                )

        return prefix

    def needs_arg_list(self) -> bool:
        """May return true if an empty argument list is to be generated even if
        the document contains none.
        """
        return False

    def get_index_text(
        self, fullname: str, modname: str, classname: str, name: str
    ) -> str:
        *prefix_parts, _ = fullname.split(".")
        prefix = ".".join(prefix_parts)
        return f"{name} ({self.objtype} in {prefix})"

    def add_target_and_index(
        self,
        name: tuple[str, str, str, str],
        sig: str,
        signode: addnodes.desc_signature,
    ) -> None:
        fullname, modname, classname, objname = name
        id = make_id(self.env, self.state.document, "lua", fullname)
        if id not in self.state.document.ids:
            signode["names"].append(id)
            signode["ids"].append(id)
            signode["first"] = not self.names
            self.state.document.note_explicit_target(signode)

            objects = self.lua_domain.objects
            globals = self.lua_domain.globals
            members = self.lua_domain.members

            if fullname in objects and self.env.docname != objects[fullname].docname:
                self.state_machine.reporter.warning(
                    "duplicate object description of %s, " % fullname
                    + "other instance in "
                    + self.env.doc2path(objects[fullname].docname)
                    + ", use :no-index: for one of them",
                    line=self.lineno,
                )
            objects[fullname] = LuaDomain.ObjectEntry(
                docname=self.env.docname,
                objtype=self.objtype,
                deprecated="deprecated" in self.options,
                id=id,
                synopsis=self.options.get("synopsis", None),
            )

            if fullname not in globals:
                globals[fullname] = LuaDomain.GlobalEntry(
                    docname=self.env.docname, entries=[]
                )
            else:
                globals[fullname] = dataclasses.replace(
                    globals[fullname], docname=self.env.docname
                )

            if fullname not in members:
                members[fullname] = LuaDomain.MemberEntry(
                    docname=self.env.docname, entries=[], bases=[]
                )
            else:
                members[fullname] = dataclasses.replace(
                    members[fullname], docname=self.env.docname
                )
            if self.collected_bases:
                members[fullname].bases = self.collected_bases
                members[fullname].base_lookup_modname = modname
                members[fullname].base_lookup_classname = classname
                members[fullname].base_lookup_using = self.options.get(
                    "using", self.env.ref_context.get("lua:using", None)
                )

            if "[" in fullname:
                name_components = utils.separate_sig(fullname, ".")
            else:
                name_components = fullname.split(".")

            if self.options.get("module", None) == "" and len(name_components) == 1:
                parent_module = self.env.ref_context.get("lua:module", "")
                parent_class = self.env.ref_context.get("lua:class", "")
                if parent_module and not parent_class:
                    if parent_module not in globals:
                        globals[parent_module] = LuaDomain.GlobalEntry(
                            docname=self.env.docname, entries=[]
                        )
                    globals[parent_module].entries.append(
                        LuaDomain.Entry(fullname=fullname, docname=self.env.docname)
                    )
            elif len(name_components) > 1:
                parent = ".".join(name_components[:-1])
                if parent not in members:
                    members[parent] = LuaDomain.MemberEntry(
                        docname=self.env.docname, entries=[], bases=[]
                    )
                members[parent].entries.append(
                    LuaDomain.Entry(fullname=fullname, docname=self.env.docname)
                )

        if "no-index-entry" not in self.options:
            indextext = self.get_index_text(fullname, modname, classname, objname)
            if indextext:
                self.indexnode["entries"].append(("single", indextext, id, "", None))

    def _object_hierarchy_parts(
        self, sig_node: addnodes.desc_signature
    ) -> tuple[str, ...]:
        if "fullname" not in sig_node:
            return ()
        else:
            return tuple(sig_node["fullname"].split("."))

    def _toc_entry_name(self, sig_node: addnodes.desc_signature) -> str:
        if not sig_node.get("_toc_parts"):
            return ""

        *parents, name = sig_node["_toc_parts"]

        if self.config.toc_object_entries_show_parents == "hide":
            fullname = name
        elif self.config.toc_object_entries_show_parents == "domain":
            fullname = sig_node["lua:domain_name"]
        else:
            fullname = ".".join([*parents, name])

        return utils.make_ref_title(fullname, self.objtype, self.config)

    def before_content(self) -> None:
        if self.names and self.allow_nesting:
            _, modname, classname, objname = self.names[-1]
            if self.objtype == "module" and not classname:
                modname = modname + "." if modname else ""
                modname += objname
            else:
                classname = classname + "." if classname else ""
                classname += objname
            using = self.options.get(
                "using", self.env.ref_context.get("lua:using", None)
            )

            self.push_context(modname, classname, using)

    def after_content(self) -> None:
        if self.names and self.allow_nesting:
            self.pop_context()

    @property
    def maximum_signature_line_length(self) -> int | None:
        return self.lua_domain.config.maximum_signature_line_length


class LuaFunction(
    LuaObject[
        tuple[list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]]
    ]
):
    """
    Everything that looks like a function: functions, methods, static and class methods.

    I.e. everything with signature ``name(params) -> returns``.

    """

    def parse_signature(self, sig):
        return self.parse_function_signature(sig)

    @staticmethod
    def parse_function_signature(sig: str):
        name, sig = utils.separate_name_prefix(sig)
        generics, sig = utils.separate_paren_prefix(sig, ("<", ">"))
        params, returns = utils.separate_paren_prefix(sig)

        if returns and returns.startswith("->"):
            returns = returns[2:].lstrip()
        elif returns and returns.startswith(":"):
            returns = returns[1:].lstrip()
        elif returns:
            raise ValueError("incorrect function return type")

        if returns.startswith("(") and returns.endswith(")"):
            returns = returns[1:-1]

        return name, (
            utils.parse_types(generics, parsingFunctionParams=True),
            utils.parse_types(params, parsingFunctionParams=True),
            utils.parse_types(returns),
        )

    @utils.handle_signature_errors
    def handle_signature(
        self, sig: str, signode: addnodes.desc_signature
    ) -> tuple[str, str, str, str]:
        (
            fullname,
            modname,
            classname,
            name,
            (generics, args, returns),
        ) = self.handle_signature_prefix(sig, signode)

        sw = _SigWriter(signode, self.maximum_signature_line_length)

        if generics:
            sw.params(generics, ("<", ">"), False, self.state.inliner)

        sw.params(args, ("(", ")"), True, self.state.inliner)

        if returns:
            sw.punctuation(":")
            sw.space()
            sw.params(
                returns,
                ("(", ")") if any(n for (n, _) in returns) else None,
                True,
                self.state.inliner,
            )

        return fullname, modname, classname, name

    def needs_arg_list(self) -> bool:
        return True

    def use_colon_path(self) -> bool:
        return self.objtype in ("method", "classmethod")

    def get_signature_prefix(
        self, signature: str, sigdata, filter_options=None
    ) -> list[nodes.Node]:
        prefix = super().get_signature_prefix(signature, sigdata, filter_options)
        if self.objtype not in ("function", "method"):
            prefix.extend(
                [
                    addnodes.desc_sig_keyword("", self.objtype),
                    addnodes.desc_sig_space(),
                ]
            )
        return prefix


class LuaData(LuaObject[str]):
    """
    Variables and other things that have type annotations in their signature.

    I.e. everything with signature ``name type``.

    """

    def parse_signature(self, sig):
        name, sig = utils.separate_name_prefix(sig)

        return name, sig.strip()

    @utils.handle_signature_errors
    def handle_signature(
        self, sig: str, signode: addnodes.desc_signature
    ) -> tuple[str, str, str, str]:
        fullname, modname, classname, name, typ = self.handle_signature_prefix(
            sig, signode
        )

        sw = _SigWriter(signode, self.maximum_signature_line_length)

        if typ:
            if typ.startswith("="):
                sw.space()
                sw.punctuation("=")
                typ = typ[1:]
            elif typ.startswith(":"):
                sw.punctuation(":")
                typ = typ[1:]
            else:
                sw.punctuation(":")
            sw.space()
            sw.typ(typ, self.state.inliner)

        return fullname, modname, classname, name

    def get_signature_prefix(
        self, signature: str, sigdata, filter_options=None
    ) -> list[nodes.Node]:
        prefix = super().get_signature_prefix(signature, sigdata, filter_options)
        if self.objtype not in ("data", "attribute"):
            prefix.extend(
                [
                    addnodes.desc_sig_keyword("", self.objtype),
                    addnodes.desc_sig_space(),
                ]
            )
        return prefix


class LuaAlias(LuaObject[tuple[list[tuple[str, str]], str]]):
    """
    Type aliases and other things that have type assignments in their signature.

    I.e. everything with signature ``name type``.

    """

    allow_nesting = True

    def parse_signature(self, sig):
        name, sig = utils.separate_name_prefix(sig)

        generics, sig = utils.separate_paren_prefix(sig, ("<", ">"))
        if sig.startswith("=") or sig.startswith(":"):
            sig = sig[1:]

        return name, (
            utils.parse_types(generics, parsingFunctionParams=True),
            sig.strip(),
        )

    @utils.handle_signature_errors
    def handle_signature(
        self, sig: str, signode: addnodes.desc_signature
    ) -> tuple[str, str, str, str]:
        (
            fullname,
            modname,
            classname,
            name,
            (generics, typ),
        ) = self.handle_signature_prefix(sig, signode)

        sw = _SigWriter(signode, self.maximum_signature_line_length)

        if generics:
            sw.params(generics, ("<", ">"), False, self.state.inliner)

        if typ:
            sw.space()
            sw.punctuation("=")
            sw.space()
            sw.typ(typ, self.state.inliner)

        return fullname, modname, classname, name

    def get_signature_prefix(
        self, signature: str, sigdata, filter_options=None
    ) -> list[nodes.Node]:
        prefix = super().get_signature_prefix(signature, sigdata, filter_options)
        prefix.extend(
            [
                addnodes.desc_sig_keyword("", self.objtype),
                addnodes.desc_sig_space(),
            ]
        )
        return prefix


class LuaClass(
    LuaObject[
        tuple[
            list[tuple[str, str]],
            list[str] | None,
            list[tuple[str, str]] | None,
            list[tuple[str, str]] | None,
        ]
    ]
):
    """
    Classes and other things that have base types in their signature.

    I.e. everything with signature ``name: base1, base2, ...``.

    These are nested.

    """

    allow_nesting = True

    def parse_signature(self, sig):
        name, sig = utils.separate_name_prefix(sig)

        generics, sig = utils.separate_paren_prefix(sig, ("<", ">"))

        if sig.startswith("("):
            # This is a constructor.

            params, returns = utils.separate_paren_prefix(sig)

            if returns and returns.startswith("->"):
                returns = returns[2:].lstrip()
            if returns and returns.startswith(":"):
                returns = returns[1:].lstrip()
            elif returns:
                raise ValueError("incorrect function return type")

            if returns.startswith("(") and returns.endswith(")"):
                returns = returns[1:-1]

            return name, (
                utils.parse_types(generics, parsingFunctionParams=True),
                None,
                utils.parse_types(params, parsingFunctionParams=True),
                utils.parse_types(returns),
            )

        if sig.startswith("=") or sig.startswith(":"):
            sig = sig[1:]

        return name, (
            utils.parse_types(generics, parsingFunctionParams=True),
            utils.separate_sig(sig),
            None,
            None,
        )

    @utils.handle_signature_errors
    def handle_signature(
        self, sig: str, signode: addnodes.desc_signature
    ) -> tuple[str, str, str, str]:
        (
            fullname,
            modname,
            classname,
            name,
            (generics, bases, params, returns),
        ) = self.handle_signature_prefix(sig, signode)

        sw = _SigWriter(signode, self.maximum_signature_line_length)

        if generics:
            sw.params(generics, ("<", ">"), False, self.state.inliner)

        if bases:
            if self.collected_bases is None:
                self.collected_bases = [utils.normalize_name(base) for base in bases]

            sw.punctuation(":")
            sw.space()
            sw.list(bases, None, self.state.inliner)

        if params is not None:
            sw.params(params, ("(", ")"), True, self.state.inliner)

        if returns:
            sw.punctuation(":")
            sw.space()
            sw.params(
                returns,
                ("(", ")") if any(n for (n, _) in returns) else None,
                True,
                self.state.inliner,
            )

        return fullname, modname, classname, name

    def get_signature_prefix(
        self, signature: str, sigdata, filter_options=None
    ) -> list[nodes.Node]:
        if sigdata[2] is not None:
            # This is a constructor.
            prefix = super().get_signature_prefix(signature, sigdata, set())
            prefix.extend(
                [
                    addnodes.desc_sig_keyword("", self.objtype),
                    addnodes.desc_sig_space(),
                    addnodes.desc_sig_keyword("", "ctor"),
                    addnodes.desc_sig_space(),
                ]
            )
        else:
            # This is a class.
            prefix = super().get_signature_prefix(
                signature, sigdata, {"async", "abstract", "virtual"}
            )
            prefix.extend(
                [
                    addnodes.desc_sig_keyword("", self.objtype),
                    addnodes.desc_sig_space(),
                ]
            )
        return prefix


class LuaTable(LuaObject[None]):
    """
    Like data, but allows nesting. Used to document tables that aren't modules.

    """

    allow_nesting = True

    def parse_signature(self, sig):
        sig = self.arguments[0]

        name, sig = utils.separate_name_prefix(sig)
        if sig:
            raise ValueError("unexpected symbols after table name")

        return name, None

    @utils.handle_signature_errors
    def handle_signature(
        self, sig: str, signode: addnodes.desc_signature
    ) -> tuple[str, str, str, str]:
        fullname, modname, classname, name, _ = self.handle_signature_prefix(
            sig, signode
        )

        return fullname, modname, classname, name

    def get_signature_prefix(
        self, signature: str, sigdata, filter_options=None
    ) -> list[nodes.Node]:
        prefix = super().get_signature_prefix(signature, sigdata, filter_options)
        if self.objtype not in ("table",):
            prefix.extend(
                [
                    addnodes.desc_sig_keyword("", self.objtype),
                    addnodes.desc_sig_space(),
                ]
            )
        return prefix


class LuaModule(LuaContextManagerMixin):
    """
    Directive to mark description of a new module.

    """

    has_content = False
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    option_spec = {
        "no-index": directives.flag,
        "deprecated": directives.flag,
        "synopsis": directives.unchanged,
    }

    def run(self) -> list[nodes.Node]:
        self.prepare_options()

        if self.env.ref_context.get("lua:class", None):
            raise self.severe("lua:module only available on top level")

        sig = self.arguments[0]
        try:
            fullname, sig = utils.separate_name_prefix(sig)
        except ValueError as e:
            raise self.error(str(e))
        if sig:
            raise self.error("unexpected symbols after module name")

        self.env.ref_context["lua:module"] = fullname
        ret = []
        if "no-index" not in self.options:
            objects = self.lua_domain.objects
            globals = self.lua_domain.globals
            members = self.lua_domain.members

            if fullname in objects and self.env.docname != objects[fullname].docname:
                self.state_machine.reporter.warning(
                    f"duplicate object description of {fullname}, "
                    "other instance in "
                    f"{self.env.doc2path(objects[fullname].docname)}, "
                    "use :no-index: for one of them",
                    line=self.lineno,
                )

            id = make_id(self.env, self.state.document, "lua", fullname)

            objects[fullname] = LuaDomain.ObjectEntry(
                docname=self.env.docname,
                objtype="module",
                deprecated="deprecated" in self.options,
                id=id,
                synopsis=self.options.get("synopsis", None),
            )

            if fullname not in globals:
                globals[fullname] = LuaDomain.GlobalEntry(
                    docname=self.env.docname, entries=[]
                )
            else:
                globals[fullname] = dataclasses.replace(
                    globals[fullname], docname=self.env.docname
                )

            if fullname not in members:
                members[fullname] = LuaDomain.MemberEntry(
                    docname=self.env.docname, entries=[], bases=[]
                )
            else:
                members[fullname] = dataclasses.replace(
                    members[fullname], docname=self.env.docname
                )

            if "[" in fullname:
                name_components = utils.separate_sig(fullname, ".")
            else:
                name_components = fullname.split(".")

            if len(name_components) > 1:
                parent = ".".join(name_components[:-1])
                if parent not in members:
                    members[parent] = LuaDomain.MemberEntry(
                        docname=self.env.docname, entries=[], bases=[]
                    )
                members[parent].entries.append(
                    LuaDomain.Entry(fullname=fullname, docname=self.env.docname)
                )

            target_node = nodes.target("", "", ids=[id], ismod=True)
            self.state.document.note_explicit_target(target_node)
            # the platform and synopsis aren't printed; in fact, they are only
            # used in the modindex currently
            ret.append(target_node)
            indextext = _("%s (module)") % fullname
            inode = addnodes.index(entries=[("single", indextext, id, "", None)])
            ret.append(inode)
        return ret


class LuaCurrentModule(SphinxDirective):
    """
    This directive is just to tell Sphinx that we're documenting
    stuff in module foo, but links to module foo won't lead here.
    """

    has_content = False
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    option_spec = {}

    def run(self) -> list[nodes.Node]:
        if self.env.ref_context.get("lua:class", None):
            raise self.severe("lua:currentmodule only available on top level")

        sig = self.arguments[0]
        try:
            modname, sig = utils.separate_name_prefix(sig)
        except ValueError as e:
            raise self.error(str(e))
        if sig:
            raise self.error("unexpected symbols after module name")

        if modname == "None":
            self.env.ref_context.pop("lua:module", None)
        else:
            self.env.ref_context["lua:module"] = modname
        return []


class LuaXRefRole(XRefRole):
    def process_link(
        self,
        env: BuildEnvironment,
        refnode: nodes.Element,
        has_explicit_title: bool,
        title: str,
        target: str,
    ) -> tuple[str, str]:
        refnode["lua:module"] = env.ref_context.get("lua:module")
        refnode["lua:class"] = env.ref_context.get("lua:class")
        refnode["lua:using"] = env.ref_context.get("lua:using")
        if not has_explicit_title:
            title = title.lstrip(".")  # only has a meaning for the target
            target = target.lstrip("~")  # only has a meaning for the title
            # if the first character is a tilde, don't display the module/class
            # parts of the contents
            if title[0:1] == "~":
                title = title[1:]
                dot = title.rfind(".")
                if dot != -1:
                    title = title[dot + 1 :]
        return title, target


class LuaDomain(Domain):
    """Lua language domain."""

    name = "lua"
    label = "Lua"
    object_types: dict[str, ObjType] = {
        "function": ObjType(_("function"), "func", "obj", "lua", "_auto"),
        "data": ObjType(_("data"), "data", "obj", "lua", "_auto"),
        "const": ObjType(_("const"), "attr", "const", "obj", "lua", "_auto"),
        "class": ObjType(_("class"), "class", "obj", "lua", "_auto"),
        "alias": ObjType(_("alias"), "alias", "obj", "lua", "_auto"),
        "enum": ObjType(_("enum"), "enum", "obj", "lua", "_auto"),
        "method": ObjType(_("method"), "meth", "obj", "lua", "_auto"),
        "classmethod": ObjType(_("class method"), "meth", "obj", "lua", "_auto"),
        "staticmethod": ObjType(_("static method"), "meth", "obj", "lua", "_auto"),
        "attribute": ObjType(_("attribute"), "attr", "obj", "lua", "_auto"),
        "table": ObjType(_("data"), "attr", "data", "obj", "lua", "_auto"),
        "module": ObjType(_("module"), "mod", "obj", "lua", "_auto"),
    }

    directives = {
        "function": LuaFunction,
        "data": LuaData,
        "const": LuaData,
        "class": LuaClass,
        "alias": LuaAlias,
        "enum": LuaAlias,
        "method": LuaFunction,
        "classmethod": LuaFunction,
        "staticmethod": LuaFunction,
        "attribute": LuaData,
        "table": LuaTable,
        "module": LuaModule,
        "currentmodule": LuaCurrentModule,
    }
    roles = {
        "func": LuaXRefRole(),
        "data": LuaXRefRole(),
        "const": LuaXRefRole(),
        "class": LuaXRefRole(),
        "alias": LuaXRefRole(),
        "enum": LuaXRefRole(),
        "meth": LuaXRefRole(),
        "attr": LuaXRefRole(),
        "mod": LuaXRefRole(),
        "obj": LuaXRefRole(),
        "lua": LuaXRefRole(),
        "_auto": LuaXRefRole(),
    }

    @dataclass(slots=True)
    class ObjectEntry:
        docname: str
        objtype: str
        deprecated: bool
        id: str
        synopsis: str | None

    @dataclass(slots=True)
    class Entry:
        docname: str
        fullname: str

    @dataclass(slots=True)
    class GlobalEntry:
        docname: str
        entries: list["LuaDomain.Entry"]

    @dataclass(slots=True)
    class MemberEntry:
        docname: str
        entries: list["LuaDomain.Entry"]
        bases: list[str]
        base_lookup_modname: str | None = None
        base_lookup_classname: str | None = None
        base_lookup_using: list[str] | None = None

    initial_data: dict[str, dict[str, tuple[Any]]] = {
        "objects": {},  # fullname -> ObjectEntry
        "globals": {},  # modname -> GlobalEntry
        "members": {},  # modname -> MemberEntry
    }

    @property
    def config(self) -> sphinx_lua_ls.config.LuaDomainConfig:
        return self.data["config"]

    @config.setter
    def config(self, config: sphinx_lua_ls.config.LuaDomainConfig):
        self.data["config"] = config

    @property
    def objtree(self) -> sphinx_lua_ls.objtree.Object:
        return self.data["objtree"]

    @objtree.setter
    def objtree(self, objtree: sphinx_lua_ls.objtree.Object):
        self.data["objtree"] = objtree

    @property
    def objects(self) -> dict[str, "LuaDomain.ObjectEntry"]:
        return self.data["objects"]

    @property
    def globals(self) -> dict[str, "LuaDomain.GlobalEntry"]:
        return self.data["globals"]

    @property
    def members(self) -> dict[str, "LuaDomain.MemberEntry"]:
        return self.data["members"]

    def clear_doc(self, docname: str) -> None:
        for fullname, data in list(self.objects.items()):
            if data.docname == docname:
                del self.objects[fullname]

        for modname, data in list(self.globals.items()):
            if data.docname == docname:
                del self.globals[modname]
            else:
                self.globals[modname] = self.GlobalEntry(
                    docname=data.docname,
                    entries=[g for g in data.entries if g.docname != docname],
                )

        for modname, data in list(self.members.items()):
            if data.docname == docname:
                del self.members[modname]
            else:
                self.members[modname] = self.MemberEntry(
                    docname=data.docname,
                    entries=[g for g in data.entries if g.docname != docname],
                    bases=data.bases,
                    base_lookup_modname=data.base_lookup_modname,
                    base_lookup_classname=data.base_lookup_classname,
                    base_lookup_using=data.base_lookup_using,
                )

    def merge_domaindata(self, docnames: Set[str], otherdata: dict[Any, Any]) -> None:
        other_objects: dict[str, LuaDomain.ObjectEntry] = otherdata["objects"]
        for fullname, data in other_objects.items():
            if data.docname in docnames:
                if fullname in self.objects:
                    logger.warning(
                        "duplicate description for object %s found in files %s and %s",
                        fullname,
                        self.env.doc2path(data.docname),
                        self.env.doc2path(self.objects[fullname].docname),
                    )
                self.objects[fullname] = data

        other_globals: dict[str, LuaDomain.GlobalEntry] = otherdata["globals"]
        for modname, data in other_globals.items():
            if data.docname not in docnames:
                continue
            if modname not in self.globals:
                self.globals[modname] = self.GlobalEntry(
                    docname=data.docname,
                    entries=[g for g in data.entries if g.docname in docnames],
                )
            else:
                self.globals[modname].entries.extend(
                    g for g in data.entries if g.docname in docnames
                )

        other_members: dict[str, LuaDomain.MemberEntry] = otherdata["members"]
        for modname, data in other_members.items():
            if data.docname not in docnames:
                continue
            if modname not in self.members:
                self.members[modname] = self.MemberEntry(
                    docname=data.docname,
                    entries=[g for g in data.entries if g.docname in docnames],
                    bases=data.bases,
                    base_lookup_modname=data.base_lookup_modname,
                    base_lookup_classname=data.base_lookup_classname,
                    base_lookup_using=data.base_lookup_using,
                )
            else:
                self.members[modname].entries.extend(
                    g for g in data.entries if g.docname in docnames
                )

    def _find_obj(
        self,
        modname: str,
        classname: str,
        name: str,
        typ: str | None,
        using: list[str] | None,
    ) -> tuple[str, "LuaDomain.ObjectEntry"] | None:
        if name[-2:] == "()":
            name = name[:-2]

        name = utils.normalize_name(name.strip())

        if not name:
            return None

        objects = self.objects

        if typ == "mod":
            candidates = [[name]]
        else:
            candidates = [
                [modname, classname, name],
                [modname, name],
                *([used_modname, name] for used_modname in using or []),
                [name],
            ]

        for candidate in candidates:
            path = ".".join(filter(None, candidate))
            if path in objects:
                return path, objects[path]

        return None

    def resolve_xref(
        self,
        env: BuildEnvironment,
        fromdocname: str,
        builder: Builder,
        typ: str,
        target: str,
        node: addnodes.pending_xref,
        contnode: nodes.Node,
    ) -> nodes.reference | None:
        modname = node.get("lua:module")
        classname = node.get("lua:class")
        using = node.get("lua:using")
        if match := self._find_obj(modname, classname, target, typ, using):
            name, data = match
            allowed_typs = self.object_types[data.objtype].roles
            if typ != "any" and typ not in allowed_typs:
                logger.warning(
                    "reference :lua:%s:`%s` resolved to an object of unexpected type %r",
                    typ,
                    target,
                    data.objtype,
                    type="lua-ls",
                    location=(node.source, node.line),
                )
            if (
                isinstance(contnode, nodes.literal)
                and not node.get("refexplicit", False)
                and len(contnode.children) == 1
                and isinstance(contnode.children[0], nodes.Text)
            ):
                title = contnode.astext()
                new_title = utils.make_ref_title(title, data.objtype, env.config)
                if new_title != title:
                    contnode = contnode.deepcopy()
                    contnode.clear()
                    contnode += nodes.Text(new_title)
            if isinstance(contnode, nodes.Element) and data.deprecated:
                contnode["classes"] += ["deprecated", "lua-deprecated"]
            return make_refnode(
                builder,
                fromdocname,
                data.docname,
                data.id,
                contnode,
                name,
            )

    def resolve_any_xref(
        self,
        env: BuildEnvironment,
        fromdocname: str,
        builder: Builder,
        target: str,
        node: addnodes.pending_xref,
        contnode: nodes.Node,
    ) -> list[tuple[str, nodes.reference]]:
        modname = node.get("lua:module")
        classname = node.get("lua:class")
        using = node.get("lua:using")
        if match := self._find_obj(modname, classname, target, None, using):
            name, data = match
            role = "lua:" + (self.role_for_objtype(data.objtype, None) or "obj")
            return [
                (
                    role,
                    make_refnode(
                        builder,
                        fromdocname,
                        data.docname,
                        data.id,
                        contnode,
                        name,
                    ),
                )
            ]

        return []

    def get_objects(self) -> Iterator[tuple[str, str, str, str, str, int]]:
        for refname, data in self.objects.items():
            yield (refname, refname, data.objtype, data.docname, refname, 1)

    def get_full_qualified_name(self, node: nodes.Element) -> str | None:
        modname = node.get("lua:module")
        classname = node.get("lua:class")
        target = node.get("reftarget")
        if target is None:
            return None
        else:
            return ".".join(filter(None, [modname, classname, target]))


def setup(app):
    app.add_domain(LuaDomain)

    return {
        "version": "builtin",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
