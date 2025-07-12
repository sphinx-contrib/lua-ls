"""
Lua domain.

This code is based on ``sphinxcontrib.luadomain`` by Eliott Dumeix.

See the original code here: https://github.com/boolangery/sphinx-luadomain

"""

import dataclasses
import functools
import re
import urllib.parse
from collections.abc import Set
from dataclasses import dataclass
from typing import Any, Callable, ClassVar, Generic, Iterator, TypeVar

import sphinx.config
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
from sphinx.util.nodes import make_refnode

T = TypeVar("T")

MESSAGE_CATALOG_NAME = "sphinx-lua-ls"
_ = get_translation(MESSAGE_CATALOG_NAME)


logger = logging.getLogger("sphinx_lua_ls")


#: Regexp for parsing a single Lua identifier.
_OBJECT_NAME_RE = re.compile(r"^\s*(?P<name>[\w-]+)")

#: A single function parameter name.
_PARAM_NAME_RE = re.compile(r"^\s*[\w-]+\s*$")


def _handle_signature_errors(handler):
    @functools.wraps(handler)
    def fn(self, sig: str, signode: addnodes.desc_signature):
        try:
            return handler(self, sig, signode)
        except ValueError as e:
            logger.warning(
                "incorrect %s signature %r: %s",
                self.objtype,
                sig,
                e,
                type="lua-ls",
                location=(signode.source, signode.line),
            )
            raise

    return fn


def _separate_name_prefix(sig: str) -> tuple[str, str]:
    name_components = []
    sig = sig.lstrip()
    while sig:
        seen_dot_prefix = False
        if name_components and sig.startswith("."):
            sig = sig[1:]
            seen_dot_prefix = True
        if sig.startswith("["):
            name, sig = _separate_paren_prefix(sig, ("[", "]"))
            name_components.append(f"[{_normalize_type(name)}]")
        elif match := _OBJECT_NAME_RE.match(sig):
            name_components.append(match.group("name"))
            sig = sig[match.span()[1] :]
        else:
            if seen_dot_prefix:
                raise ValueError("incorrect object name")
            break
    if not name_components:
        raise ValueError("incorrect object name")
    return ".".join(name_components), sig


def _make_ref_title(fullname: str, objtype: str, config: sphinx.config.Config):
    if "[" in fullname:
        components = [
            "[" + _normalize_type(c[1:-1]) + "]"
            if c.startswith("[") and c.endswith("]")
            else c
            for c in _separate_sig(fullname, ".")
        ]

        if objtype in ("method", "classmethod"):
            fullname = ".".join(components[:-1])
            if fullname:
                fullname += ":"
            fullname += components[-1]
        else:
            fullname = ".".join(components)
    elif objtype in ("method", "classmethod") and ":" not in fullname:
        i = fullname.rfind(".")
        if i != -1:
            fullname = fullname[:i] + ":" + fullname[i + 1 :]

    if (
        config.add_function_parentheses
        and objtype
        in (
            "function",
            "method",
            "classmethod",
            "staticmethod",
        )
        and not fullname.endswith("()")
    ):
        fullname += "()"

    return fullname


def _separate_paren_prefix(
    sig: str, parens: tuple[str, str] = ("(", ")")
) -> tuple[str, str]:
    """
    If string starts with a brace sequence, separate it out from the string.

    """

    if not sig.startswith(parens[0]):
        return "", sig.strip()
    else:
        sig = sig[1:]

    depth = 0
    in_str = False
    str_c = ""
    esc = False
    for i, c in enumerate(sig):
        if in_str:
            if esc:
                esc = False
            elif c == str_c:
                in_str = False
            elif c == "\\":
                esc = True
        elif c in "([{<":
            depth += 1
        elif depth == 0 and c == parens[1]:
            return sig[:i].strip(), sig[i + 1 :].strip()
        elif c in ")]}>":
            depth = max(depth - 1, 0)
        elif c in "'\"`":
            in_str = True
            str_c = c

    return sig.strip(), ""


