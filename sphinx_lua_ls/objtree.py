"""
Parser for Lua-LS output.

"""

from __future__ import annotations

import dataclasses
import enum
import functools
import pathlib
import re
import textwrap
import typing as _t
from dataclasses import dataclass


class Kind(enum.Enum):
    """
    Kind of a lua object.

    """

    Module = "module"

    Table = "table"

    Data = "data"

    Function = "function"

    Class = "class"

    Alias = "alias"

    @property
    def order(self) -> int:
        return _GROUPWISE_ORDER[self]


_GROUPWISE_ORDER = {
    Kind.Table: 1,
    Kind.Data: 1,
    Kind.Function: 2,
    Kind.Class: 3,
    Kind.Alias: 4,
    Kind.Module: 5,
}


class Visibility(enum.Enum):
    """
    Visibility of a lua object.

    """

    #: Public visibility.
    Public = "public"

    #: Protected visibility.
    Protected = "protected"

    #: Private visibility.
    Private = "private"

    #: Module visibility.
    Package = "package"


class _ParseDocstringMixin:
    docstring: str | None

    @functools.cached_property
    def parsed_docstring(self) -> str | None:
        self._parse_docstring()
        return self._parsed_docstring

    @functools.cached_property
    def parsed_options(self) -> dict[str, str]:
        self._parse_docstring()
        return self._parsed_options

    @functools.cached_property
    def parsed_doctype(self) -> str | None:
        self._parse_docstring()
        return self._parsed_doctype

    def _parse_docstring(self):
        if not self.docstring:
            self._parsed_docstring = None
            self._parsed_options = {}
            self._parsed_doctype = None
            return

        docs = self.docstring
        docs = re.sub(r"^\@\*\w+\*.*$", "", docs, flags=re.MULTILINE)
        docs = re.sub(r"^```lua\n.*?\n```", "", docs, flags=re.MULTILINE | re.DOTALL)
        self._parse_options(docs)
        docs = re.sub(r"^\s*\!doc(?:type)?\s+(?:.*)$", "", docs, flags=re.MULTILINE)
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
        else:
            if match := re.match(
                r"""
                ^
                See:[ ]
                (?:
                    ~(?P<rejected_type>.+?)~ (?P<rejected_doc>.*)
                    |
                    \[(?P<type>.+?)\]\(.*?\) (?P<doc>.*)
                )
                $
                """,
                docs,
                flags=re.MULTILINE | re.VERBOSE,
            ):
                typ = match.group("type") or match.group("rejected_type")
                doc = match.group("doc") or match.group("rejected_doc") or ""
                if doc:
                    doc = ": " + doc
                see_lines.append(f":lua:obj:`{typ}`{doc}")
                docs = docs.replace(match.group(0), "")

        if rejected_see_lines:
            docs += "\n\nSee:\n" + "\n".join(rejected_see_lines)

        docs = textwrap.dedent(docs)

        if len(see_lines) > 1:
            see_lines = ["", "See:", ""] + [
                nl for l in see_lines for nl in (f"- {l}", "")
            ]
        else:
            see_lines = [""] + [f"See {l}" for l in see_lines]

        if see_lines:
            docs += "\n".join(see_lines)

        self._parsed_docstring = docs

    def _parse_options(self, docs: str):
        options: dict[str, str] = {}
        doctype: str | None = None

        for match in re.finditer(
            r"^\s*\!doc(?P<type>type)?\s+(?P<value>.*)$", docs, flags=re.MULTILINE
        ):
            if match.group("type"):
                doctype = match.group("value").strip()
            else:
                value = match.group("value").strip()
                if ":" in value:
                    name, arg = value.split(":", maxsplit=1)
                else:
                    name, arg = value, ""
                options[name.strip()] = arg.strip()

        self._parsed_options = options
        self._parsed_doctype = doctype


