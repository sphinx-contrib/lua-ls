import functools
import re
import urllib.parse

import sphinx.config
from docutils import nodes
from sphinx import addnodes
from sphinx.util import logging

logger = logging.getLogger("sphinx_lua_ls")


#: Regexp for parsing a single Lua identifier.
_OBJECT_NAME_RE = re.compile(r"^\s*(?P<name>[\w-]+)")

#: A single function parameter name.
_PARAM_NAME_RE = re.compile(r"^\s*[\w-]+\s*$")


def handle_signature_errors(handler):
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


def separate_name_prefix(sig: str) -> tuple[str, str]:
    name_components = []
    sig = sig.lstrip()
    while sig:
        seen_dot_prefix = False
        if name_components and sig.startswith("."):
            sig = sig[1:]
            seen_dot_prefix = True
        if sig.startswith("["):
            name, sig = separate_paren_prefix(sig, ("[", "]"))
            name_components.append(f"[{normalize_type(name)}]")
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


def make_ref_title(fullname: str, objtype: str, config: sphinx.config.Config):
    if "[" in fullname:
        components = [
            "[" + normalize_type(c[1:-1]) + "]"
            if c.startswith("[") and c.endswith("]")
            else c
            for c in separate_sig(fullname, ".")
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


def separate_paren_prefix(
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


def separate_sig(sig: str, sep: str = ",", strip: bool = True) -> list[str]:
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


def parse_types(sig: str, parsingFunctionParams: bool = False) -> list[tuple[str, str]]:
    """
    Parse sequence of type annotations separated by commas.

    Each type annotation might consist of a single type or a name-type pair.

    """

    res = []
    for elem in separate_sig(sig):
        elems = separate_sig(elem, ":", strip=False)
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


def type_to_nodes(typ: str, inliner) -> list[nodes.Node]:
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
            import sphinx_lua_ls.domain

            ref_nodes, warn_nodes = sphinx_lua_ls.domain.LuaXRefRole()(
                "lua:obj", text, text, 0, inliner
            )
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


def normalize_type(typ: str) -> str:
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


def make_anchor(name: str) -> str:
    return f"lua-{urllib.parse.quote(name)}"


def normalize_name(name: str) -> str:
    if "[" in name:
        return ".".join(
            [
                "[" + normalize_type(c[1:-1]) + "]"
                if c.startswith("[") and c.endswith("]")
                else c
                for c in separate_sig(name, ".")
            ]
        )
    else:
        return name


def parse_list_option(value: str):
    if not value:
        return True
    else:
        return separate_sig(value)
