"""
Parser for Lua-LS output.

"""

from __future__ import annotations

import dataclasses
import enum
import functools
import pathlib
import re
import typing as _t
from dataclasses import dataclass


class Kind(enum.Enum):
    """
    Kind of a lua object.

    """

    Module = "module"

    Data = "data"

    Function = "function"

    Class = "class"

    Alias = "alias"


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


@dataclass(kw_only=True, repr=False)
class Object:
    """
    A documented lua object.

    """

    #: When two objects with the same name are defined, the one with a higher
    #: priority wins.
    priority: _t.ClassVar[int] = 0

    #: Kind of a lua object.
    kind: Kind = dataclasses.field(default=Kind.Module, init=False)

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

            if in_class or root.kind != Kind.Module:
                in_class = True
                classname.append(name)
            else:
                modname.append(name)

            root = root.children[name]

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

    kind = Kind.Data

    priority = 1

    #: Variable type.
    type: str

    def _print_object(self) -> str:
        return f": {self.type}"

    def _print_object_tail(self) -> str:
        return ""


@dataclass(kw_only=True, repr=False)
class Function(Object):
    """
    A lua function.

    """

    kind = Kind.Function

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


@dataclass(kw_only=True, repr=False)
class Class(Object):
    """
    A lua class.

    """

    priority = 2

    kind = Kind.Class  # type: ignore

    #: Base classes or types.
    bases: list[str] = dataclasses.field(default_factory=list)

    @functools.cached_property
    def is_module(self):
        """
        Indicates that this class is just a module or a namespace.

        """

        return self.bases == ["table"]

    @property
    def kind(self) -> Kind:  # type: ignore
        return Kind.Module if self.is_module else Kind.Class

    def _print_object(self) -> str:
        bases = ", ".join(self.bases)
        if self.is_module:
            return " = module {"
        else:
            return f" = class({bases}) {{"

    def _print_object_tail(self) -> str:
        return "}"


@dataclass(kw_only=True, repr=False)
class Alias(Object):
    """
    A lua type alias.

    """

    priority = 2

    kind = Kind.Alias

    #: Alias type.
    type: str

    def _print_object(self) -> str:
        return f" = {self.type}"

    def _print_object_tail(self) -> str:
        return ""


class Parser:
    def __init__(self):
        #: Root of the object tree.
        self.root = Object()

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

        # TODO: handle function overloads?
        a, b = sorted([a, b], key=lambda x: (-x.priority, x.line))
        for name, child in b.children.items():
            self.add_child(a, name, child)
        if not a.file:
            a.file = b.file
            a.line = b.line
        if not a.docstring:
            a.docstring = b.docstring
        elif b.docstring:
            if len(a.docstring) < len(b.docstring):
                # Sometimes, `@see` directives are only included in one definition.
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
                res.docstring = ns.get("desc")
                for base in ns.get("extends", []):
                    if "view" in base:
                        res.bases.append(base["view"])
            case "doc.alias":
                res = Alias(type=ns.get("view", "unknown"))
                _process_alias_doc(res, ns.get("desc"))
            case _:
                return self._parse_field(ns)

        res.is_deprecated = bool(ns.get("deprecated", False))
        res.is_async = bool(ns.get("async", False))
        res.visibility = Visibility(ns.get("visible", "public"))
        res.file = self._normalize_path(ns.get("file"))
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
                    typ = param.get("view")
                    res.params.append(Param(name, typ, param.get("desc")))
                for param in extends.get("returns", []):
                    name = param.get("name")
                    if param.get("type") == "...":
                        name = "..."
                    if not isinstance(name, str):
                        name = None
                    typ = param.get("view")
                    res.returns.append(Param(name, typ, param.get("desc")))
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
            return pathlib.Path(re.sub(r"^.*://", "", path)).resolve()
        else:
            return None


def _process_alias_doc(node: Alias, doc: str | None):
    if not doc or not (doc.startswith("```lua\n") and doc.endswith("\n```")):
        node.docstring = doc
        return

    main_doc = []

    for line in doc[7:-5].splitlines():
        if line.startswith("--"):
            main_doc.append(line[2:])

    node.docstring = "\n".join(main_doc)