@dataclass
class Param(_ParseDocstringMixin):
    """
    Function parameter or return value.

    """

    #: Parameter's name.
    name: str | None

    #: Parameter's type.
    type: str | None

    #: Unparsed documentation text.
    docstring: str | None

    def __str__(self) -> str:
        return f"{self.name or '_'}: {self.type or 'unknown'}"


@dataclass(kw_only=True, repr=False)
class Object(_ParseDocstringMixin):
    """
    A documented lua object.

    """

    #: When two objects with the same name are defined, the one with a higher
    #: priority wins.
    priority: _t.ClassVar[int] = 0

    #: Deprecation marker.
    is_deprecated: bool = False

    #: Async marker.
    is_async: bool = False

    #: Object visibility.
    visibility: Visibility = Visibility.Public

    #: Absolute path to all `.lua` file where this object was defined.
    files: set[pathlib.Path] = dataclasses.field(default_factory=set)

    #: Where the docstring comes from.
    docstring_file: pathlib.Path | None = None

    #: True for definitions that come from Lua standard library and other libraries
    #: not in the project root.
    is_foreign: bool = False

    #: Line number in the file.
    line: int | None = None

    #: Unparsed documentation text.
    docstring: str | None = None

    #: Child objects.
    children: dict[str, Object] = dataclasses.field(default_factory=dict)

    @functools.cached_property
    def kind(self) -> Kind | None:
        """
        Determine object's kind based on how lua-ls reported this object
        and how user specified ``!doctype``.

        Return `None` if user's ``!doctype`` is incompatible with returned type.

        """

        if self.parsed_doctype in [None, "module"]:
            return Kind.Module
        elif self.parsed_doctype in ["data", "const", "attribute"]:
            return Kind.Data
        elif self.parsed_doctype in ["table"]:
            return Kind.Table
        else:
            return None

    def __repr__(self) -> str:
        return self.__class__.__name__

    def __str__(self) -> str:
        res = ""
        if self.is_deprecated:
            res += " (deprecated)"
        if self.is_async:
            res += " (async)"

        res += self._print_object()
        tail = self._print_object_tail()

        for name, ch in self.children.items():
            if not name.startswith("_"):
                first, *rest = str(ch).splitlines()
                if rest:
                    rest = "\n    " + "\n    ".join(rest)
                else:
                    rest = ""
                res += f"\n  {name}{first}{rest}"

        if self.children and tail:
            res += "\n"
        res += tail

        return res

    def _print_object(self) -> str:
        return " {"

    def _print_object_tail(self) -> str:
        return "}"

    def find(self, path: str) -> Object | None:
        """
        Find an object and return it.

        :param path:
            dot-separated object path.
        :return:
            a found object or ``None``.

        """

        root = self
        for name in path.split("."):
            if name not in root.children:
                return None
            root = root.children[name]
        return root

    def find_path(self, path: str) -> tuple[Object, str, str, str] | None:
        """
        Find an object and return a path to it.

        :param path:
            dot-separated object path.
        :return:
            an object itself, a module path component, a class path component,
            and an object name.

        """

        root = self

        in_class = False
        modname = []
        classname = []

        for name in path.split("."):
            if name not in root.children:
                return None

            root = root.children[name]

            if in_class or root.kind != Kind.Module:
                in_class = True
                classname.append(name)
            else:
                modname.append(name)

        if classname:
            name = classname.pop()
        elif modname:
            name = modname.pop()
        else:
            name = ""

        return root, ".".join(modname), ".".join(classname), name


@dataclass(kw_only=True, repr=False)
class Data(Object):
    """
    A lua variable.

    """

    priority = 1

    #: Variable type.
    type: str

    @functools.cached_property
    def kind(self) -> Kind | None:
        if self.parsed_doctype in [None, "data", "const", "attribute"]:
            return Kind.Data
        elif self.parsed_doctype in ["table"]:
            return Kind.Table
        elif self.parsed_doctype in ["module"]:
            return Kind.Module
        else:
            return None

    def _print_object(self) -> str:
        return f": {self.type}"

    def _print_object_tail(self) -> str:
        return ""


