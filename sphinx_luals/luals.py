from __future__ import annotations

from dataclasses import dataclass
import dataclasses
import enum
import functools
import json
import pathlib
import re
import subprocess
import tempfile
import typing as _t


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


@dataclass
class Param:
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


@dataclass(kw_only=True)
class Object:
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

    #: Absolute path to the `.lua` file where this object was defined.
    file: pathlib.Path | None = None

    #: Line number in the file.
    line: int | None = None

    #: Unparsed documentation text.
    docstring: str | None = None

    #: Child objects.
    children: dict[str, Object] = dataclasses.field(default_factory=dict)

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


@dataclass(kw_only=True)
class Data(Object):
    """
    A lua variable.

    """

    priority = 1

    #: Variable type.
    type: str

    def _print_object(self) -> str:
        return f": {self.type}"

    def _print_object_tail(self) -> str:
        return ""


@dataclass(kw_only=True)
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

    def _print_object(self) -> str:
        params = ", ".join(map(str, self.params))
        returns = ", ".join(map(str, self.returns))
        if returns:
            returns = " -> " + returns
        return f" = function ({params}){returns}"

    def _print_object_tail(self) -> str:
        return ""


@dataclass(kw_only=True)
class Class(Object):
    """
    A lua class.

    """

    priority = 2

    #: Base classes or types.
    bases: list[str] = dataclasses.field(default_factory=list)

    @functools.cached_property
    def is_module(self):
        """
        Indicates that this class is just a module or a namespace.

        """

        return self.bases == ["table"]

    def _print_object(self) -> str:
        bases = ', '.join(self.bases)
        if self.is_module:
            return " = module {"
        else:
            return f" = class({bases}) {{"

    def _print_object_tail(self) -> str:
        return "}"


@dataclass(kw_only=True)
class Alias(Object):
    """
    A lua type alias.

    """

    priority = 2

    #: Alias type.
    type: str

    def _print_object(self) -> str:
        return f" = {self.type}"

    def _print_object_tail(self) -> str:
        return ""


class Parser:
    def __init__(self, name_separator: str = ".", root_dir: str = "") -> None:
        #: Separator between name components.
        self.name_separator = name_separator

        #: Root of the object tree.
        self.root = Object()

        #:
        self.root_dir = root_dir

    def parse(self, json):
        """
        Parse jua-ls json output.

        """
        if not isinstance(json, list):
            return
        for ns in json:
            self._parse_toplevel(ns)

    def add(self, path: str, o: Object):
        """
        Add an object to the object tree.

        """

        root = self.root
        *components, name = path.split(self.name_separator)
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

        # TODO: handle function overloads?
        a, b = sorted([a, b], key=lambda x: (x.priority, x.line))
        for name, child in b.children.items():
            self.add_child(a, name, child)
        if not a.file:
            a.file = b.file
            a.line = b.line
        if not a.docstring:
            a.docstring = b.docstring
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
                        res.bases.append(base["view"])
            case "doc.alias":
                res = Alias(type=ns.get("view", "unknown"))
            case _:
                return self._parse_field(ns)

        res.is_deprecated = bool(ns.get("deprecated", False))
        res.is_async = bool(ns.get("async", False))
        res.visibility = Visibility(ns.get("visible", "public"))
        res.file = self._normalize_path(ns.get("file"))
        res.line = ns.get("start", [None, None])[0]
        res.docstring = ns.get("desc")

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
                    res.params.append(Param(name, param.get("view"), param.get("desc")))
                for param in extends.get("returns", []):
                    name = param.get("name")
                    if param.get("type") == "...":
                        name = "..."
                    if not isinstance(name, str):
                        name = None
                    res.returns.append(Param(name, param.get("view"), param.get("desc")))
                res.implicit_self = implicit_self
            case _:
                res = Data(type=extends.get("view", "unknown"))

        res.is_deprecated = bool(ns.get("deprecated", False))
        res.is_async = bool(ns.get("async", False))
        res.visibility = Visibility(ns.get("visible", "public"))
        res.file = self._normalize_path(ns.get("file"))
        res.line = ns.get("start", [None, None])[0]
        res.docstring = ns.get("desc")

        return res

    def _normalize_path(self, path: str | None) -> pathlib.Path | None:
        if path:
            return pathlib.Path(re.sub(r"^.*://", "", path))
        else:
            return None


# def parse_directories(luals_cmd: str, parser: Parser, dirs: list[str | pathlib.Path]):
#     for dir in dirs:
#         with tempfile.TemporaryDirectory() as tmpdir:
#             subprocess.check_call(
#                 [luals_cmd, "--doc", str(dir), "--doc_out_path", tmpdir]
#             )

#             parser.parse(json.loads(pathlib.Path(tmpdir, "doc.json").read_text()))