def _separate_sig(sig: str, sep: str = ",", strip: bool = True) -> list[str]:
    """
    Separate a string by commas, ignoring commas within parens and string literals.

    """

    assert len(sep) == 1

    res = []

    pos = 0
    depth = 0
    in_str = False
    str_c = ""
    esc = False
    for i, c in enumerate(sig):
        if in_str:
            if esc:
                esc = False
            elif c == str_c:
                in_str = False
            elif c == "\\":
                esc = True
        elif c in "([{<":
            depth += 1
        elif c in ")]}>":
            depth = max(depth - 1, 0)
        elif c in "'\"`":
            in_str = True
            str_c = c
        elif depth == 0 and c == sep:
            elem = sig[pos:i]
            if strip:
                elem = elem.strip()
            if elem and not elem.isspace():
                res.append(elem)
            pos = i + 1

    if pos < len(sig):
        elem = sig[pos:]
        if strip:
            elem = elem.strip()
        if elem and not elem.isspace():
            res.append(elem)

    return res


def _parse_types(
    sig: str, parsingFunctionParams: bool = False
) -> list[tuple[str, str]]:
    """
    Parse sequence of type annotations separated by commas.

    Each type annotation might consist of a single type or a name-type pair.

    """

    res = []
    for elem in _separate_sig(sig):
        elems = _separate_sig(elem, ":", strip=False)
        if not elems:
            continue
        elif (
            len(elems) == 1 and not parsingFunctionParams
        ) or not _PARAM_NAME_RE.match(elems[0]):
            # A single type annotation.
            res.append(("", ":".join(elems).strip()))
        else:
            # A name and a type annotation.
            res.append((elems[0].strip(), ":".join(elems[1:]).strip()))
    return res


_TYPE_PARSE_RE = re.compile(
    r"""
    # Skip spaces, they're not meaningful in this context.
    \s+
    |
    (?P<dots>[.]{3})
    |
    # Literal string with escapes.
    # Example: `"foo"`, `"foo-\"-bar"`.
    (?P<string>(?P<string_q>['"`])(?:\\.|[^\\])*?(?P=string_q))
    |
    # Number with optional exponent.
    # Example: `1.0`, `.1`, `1.`, `1e+5`.
    (?P<number>(?:\d+(?:\.\d*)|\.\d+)(?:[eE][+-]?\d+)?)
    |
    # Function type followed by an opening brace.
    # Example: `fun( ...`.
    (?P<kwd>fun)\s*(?=\()
    |
    # Ident not followed by an open brace, semicolon, etc.
    # Example: `module.Type`.
    # Doesn't match: `name?: ...`, `name( ...`, etc.
    (?P<ident>[\w-]+(?:\.[\w-]+)*)
    \s*(?P<ident_qm>\??)\s*
    (?![:(\w.?-])
    |
    # Built-in type not followed by an open brace, semicolon, etc.
    # Example: `string`, `string?`.
    # Doesn't match: `string?: ...`, `string( ...`, etc.
    (?P<type>nil|any|boolean|string|number|integer|function|table|thread|userdata|lightuserdata)
    \s*(?P<type_qm>\??)\s*
    (?![:(\w.?-])
    |
    # Name component, only matches when `ident` and `type` didn't match.
    # Example: `string: ...`.
    (?P<name>[\w.-]+)
    |
    # Punctuation that we separate with spaces.
    (?P<punct>[=:,|])
    |
    # Punctuation that we copy as-is, without adding spaces.
    (?P<other_punct>[-!"#$%&'()*+/;<>?@[\]^_`{}~]+)
    |
    # Anything else is copied as-is.
    (?P<other>.)
    """,
    re.VERBOSE,
)


def _type_to_nodes(typ: str, inliner) -> list[nodes.Node]:
    """
    Loosely parse a type definition, and return a list of nodes and xrefs.

    :param typ:
        string with lua type declaration.
    :param inliner:
        inliner for xrefs (available in directives as ``self.state.inliner``).

    """

    res = []

    for match in _TYPE_PARSE_RE.finditer(typ):
        if text := match.group("dots"):
            res.append(addnodes.desc_sig_name(text, text))
        elif text := match.group("kwd"):
            res.append(addnodes.desc_sig_keyword(text, text))
        elif text := match.group("type"):
            res.append(addnodes.desc_sig_keyword_type(text, text))
            if qm := match.group("type_qm"):
                res.append(addnodes.desc_sig_punctuation(qm, qm))
        elif text := match.group("string"):
            res.append(addnodes.desc_sig_literal_string(text, text))
        elif text := match.group("number"):
            res.append(addnodes.desc_sig_literal_number(text, text))
        elif text := match.group("ident"):
            ref_nodes, warn_nodes = LuaXRefRole()("lua:obj", text, text, 0, inliner)
            res.extend(ref_nodes)
            res.extend(warn_nodes)
            if qm := match.group("ident_qm"):
                res.append(addnodes.desc_sig_punctuation(qm, qm))
        elif text := match.group("name"):
            res.append(addnodes.desc_sig_name(text, text))
        elif text := match.group("punct"):
            if text in "=|":
                res.append(addnodes.desc_sig_space())
            res.append(addnodes.desc_sig_punctuation(text, text))
            res.append(addnodes.desc_sig_space())
        elif text := match.group("other_punct"):
            res.append(addnodes.desc_sig_punctuation(text, text))
        elif text := match.group("other"):
            res.append(nodes.Text(text))

    return res


