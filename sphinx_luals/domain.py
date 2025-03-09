"""
Lua domain.

This code is based on ``sphinxcontrib.luadomain`` by Eliott Dumeix.

See the original code here: https://github.com/boolangery/sphinx-luadomain

"""

import functools
import re
from collections.abc import Set
from typing import Any, Callable, ClassVar, Generic, Iterable, Iterator, TypeVar

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.parsers.rst.states import Inliner
from sphinx import addnodes
from sphinx.builders import Builder
from sphinx.directives import ObjectDescription
from sphinx.domains import Domain, Index, IndexEntry, ObjType
from sphinx.environment import BuildEnvironment
from sphinx.locale import get_translation
from sphinx.roles import XRefRole
from sphinx.util import logging
from sphinx.util.docfields import TypedField
from sphinx.util.docutils import SphinxDirective
from sphinx.util.nodes import make_refnode

T = TypeVar("T")

MESSAGE_CATALOG_NAME = "sphinx-luals"
_ = get_translation(MESSAGE_CATALOG_NAME)


logger = logging.getLogger("sphinx_luals")


#: Regexp for parsing a single Lua identifier.
_OBJECT_NAME_RE = re.compile(r"^\s*[\w-]+(\s*\.\s*[\w-]+)*\s*")

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


def _separate_paren_prefix(sig: str) -> tuple[str, str]:
    """
    If string starts with a brace sequence, separate it out from the string.

    """

    if not sig.startswith("("):
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
        elif depth == 0 and c == ")":
            return sig[:i].strip(), sig[i + 1 :].strip()
        elif c in ")]}>":
            depth = max(depth - 1, 0)
        elif c in "'\"`":
            in_str = True
            str_c = c

    return sig.strip(), ""