@dataclass(kw_only=True, repr=False)
class Function(Object):
    """
    A lua function.

    """

    priority = 2

    #: Function parameters.
    params: list[Param] = dataclasses.field(default_factory=list)

    #: Function return values.
    returns: list[Param] = dataclasses.field(default_factory=list)

    #: Indicates that this function implicitly accepts ``self`` argument.
    implicit_self: bool = False

    @functools.cached_property
    def kind(self) -> Kind | None:
        if self.parsed_doctype in [
            None,
            "function",
            "method",
            "classmethod",
            "staticmethod",
        ]:
            return Kind.Function
        else:
            return None

    def _print_object(self) -> str:
        params = ", ".join(map(str, self.params))
        returns = ", ".join(map(str, self.returns))
        if returns:
            returns = " -> " + returns
        return f" = function ({params}){returns}"

    def _print_object_tail(self) -> str:
        return ""


@dataclass(kw_only=True, repr=False)
class Class(Object):
    """
    A lua class.

    """

    priority = 2

    #: Base classes or types.
    bases: list[str] = dataclasses.field(default_factory=list)

    @functools.cached_property
    def kind(self) -> Kind | None:
        if self.parsed_doctype in [None, "class"]:
            return Kind.Class
        elif self.parsed_doctype in ["data", "const", "attribute"]:
            return Kind.Data
        elif self.parsed_doctype in ["table"]:
            return Kind.Table
        elif self.parsed_doctype in ["module"]:
            return Kind.Module
        else:
            return None

    def _print_object(self) -> str:
        return f" = class({', '.join(self.bases)}) {{"

    def _print_object_tail(self) -> str:
        return "}"


@dataclass(kw_only=True, repr=False)
class Alias(Object):
    """
    A lua type alias.

    """

    priority = 2

    #: Alias type.
    type: str

    @functools.cached_property
    def kind(self) -> Kind | None:
        if self.parsed_doctype in [None, "alias"]:
            return Kind.Alias
        elif self.parsed_doctype in ["data", "const", "attribute"]:
            return Kind.Data
        elif self.parsed_doctype in ["table"]:
            return Kind.Table
        elif self.parsed_doctype in ["module"]:
            return Kind.Module
        else:
            return None

    def _print_object(self) -> str:
        return f" = {self.type}"

    def _print_object_tail(self) -> str:
        return ""