def _normalize_type(typ: str) -> str:
    """
    Loosely parse a type definition and normalize spaces.

    :param typ:
        string with lua type declaration.

    """

    res = ""

    for match in _TYPE_PARSE_RE.finditer(typ):
        if text := match.group("dots"):
            res += text
        elif text := match.group("kwd"):
            res += text
        elif text := match.group("type"):
            res += text
            if qm := match.group("type_qm"):
                res += qm
        elif text := match.group("string"):
            res += text
        elif text := match.group("number"):
            res += text
        elif text := match.group("ident"):
            res += text
            if qm := match.group("ident_qm"):
                res += qm
        elif text := match.group("name"):
            res += text
        elif text := match.group("punct"):
            if text in "=|":
                res += " "
            res += text
            res += " "
        elif text := match.group("other_punct"):
            res += text
        elif text := match.group("other"):
            res += text

    return res


def _make_anchor(name: str) -> str:
    return f"lua-{urllib.parse.quote(name)}"


def _normalize_name(name: str) -> str:
    if "[" in name:
        return ".".join(
            [
                "[" + _normalize_type(c[1:-1]) + "]"
                if c.startswith("[") and c.endswith("]")
                else c
                for c in _separate_sig(name, ".")
            ]
        )
    else:
        return name


class _SigWriter:
    def __init__(self, signode: addnodes.desc_signature) -> None:
        self._signode = signode
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
        self._line += addnodes.desc_type("", "", *_type_to_nodes(txt, inliner))

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
        multiline = estimated_len > 50

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
        multiline = estimated_len > 50

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
                        type_body = _type_to_nodes(typename, inliner)

                    types[name] = type_body

        return super().make_field(types, domain, items, env, inliner, location)