def _separate_sig(sig: str, sep: str = ",", strip: bool = True) -> list[str]:
    """
    Separate a string by comas, ignoring comas within parens and string literals.

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
    Parse sequence of type annotations separated by comas.

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


def _type_to_nodes(typ: str, inliner) -> list[nodes.Node]:
    """
    Loosely parse a type definition, and return a list of nodes and xrefs.

    :param typ:
        string with lua type declaration.
    :param inliner:
        inliner for xrefs (available in directives as ``self.state.inliner``).

    """

    res = []

    for match in re.finditer(
        r"""
            # Skip spaces, they're not meaningful in this context.
            \s+
            |
            (?P<dots>[.]{3})
            |
            # Literal string with escapes.
            # Example: `"foo"`, `"foo-\"-bar"`.
            (?P<string>(?P<string_q>['"`])(?:\\.|[^\\])*(?P=string_q))
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
        typ,
        re.VERBOSE,
    ):
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


class LuaObject(ObjectDescription[tuple[str, str, str, str]], Generic[T]):
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

    option_spec: ClassVar[dict[str, Callable[[str], Any]]] = {
        "no-index": directives.flag,
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

    def run(self) -> list[nodes.Node]:
        for name, option in self.env.config["luals_default_options"].items():
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

        modname = self.options.get("module", self.env.ref_context.get("lua:module"))
        classname = self.env.ref_context.get("lua:class", None)
        fullname = ".".join(filter(None, [modname, classname, name]))

        # Only display full path if we're not inside of a class.
        prefix = "" if classname else ".".join(filter(None, [modname, classname]))
        if prefix:
            prefix += ":" if self.use_semicolon_path() else "."

        signode["module"] = modname
        signode["class"] = classname
        signode["fullname"] = fullname

        sig_prefix = self.get_signature_prefix(sig)
        if sig_prefix:
            signode += addnodes.desc_annotation("", "", *sig_prefix)

        if prefix:
            signode += addnodes.desc_addname(prefix, prefix)
        signode += addnodes.desc_name(name, name)

        return fullname, modname, classname, name, sigdata

    def get_signature_prefix(self, signature: str) -> list[nodes.Node]:
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
        anchor = "lua:" + fullname
        if anchor not in self.state.document.ids:
            signode["names"].append(anchor)
            signode["ids"].append(anchor)
            signode["first"] = not self.names
            self.state.document.note_explicit_target(signode)
            objects = self.env.domaindata["lua"]["objects"]
            if fullname in objects:
                self.state_machine.reporter.warning(
                    "duplicate object description of %s, " % fullname
                    + "other instance in "
                    + self.env.doc2path(objects[fullname][0])
                    + ", use :no-index: for one of them",
                    line=self.lineno,
                )
            objects[fullname] = (self.env.docname, self.objtype)

        indextext = self.get_index_text(fullname, modname, classname, objname)
        if indextext:
            self.indexnode["entries"].append(("single", indextext, anchor, "", None))

    def before_content(self) -> None:
        if self.names and self.allow_nesting:
            _, _, classname, name = self.names[-1]
            # Add name of the current object to the current classname,
            # thus getting a new classname.
            new_classname = ".".join(filter(None, [classname, name]))
            classes = self.env.ref_context.setdefault("lua:classes", [])
            classes.append(self.env.ref_context.get("lua:class"))
            self.env.ref_context["lua:class"] = new_classname

        if "module" in self.options:
            modules = self.env.ref_context.setdefault("lua:modules", [])
            modules.append(self.env.ref_context.get("lua:module"))
            self.env.ref_context["lua:module"] = self.options["module"]

    def after_content(self) -> None:
        if self.names and self.allow_nesting:
            classes = self.env.ref_context.setdefault("lua:classes", [])
            self.env.ref_context["lua:class"] = classes.pop() if classes else None

        if "module" in self.options:
            modules = self.env.ref_context.setdefault("lua:modules", [])
            self.env.ref_context["lua:module"] = modules.pop() if modules else None


class LuaFunction(LuaObject[tuple[list[tuple[str, str]], list[tuple[str, str]]]]):
    """
    Everything that looks like a function: functions, methods, static and class methods.

    I.e. everything with signature ``name(params) -> returns``.

    """

    def parse_signature(self, sig):
        if match := _OBJECT_NAME_RE.match(sig):
            name = re.sub(r"\s", "", match.group())
            sig = sig[match.span()[1] :]
        else:
            raise ValueError("Incorrect function name")

        params, returns = _separate_paren_prefix(sig)

        if returns and returns.startswith("->"):
            returns = returns[2:].lstrip()
        elif returns:
            raise ValueError("Incorrect function return type")

        if returns.startswith("(") and returns.endswith(")"):
            returns = returns[1:-1]

        return name, (
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
            (args, returns),
        ) = self.handle_signature_prefix(sig, signode)

        if not args:
            if self.needs_arg_list():
                signode += addnodes.desc_parameterlist()
        else:
            parameterslist = addnodes.desc_parameterlist()
            signode += parameterslist
            for arg, typ in args:
                if arg and typ and typ.endswith("?"):
                    arg, typ = arg + "?", typ[:-1]
                    if typ.startswith("(") and typ.endswith(")"):
                        typ = typ[1:-1]

                parameter = addnodes.desc_parameter()

                parameter += addnodes.desc_sig_name(arg, arg)
                if typ:
                    parameter += addnodes.desc_sig_punctuation(":", ":")
                    parameter += addnodes.desc_sig_space()
                    parameter += _type_to_nodes(typ, self.state.inliner)

                parameterslist += parameter

        if returns:
            retnode = addnodes.desc_returns()
            signode += retnode

            for i, (arg, typ) in enumerate(returns):
                if arg and typ and typ.endswith("?"):
                    arg, typ = arg + "?", typ[:-1]
                    if typ.startswith("(") and typ.endswith(")"):
                        typ = typ[1:-1]

                if arg:
                    retnode += addnodes.desc_sig_name("", arg or "_")
                    retnode += addnodes.desc_sig_punctuation(":", ":")
                    retnode += addnodes.desc_sig_space()
                retnode += _type_to_nodes(typ, self.state.inliner)
                if i + 1 < len(returns):
                    retnode += addnodes.desc_sig_punctuation(",", ",")
                    retnode += addnodes.desc_sig_space()

        return fullname, modname, classname, name

    def needs_arg_list(self) -> bool:
        return True

    def use_semicolon_path(self) -> bool:
        return self.objtype in ("method", "classmethod")

    def get_signature_prefix(self, signature: str) -> list[nodes.Node]:
        prefix = super().get_signature_prefix(signature)
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
        if match := _OBJECT_NAME_RE.match(sig):
            name = re.sub(r"\s", "", match.group())
            sig = sig[match.span()[1] :]
        else:
            raise ValueError("Incorrect data name")

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

        if typ:
            signode += addnodes.desc_sig_punctuation(":", ":")
            signode += addnodes.desc_sig_space()
            signode += addnodes.desc_type(
                "", "", *_type_to_nodes(typ, self.state.inliner)
            )

        return fullname, modname, classname, name

    def get_signature_prefix(self, signature: str) -> list[nodes.Node]:
        prefix = super().get_signature_prefix(signature)
        if self.objtype not in ("data", "attribute"):
            prefix.extend(
                [
                    addnodes.desc_sig_keyword("", self.objtype),
                    addnodes.desc_sig_space(),
                ]
            )
        return prefix


class LuaAlias(LuaObject[str]):
    """
    Type aliases and other things that have type assignments in their signature.

    I.e. everything with signature ``name type``.

    """

    allow_nesting = True

    def parse_signature(self, sig):
        if match := _OBJECT_NAME_RE.match(sig):
            name = re.sub(r"\s", "", match.group())
            sig = sig[match.span()[1] :]
        else:
            raise ValueError("Incorrect alias name")

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

        if typ:
            signode += addnodes.desc_sig_space()
            signode += addnodes.desc_sig_punctuation("=", "=")
            signode += addnodes.desc_sig_space()
            signode += addnodes.desc_type(
                "", "", *_type_to_nodes(typ, self.state.inliner)
            )

        return fullname, modname, classname, name

    def get_signature_prefix(self, signature: str) -> list[nodes.Node]:
        prefix = super().get_signature_prefix(signature)
        prefix.extend(
            [
                addnodes.desc_sig_keyword("", self.objtype),
                addnodes.desc_sig_space(),
            ]
        )
        return prefix


class LuaClass(LuaObject[list[str]]):
    """
    Classes and other things that have base types in their signature.

    I.e. everything with signature ``name: base1, base2, ...``.

    These are nested.

    """

    allow_nesting = True

    def parse_signature(self, sig):
        if match := _OBJECT_NAME_RE.match(sig):
            name = re.sub(r"\s", "", match.group())
            sig = sig[match.span()[1] :]
        else:
            raise ValueError("Incorrect data name")

        if sig.startswith("=") or sig.startswith(":"):
            sig = sig[1:]

        return name, _separate_sig(sig)

    @_handle_signature_errors
    def handle_signature(
        self, sig: str, signode: addnodes.desc_signature
    ) -> tuple[str, str, str, str]:
        fullname, modname, classname, name, bases = self.handle_signature_prefix(
            sig, signode
        )

        if bases:
            signode += addnodes.desc_sig_space()
            signode += addnodes.desc_sig_punctuation(":", ":")
            signode += addnodes.desc_sig_space()

            sep = False
            for typ in bases:
                if sep:
                    signode += addnodes.desc_sig_punctuation(",", ",")
                    signode += addnodes.desc_sig_space()
                signode += addnodes.desc_type(
                    "", "", *_type_to_nodes(typ, self.state.inliner)
                )
                sep = True

        return fullname, modname, classname, name

    def get_signature_prefix(self, signature: str) -> list[nodes.Node]:
        prefix = super().get_signature_prefix(signature)
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
        "platform": lambda x: x,
        "synopsis": lambda x: x,
        "no-index": directives.flag,
        "deprecated": directives.flag,
    }

    def run(self) -> list[nodes.Node]:
        for name, option in self.env.config["luals_default_options"].items():
            if name not in self.options:
                self.options[name] = option

        sig = self.arguments[0]
        if match := _OBJECT_NAME_RE.match(sig):
            modname = re.sub(r"\s", "", match.group())
            sig = sig[match.span()[1] :]
            if sig:
                raise ValueError("Unexpected symbols after module name")
        else:
            raise ValueError("Incorrect module name")

        env = self.state.document.settings.env
        no_index = "no-index" in self.options
        env.ref_context["lua:module"] = modname
        ret = []
        if not no_index:
            env.domaindata["lua"]["modules"][modname] = (
                env.docname,
                self.options.get("synopsis", ""),
                self.options.get("platform", ""),
                "deprecated" in self.options,
            )
            # make a duplicate entry in 'objects' to facilitate searching for
            # the module in LuaDomain.find_obj()
            env.domaindata["lua"]["objects"][modname] = (env.docname, "module")
            target_node = nodes.target("", "", ids=["lua:" + modname], ismod=True)
            self.state.document.note_explicit_target(target_node)
            # the platform and synopsis aren't printed; in fact, they are only
            # used in the modindex currently
            ret.append(target_node)
            indextext = _("%s (module)") % modname
            inode = addnodes.index(
                entries=[("single", indextext, "lua:" + modname, "", None)]
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
        sig = self.arguments[0]
        if match := _OBJECT_NAME_RE.match(sig):
            modname = re.sub(r"\s", "", match.group())
            sig = sig[match.span()[1] :]
            if sig:
                raise ValueError("Unexpected symbols after module name")
        else:
            raise ValueError("Incorrect module name")

        env = self.state.document.settings.env
        if modname == "None":
            env.ref_context.pop("lua:module", None)
        else:
            env.ref_context["lua:module"] = modname
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


class LuaModuleIndex(Index):
    """
    Index subclass to provide the Lua module index.
    """

    name = "modindex"
    localname = _("Lua Module Index")
    shortname = _("modules")

    def generate(
        self, docnames: Iterable[str] | None = None
    ) -> tuple[list[tuple[str, list[IndexEntry]]], bool]:
        content: dict[str, list[IndexEntry]] = {}
        # list of prefixes to ignore
        ignores = self.domain.env.config["modindex_common_prefix"]
        ignores = sorted(ignores, key=len, reverse=True)
        # list of all modules, sorted by module name
        modules: list[tuple[str, tuple[str, str, str, bool]]] = sorted(
            self.domain.data["modules"].items(), key=lambda x: x[0].lower()
        )
        # sort out collapsable modules
        prev_modname = ""
        num_top_levels = 0
        for modname, (docname, synopsis, platforms, deprecated) in modules:
            if docnames and docname not in docnames:
                continue
            if not modname:
                continue

            for ignore in ignores:
                if modname.startswith(ignore):
                    modname = modname[len(ignore) :]
                    stripped = ignore
                    break
            else:
                stripped = ""

            # we stripped the whole module name?
            if not modname:
                modname, stripped = stripped, ""

            entries = content.setdefault(modname[0].lower(), [])

            package = modname.split(".")[0]
            if package != modname:
                # it's a submodule
                if prev_modname == package:
                    # first submodule - make parent a group head
                    if entries:
                        name, _subtype, *rest = entries[-1]
                        entries[-1] = IndexEntry(name, 1, *rest)
                elif not prev_modname.startswith(package):
                    # submodule without parent in list, add dummy entry
                    entries.append(
                        IndexEntry(stripped + package, 1, "", "", "", "", "")
                    )
                subtype = 2
            else:
                num_top_levels += 1
                subtype = 0

            qualifier = deprecated and _("Deprecated") or ""
            entries.append(
                IndexEntry(
                    stripped + modname,
                    subtype,
                    docname,
                    "lua:" + stripped + modname,
                    platforms,
                    qualifier,
                    synopsis,
                )
            )
            prev_modname = modname

        # apply heuristics when to collapse modindex at page load:
        # only collapse if number of toplevel modules is larger than
        # number of submodules
        collapse = len(modules) - num_top_levels < num_top_levels

        # sort by first letter
        sorted_content = sorted(content.items())

        return sorted_content, collapse


class LuaDomain(Domain):
    """Lua language domain."""

    name = "lua"
    label = "Lua"
    object_types: dict[str, ObjType] = {
        "function": ObjType(_("function"), "func", "obj"),
        "data": ObjType(_("data"), "data", "obj"),
        "const": ObjType(_("const"), "const", "obj"),
        "class": ObjType(_("class"), "class", "obj"),
        "alias": ObjType(_("alias"), "alias", "obj"),
        "method": ObjType(_("method"), "meth", "obj"),
        "classmethod": ObjType(_("class method"), "meth", "obj"),
        "staticmethod": ObjType(_("static method"), "meth", "obj"),
        "attribute": ObjType(_("attribute"), "attr", "obj"),
        "module": ObjType(_("module"), "mod", "obj"),
    }

    directives = {
        "function": LuaFunction,
        "data": LuaData,
        "const": LuaData,
        "class": LuaClass,
        "alias": LuaAlias,
        "method": LuaFunction,
        "classmethod": LuaFunction,
        "staticmethod": LuaFunction,
        "attribute": LuaData,
        "module": LuaModule,
        "currentmodule": LuaCurrentModule,
    }
    roles = {
        "func": LuaXRefRole(),
        "data": LuaXRefRole(),
        "const": LuaXRefRole(),
        "class": LuaXRefRole(),
        "alias": LuaXRefRole(),
        "meth": LuaXRefRole(),
        "attr": LuaXRefRole(),
        "mod": LuaXRefRole(),
        "obj": LuaXRefRole(),
    }
    initial_data: dict[str, dict[str, tuple[Any]]] = {
        "objects": {},  # fullname -> docname, objtype
        "modules": {},  # modname -> docname, synopsis, platform, deprecated
    }
    indices = [
        LuaModuleIndex,
    ]

    def clear_doc(self, docname: str) -> None:
        for fullname, (fn, _l) in list(self.data["objects"].items()):
            if fn == docname:
                del self.data["objects"][fullname]
        for modname, (fn, _x, _x, _x) in list(self.data["modules"].items()):
            if fn == docname:
                del self.data["modules"][modname]

    def merge_domaindata(self, docnames: Set[str], otherdata: dict[Any, Any]) -> None:
        # XXX check duplicates?
        for fullname, (fn, objtype) in otherdata["objects"].items():
            if fn in docnames:
                self.data["objects"][fullname] = (fn, objtype)
        for modname, data in otherdata["modules"].items():
            if data[0] in docnames:
                self.data["modules"][modname] = data

    def _find_obj(
        self, modname: str, classname: str, name: str, typ: str | None
    ) -> tuple[str, Any] | None:
        if name[-2:] == "()":
            name = name[:-2]

        if not name:
            return None

        objects = self.data["objects"]

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
            name, (docname, objtype) = match
            if typ not in ("any", "obj") and typ not in objtype:
                logger.warning(
                    "reference :lua:%s:`%s` resolved to an object of unexpected type %r",
                    typ,
                    target,
                    objtype,
                    type="lua-ls",
                    location=(node.source, node.line),
                )
            if (
                isinstance(contnode, nodes.literal)
                and not node["refexplicit"]
                and len(contnode.children) == 1
                and isinstance(contnode.children[0], nodes.Text)
            ):
                title = contnode.astext()
                new_title = title
                if objtype in (
                    "function",
                    "method",
                    "classmethod",
                    "staticmethod",
                ) and not new_title.endswith("()"):
                    new_title += "()"
                if objtype in ("method", "classmethod"):
                    i = new_title.rfind(".")
                    if i != -1:
                        new_title = new_title[:i] + ":" + new_title[i + 1 :]
                if new_title != title:
                    contnode = contnode.deepcopy()
                    contnode.clear()
                    contnode += nodes.Text(new_title)
            return make_refnode(
                builder, fromdocname, docname, "lua:" + name, contnode, name
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
            name, (docname, objtype) = match
            role = "lua:" + (self.role_for_objtype(objtype, None) or "obj")
            return [
                (
                    role,
                    make_refnode(
                        builder, fromdocname, docname, "lua:" + name, contnode, name
                    ),
                )
            ]

        return []

    def get_objects(self) -> Iterator[tuple[str, str, str, str, str, int]]:
        for modname, info in self.data["modules"].items():
            yield (modname, modname, "module", info[0], "lua:" + modname, 0)
        for refname, (docname, type) in self.data["objects"].items():
            if type != "module":  # modules are already handled
                yield (refname, refname, type, docname, refname, 1)

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