class Parser:
    def __init__(self):
        #: Root of the object tree.
        self.root = Object()

        #: All files seen while parsing docs.
        self.files: set[pathlib.Path] = set()

    def parse(self, json, path: str | pathlib.Path):
        """
        Parse jua-ls json output.

        """
        if not isinstance(json, list):
            return

        self.path = pathlib.Path(path).expanduser().resolve()

        for ns in json:
            self._parse_toplevel(ns)

    def add(self, path: str, o: Object):
        """
        Add an object to the object tree.

        """

        root = self.root
        *components, name = path.split(".")
        for component in components:
            if component in root.children:
                root = root.children[component]
            else:
                root.children[component] = root = Object()
        self.add_child(root, name, o)

    def merge_objects(self, a: Object, b: Object) -> Object:
        """
        Merge two objects with the same name.

        """

        a, b = sorted([a, b], key=lambda x: (-x.is_foreign, -x.priority, x.line))
        for name, child in b.children.items():
            self.add_child(a, name, child)
        a.files.update(b.files)
        a.is_foreign = a.is_foreign and b.is_foreign
        if not a.docstring:
            a.docstring = b.docstring
            a.docstring_file = b.docstring_file
        elif b.docstring and len(a.docstring) < len(b.docstring) and not b.is_foreign:
            # Sometimes, `@see` directives are only included in one definition.
            a.docstring = b.docstring
            a.docstring_file = b.docstring_file
        return a

    def add_child(self, o: Object, name: str, child: Object):
        """
        Add child to an object, merging objects if necessary.

        """

        if name not in o.children:
            o.children[name] = child
        else:
            o.children[name] = self.merge_objects(o.children[name], child)

    def _parse_toplevel(self, ns):
        if not isinstance(ns, dict):
            return

        o = self._parse_definitions(ns.get("defines", []))

        for field in ns.get("fields", []):
            if "name" not in field:
                continue

            self.add_child(o, field["name"], self._parse_field(field))

        self.add(ns.get("name", ""), o)

    def _parse_definitions(self, ns) -> Object:
        if not ns or not isinstance(ns, list):
            return Object()
        first, *rest = ns
        first = self._parse_definition(first)
        for o in rest:
            first = self.merge_objects(first, self._parse_definition(o))
        return first

    def _parse_definition(self, ns) -> Object:
        if not isinstance(ns, dict):
            return Object()

        match ns.get("type"):
            case "doc.class":
                res = Class()
                for base in ns.get("extends", []):
                    if "view" in base:
                        typ = self._normalize_type(base.get("view", None) or "unknown")
                        res.bases.append(typ)
                res.docstring = ns.get("desc")
            case "doc.alias":
                typ = self._normalize_type(ns.get("view", None) or "unknown")
                res = Alias(type=typ)
                _process_alias_doc(res, ns.get("desc"))
            case _:
                return self._parse_field(ns)

        res.is_deprecated = bool(ns.get("deprecated", False))
        res.is_async = bool(ns.get("async", False))
        res.visibility = Visibility(ns.get("visible", "public"))
        self._set_path(res, ns.get("file"))
        res.line = ns.get("start", [None, None])[0]

        return res

    def _parse_field(self, ns) -> Object:
        implicit_self = ns.get("type") == "setmethod"
        if "extends" not in ns or not isinstance(ns["extends"], dict):
            return Object()
        extends = ns["extends"]

        match extends.get("type"):
            case "function":
                res = Function()
                for param in extends.get("args", []):
                    name = param.get("name")
                    if param.get("type") == "...":
                        name = "..."
                    if not isinstance(name, str):
                        name = None
                    typ = self._normalize_type(param.get("view", None) or "unknown")
                    res.params.append(Param(name, typ, param.get("desc")))
                for param in extends.get("returns", []):
                    name = param.get("name")
                    if param.get("type") == "...":
                        name = "..."
                    if not isinstance(name, str):
                        name = None
                    typ = self._normalize_type(param.get("view", None) or "unknown")
                    res.returns.append(Param(name, typ, param.get("desc")))
                res.implicit_self = implicit_self
            case _:
                typ = self._normalize_type(ns.get("view", None) or "unknown")
                res = Data(type=typ)

        res.is_deprecated = bool(ns.get("deprecated", False))
        res.is_async = bool(ns.get("async", False))
        res.visibility = Visibility(ns.get("visible", "public"))
        self._set_path(res, ns.get("file"))
        res.line = ns.get("start", [None, None])[0]
        res.docstring = ns.get("desc")

        return res

    def _set_path(self, res: Object, path: str | None) -> pathlib.Path | None:
        if path:
            path = re.sub(r"^\s*\[FOREIGN\]\s*", "", path, flags=re.IGNORECASE)
            path = re.sub(r"^.*?://", "", path)
            resolved = pathlib.Path(self.path, path).resolve()
            res.files = {resolved}
            res.docstring_file = resolved
            res.is_foreign = not resolved.is_relative_to(self.path)
            self.files.add(resolved)
        else:
            return None

    def _normalize_type(self, typ: str) -> str:
        if re.match(r"^\([\w.-]+\)\?$", typ):
            return typ[1:-2] + "?"
        else:
            return typ


def _process_alias_doc(node: Alias, doc: str | None):
    if not doc or not (doc.startswith("```lua\n") and doc.endswith("\n```")):
        node.docstring = doc
        return

    main_doc = []

    for line in doc[7:-5].splitlines():
        if line.startswith("--"):
            main_doc.append(line[2:])

    node.docstring = "\n".join(main_doc)