class LuaContextManagerMixin(SphinxDirective):
    def push_context(self, modname: str, classname: str):
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
        **ObjectDescription.option_spec,
    }

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

    force_prefix_only = False

    collected_bases: list[str] | None = None

    def run(self) -> list[nodes.Node]:
        for name, option in self.env.domaindata["lua"]["config"][
            "default_options"
        ].items():
            if name not in self.options:
                self.options[name] = option
        return super().run()

    def parse_signature(self, sig: str) -> tuple[str, T]:
        raise NotImplementedError()

    def use_semicolon_path(self) -> bool:
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
        prefix = (
            ""
            if classname and not self.force_prefix_only
            else ".".join(filter(None, [modname, classname]))
        )

        descname = name
        if self.use_semicolon_path():
            if "[" in descname:
                descname_components = _separate_sig(descname, ".")
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

        if self.force_prefix_only and prefix:
            prefix_components = _separate_sig(prefix, ".")
            if len(prefix_components) > 1:
                descname = prefix_components[-1]
                prefix = prefix[: -len(descname) - 1]

        if prefix:
            signode += addnodes.desc_addname(prefix, prefix)
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
        anchor = _make_anchor(fullname)
        if anchor not in self.state.document.ids:
            signode["names"].append(anchor)
            signode["ids"].append(anchor)
            signode["first"] = not self.names
            self.state.document.note_explicit_target(signode)

            domaindata = self.env.domaindata["lua"]
            objects: dict[str, LuaDomain.ObjectEntry] = domaindata["objects"]
            globals: dict[str, LuaDomain.GlobalEntry] = domaindata["globals"]
            members: dict[str, LuaDomain.MemberEntry] = domaindata["members"]

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

            if "[" in fullname:
                name_components = _separate_sig(fullname, ".")
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
                self.indexnode["entries"].append(
                    ("single", indextext, anchor, "", None)
                )

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

        return _make_ref_title(fullname, self.objtype, self.config)

    def before_content(self) -> None:
        if self.names and self.allow_nesting:
            _, modname, classname, objname = self.names[-1]
            if self.objtype == "module" and not classname:
                modname = modname + "." if modname else ""
                modname += objname
            else:
                classname = classname + "." if classname else ""
                classname += objname

            self.push_context(modname, classname)

    def after_content(self) -> None:
        if self.names and self.allow_nesting:
            self.pop_context()


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
        name, sig = _separate_name_prefix(sig)
        generics, sig = _separate_paren_prefix(sig, ("<", ">"))
        params, returns = _separate_paren_prefix(sig)

        if returns and returns.startswith("->"):
            returns = returns[2:].lstrip()
        elif returns and returns.startswith(":"):
            returns = returns[1:].lstrip()
        elif returns:
            raise ValueError("incorrect function return type")

        if returns.startswith("(") and returns.endswith(")"):
            returns = returns[1:-1]

        return name, (
            _parse_types(generics, parsingFunctionParams=True),
            _parse_types(params, parsingFunctionParams=True),
            _parse_types(returns),
        )

    @_handle_signature_errors
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

        sw = _SigWriter(signode)

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

    def use_semicolon_path(self) -> bool:
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
        name, sig = _separate_name_prefix(sig)

        if sig.startswith("=") or sig.startswith(":"):
            sig = sig[1:]

        return name, sig.strip()

    @_handle_signature_errors
    def handle_signature(
        self, sig: str, signode: addnodes.desc_signature
    ) -> tuple[str, str, str, str]:
        fullname, modname, classname, name, typ = self.handle_signature_prefix(
            sig, signode
        )

        sw = _SigWriter(signode)

        if typ:
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
        name, sig = _separate_name_prefix(sig)

        generics, sig = _separate_paren_prefix(sig, ("<", ">"))
        if sig.startswith("=") or sig.startswith(":"):
            sig = sig[1:]

        return name, (_parse_types(generics, parsingFunctionParams=True), sig.strip())

    @_handle_signature_errors
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

        sw = _SigWriter(signode)

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
        name, sig = _separate_name_prefix(sig)

        generics, sig = _separate_paren_prefix(sig, ("<", ">"))

        if sig.startswith("("):
            # This is a constructor.

            params, returns = _separate_paren_prefix(sig)

            if returns and returns.startswith("->"):
                returns = returns[2:].lstrip()
            if returns and returns.startswith(":"):
                returns = returns[1:].lstrip()
            elif returns:
                raise ValueError("incorrect function return type")

            if returns.startswith("(") and returns.endswith(")"):
                returns = returns[1:-1]

            return name, (
                _parse_types(generics, parsingFunctionParams=True),
                None,
                _parse_types(params, parsingFunctionParams=True),
                _parse_types(returns),
            )

        if sig.startswith("=") or sig.startswith(":"):
            sig = sig[1:]

        return name, (
            _parse_types(generics, parsingFunctionParams=True),
            _separate_sig(sig),
            None,
            None,
        )

    @_handle_signature_errors
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

        sw = _SigWriter(signode)

        if generics:
            sw.params(generics, ("<", ">"), False, self.state.inliner)

        if bases:
            if self.collected_bases is None:
                self.collected_bases = []
            self.collected_bases.extend(map(_normalize_name, bases))

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
                    addnodes.desc_sig_keyword("", "constructor"),
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

        name, sig = _separate_name_prefix(sig)
        if sig:
            raise ValueError("unexpected symbols after table name")

        return name, None

    @_handle_signature_errors
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


class LuaModule(SphinxDirective):
    """
    Directive to mark description of a new module.

    """

    has_content = False
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = False
    option_spec = {
        "no-index": directives.flag,
        "deprecated": directives.flag,
        "synopsis": directives.unchanged,
    }

    def run(self) -> list[nodes.Node]:
        for name, option in self.env.domaindata["lua"]["config"][
            "default_options"
        ].items():
            if name not in self.options:
                self.options[name] = option

        if self.env.ref_context.get("lua:class", None):
            raise self.severe("lua:module only available on top level")

        sig = self.arguments[0]
        try:
            fullname, sig = _separate_name_prefix(sig)
        except ValueError as e:
            raise self.error(str(e))
        if sig:
            raise self.error("unexpected symbols after module name")

        self.env.ref_context["lua:module"] = fullname
        ret = []
        if "no-index" not in self.options:
            domaindata = self.env.domaindata["lua"]
            objects: dict[str, LuaDomain.ObjectEntry] = domaindata["objects"]
            globals: dict[str, LuaDomain.GlobalEntry] = domaindata["globals"]
            members: dict[str, LuaDomain.MemberEntry] = domaindata["members"]

            if fullname in objects and self.env.docname != objects[fullname].docname:
                self.state_machine.reporter.warning(
                    f"duplicate object description of {fullname}, "
                    "other instance in "
                    f"{self.env.doc2path(objects[fullname].docname)}, "
                    "use :no-index: for one of them",
                    line=self.lineno,
                )
            objects[fullname] = LuaDomain.ObjectEntry(
                docname=self.env.docname,
                objtype="module",
                deprecated="deprecated" in self.options,
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
                name_components = _separate_sig(fullname, ".")
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

            target_node = nodes.target("", "", ids=[_make_anchor(fullname)], ismod=True)
            self.state.document.note_explicit_target(target_node)
            # the platform and synopsis aren't printed; in fact, they are only
            # used in the modindex currently
            ret.append(target_node)
            indextext = _("%s (module)") % fullname
            inode = addnodes.index(
                entries=[("single", indextext, _make_anchor(fullname), "", None)]
            )
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
    final_argument_whitespace = False
    option_spec = {}

    def run(self) -> list[nodes.Node]:
        if self.env.ref_context.get("lua:class", None):
            raise self.severe("lua:currentmodule only available on top level")

        sig = self.arguments[0]
        try:
            modname, sig = _separate_name_prefix(sig)
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
        "function": ObjType(_("function"), "func", "obj", "lua"),
        "data": ObjType(_("data"), "data", "obj", "lua"),
        "const": ObjType(_("const"), "attr", "const", "obj", "lua"),
        "class": ObjType(_("class"), "class", "obj", "lua"),
        "alias": ObjType(_("alias"), "alias", "obj", "lua"),
        "enum": ObjType(_("enum"), "enum", "obj", "lua"),
        "method": ObjType(_("method"), "meth", "obj", "lua"),
        "classmethod": ObjType(_("class method"), "meth", "obj", "lua"),
        "staticmethod": ObjType(_("static method"), "meth", "obj", "lua"),
        "attribute": ObjType(_("attribute"), "attr", "obj", "lua"),
        "table": ObjType(_("data"), "attr", "data", "obj", "lua"),
        "module": ObjType(_("module"), "mod", "obj", "lua"),
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
    }

    @dataclass(slots=True)
    class ObjectEntry:
        docname: str
        objtype: str
        deprecated: bool
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

    initial_data: dict[str, dict[str, tuple[Any]]] = {
        "objects": {},  # fullname -> ObjectEntry
        "globals": {},  # modname -> GlobalEntry
        "members": {},  # modname -> MemberEntry
    }

    @property
    def config(self) -> dict[str, Any]:
        return self.data.setdefault("config", {})

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
                )
            else:
                self.members[modname].entries.extend(
                    g for g in data.entries if g.docname in docnames
                )

    def _find_obj(
        self, modname: str, classname: str, name: str, typ: str | None
    ) -> tuple[str, "LuaDomain.ObjectEntry"] | None:
        if name[-2:] == "()":
            name = name[:-2]

        name = _normalize_name(name.strip())

        if not name:
            return None

        objects = self.objects

        if typ == "mod":
            candidates = [[name]]
        else:
            candidates = [
                [modname, classname, name],
                [modname, name],
                [name],
            ]

            if typ in ("func", "meth") and "." not in name:
                candidates.append(["object", name])

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
        if match := self._find_obj(modname, classname, target, typ):
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
                new_title = _make_ref_title(title, data.objtype, env.config)
                if new_title != title:
                    contnode = contnode.deepcopy()
                    contnode.clear()
                    contnode += nodes.Text(new_title)
            if isinstance(contnode, nodes.Element) and data.deprecated:
                contnode["classes"] += ["deprecated", "lua-deprecated"]
            return make_refnode(
                builder, fromdocname, data.docname, _make_anchor(name), contnode, name
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
        if match := self._find_obj(modname, classname, target, None):
            name, data = match
            role = "lua:" + (self.role_for_objtype(data.objtype, None) or "obj")
            return [
                (
                    role,
                    make_refnode(
                        builder,
                        fromdocname,
                        data.docname,
                        _make_anchor(name),
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
