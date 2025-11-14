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

    Enum = "enum"

    @property
    def order(self) -> int:
        return _GROUPWISE_ORDER[self]


_GROUPWISE_ORDER = {
    Kind.Table: 1,
    Kind.Data: 1,
    Kind.Function: 2,
    Kind.Class: 3,
    Kind.Alias: 4,
    Kind.Enum: 5,
    Kind.Module: 6,
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


@dataclass(kw_only=True, repr=False, eq=False)
class DocstringMixin:
    #: Raw docstring contents.
    docstring: str | None = None

    #: Whether we need to clean up LuaLs-generated junk.
    needs_cleanup: bool = False

    #: Additional options for `parsed_options`.
    inferred_options: dict[str, str] = dataclasses.field(default_factory=dict)

    #: Additional options for `parsed_doctype`.
    inferred_doctype: str | None = None

    @functools.cached_property
    def parsed_docstring(self) -> str | None:
        if not hasattr(self, "_parsed_docstring"):
            self._parse_docstring()
        return self._parsed_docstring

    @functools.cached_property
    def parsed_options(self) -> dict[str, str]:
        if not hasattr(self, "_parsed_options"):
            self._parse_docstring()
        return self._parsed_options

    @functools.cached_property
    def parsed_doctype(self) -> str | None:
        if not hasattr(self, "_parsed_doctype"):
            self._parse_docstring()
        return self._parsed_doctype

    def _parse_docstring(self):
        if not self.docstring:
            self._parsed_docstring = None
            self._parsed_options = {}
            self._parsed_doctype = self.inferred_doctype
            return

        docs = self.docstring

        if self.needs_cleanup:
            docs = re.sub(r"^\@\*\w+\*.*$", "", docs, flags=re.MULTILINE)
            docs = re.sub(
                r"^```lua\n.*?\n```", "", docs, flags=re.MULTILINE | re.DOTALL
            )

        self._parse_options(docs)
        docs = re.sub(r"^\s*\!doc(?:type)?\s+(?:.*)$", "", docs, flags=re.MULTILINE)

        if self.needs_cleanup:
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
                if match := re.search(
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
                    doc = doc.strip()
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
        else:
            docs = textwrap.dedent(docs)

        self._parsed_docstring = docs

    def _parse_options(self, docs: str):
        options: dict[str, str] = self.inferred_options
        doctype: str | None = self.inferred_doctype

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
class Param(DocstringMixin):
    """
    Function parameter or return value.

    """

    #: Parameter's name.
    name: str | None

    #: Parameter's type.
    type: str | None

    def __str__(self) -> str:
        return f"{self.name or '_'}: {self.type or 'unknown'}"


@dataclass(kw_only=True, repr=False, eq=False)
class Object(DocstringMixin):
    """
    A documented lua object.

    """

    #: When two objects with the same name are defined, the one with a higher
    #: priority wins.
    priority: _t.ClassVar[int] = 0

    #: Deprecation marker.
    is_deprecated: bool = False

    #: Deprecation reason.
    deprecation_reason: str | None = None

    #: Nodiscard marker.
    is_nodiscard: bool = False

    #: Nodiscard reason.
    nodiscard_reason: str | None = None

    #: Async marker.
    is_async: bool = False

    #: Object visibility.
    visibility: Visibility | None = None

    #: All ``@see`` notes parsed from docstring.
    #:
    #: Note: for lua ls, these are embedded into documentation.
    see: list[str] = dataclasses.field(default_factory=list)

    #: Absolute path to all `.lua` file where this object was defined.
    files: set[pathlib.Path] = dataclasses.field(default_factory=set)

    #: Where the docstring comes from.
    docstring_file: pathlib.Path | None = None

    #: True for definitions that come from Lua standard library and other libraries
    #: not in the project root.
    is_foreign: bool = False

    #: Line number in the file.
    line: int | None = None

    #: Child objects.
    children: dict[str, Object] = dataclasses.field(default_factory=dict)

    #: All ``@using`` directives of the module.
    using: list[str] = dataclasses.field(default_factory=list)

    #: Type that will be returned when you require this module.
    require_type: str | None = None

    #: Name of the ``require`` function used to require this module.
    require_function: str | None = None

    #: Separator used with the ``require`` function.
    require_separator: str | None = None

    #: True if this object appears on top level of object tree.
    is_toplevel: bool = False

    @functools.cached_property
    def kind(self) -> Kind | None:
        """
        Determine object's kind based on how lua-ls reported this object
        and how user specified ``!doctype``.

        Return `None` if user's ``!doctype`` is incompatible with returned type.

        """

        return self.get_kind(self.parsed_doctype)

    def get_kind(self, parsed_doctype: str | None) -> Kind | None:
        """
        Determine object's kind based on how lua-ls reported this object
        and the given doctype override.

        Return `None` if doctype override is incompatible with returned type.

        Doctype overrides can come either from ``!doctype`` found in object's
        docstring, or from autoobject directive options.

        """

        if parsed_doctype in [None, "module"]:
            return Kind.Module
        elif parsed_doctype in ["data", "const", "attribute"]:
            return Kind.Data
        elif parsed_doctype in ["table"]:
            return Kind.Table
        else:
            return None

    def find_all_bases(self, obj: Class) -> list[Object]:
        """
        Find all bases of a class, including transitive ones.

        Bases are returned in order of DFS.

        """

        if not hasattr(self, "_bases_cache"):
            self._bases_cache = {}

        if obj not in self._bases_cache:
            seen_bases: set[str] = set()
            res: list[Object] = []
            stack: list[str] = list(obj.bases)
            while stack:
                basename = stack.pop()
                if basename in seen_bases:
                    continue
                seen_bases.add(basename)
                if (base := self.find(basename)) and base != obj:
                    res.append(base)
                    if isinstance(base, Class):
                        stack.extend(base.bases)
            self._bases_cache[obj] = res

        return self._bases_cache[obj]

    def __repr__(self) -> str:
        return self.__class__.__name__

    def __str__(self) -> str:
        res = ""

        res += self._print_object()

        if self.is_deprecated:
            res += " (deprecated)"
        if self.is_async:
            res += " (async)"
        if self.is_nodiscard:
            res += " (nodiscard)"

        tail = self._print_object_tail()

        for name, ch in self.children.items():
            first, *rest = str(ch).splitlines()
            if rest:
                rest = "\n  " + "\n  ".join(rest)
            else:
                rest = ""
            res += f"\n  {name} {first}{rest}"

        if self.children and tail:
            res += "\n"
        res += tail

        return res

    def _print_object(self) -> str:
        return "{"

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


@dataclass(kw_only=True, repr=False, eq=False)
class Data(Object):
    """
    A lua variable.

    """

    priority = 1

    #: Variable type.
    type: str

    #: Variable literal.
    lit: str | None = None

    def get_kind(self, parsed_doctype: str | None) -> Kind | None:
        if parsed_doctype in [None, "data", "const", "attribute"]:
            return Kind.Data
        elif parsed_doctype in ["table"]:
            return Kind.Table
        elif parsed_doctype in ["module"]:
            return Kind.Module
        else:
            return None

    def _print_object(self) -> str:
        lit = f" = {self.lit}" if self.lit else ""
        return f": {self.type}{lit}"

    def _print_object_tail(self) -> str:
        return ""


@dataclass(kw_only=True, repr=False, eq=False)
class Table(Object):
    """
    A lua table.

    """

    priority = 1

    def get_kind(self, parsed_doctype: str | None) -> Kind | None:
        if parsed_doctype in [None, "table"]:
            return Kind.Table
        elif parsed_doctype in ["data", "const", "attribute"]:
            return Kind.Data
        elif parsed_doctype in ["module"]:
            return Kind.Module
        else:
            return None

    def _print_object(self) -> str:
        return "= table {"

    def _print_object_tail(self) -> str:
        return "}"


@dataclass(kw_only=True, repr=False, eq=False)
class Function(Object):
    """
    A lua function.

    """

    priority = 2

    #: Function parameters.
    params: list[Param] = dataclasses.field(default_factory=list)

    #: Function return values.
    returns: list[Param] = dataclasses.field(default_factory=list)

    #: Generic parameters of a class.
    generics: list[Param] = dataclasses.field(default_factory=list)

    #: List of overload declarations.
    overloads: list[str] = dataclasses.field(default_factory=list)

    #: Indicates that this function implicitly accepts ``self`` argument.
    implicit_self: bool = False

    def get_kind(self, parsed_doctype: str | None) -> Kind | None:
        if parsed_doctype in [
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
        generics = ", ".join(map(str, self.generics))
        if generics:
            generics = f"<{generics}>"
        returns = ", ".join(map(str, self.returns))
        if returns:
            returns = " -> " + returns
        return f"= function{generics}({params}){returns}"

    def _print_object_tail(self) -> str:
        return ""


@dataclass(kw_only=True, repr=False, eq=False)
class Class(Object):
    """
    A lua class.

    """

    priority = 2

    #: Base classes or types.
    bases: list[str] = dataclasses.field(default_factory=list)

    #: Generic parameters of a class.
    generics: list[Param] = dataclasses.field(default_factory=list)

    #: Name of the constructor function.
    constructor_name: str | None = None

    #: Function that will be invoked to initialize a class instance.
    constructor: Function | None = None

    def get_kind(self, parsed_doctype: str | None) -> Kind | None:
        if parsed_doctype in [None, "class"]:
            return Kind.Class
        elif parsed_doctype in ["data", "const", "attribute"]:
            return Kind.Data
        elif parsed_doctype in ["table"]:
            return Kind.Table
        elif parsed_doctype in ["module"]:
            return Kind.Module
        else:
            return None

    def _print_object(self) -> str:
        generics = ", ".join(map(str, self.generics))
        if generics:
            generics = f"<{generics}>"
        return f"= class{generics}({', '.join(self.bases)})"

    def _print_object_tail(self) -> str:
        return ""


@dataclass(kw_only=True, repr=False, eq=False)
class Alias(Object):
    """
    A lua type alias.

    """

    priority = 2

    #: Alias type.
    type: str

    #: Generic parameters of a class.
    generics: list[Param] = dataclasses.field(default_factory=list)

    def get_kind(self, parsed_doctype: str | None) -> Kind | None:
        if parsed_doctype in [None, "alias"]:
            return Kind.Alias
        elif parsed_doctype in ["data", "const", "attribute"]:
            return Kind.Data
        elif parsed_doctype in ["table"]:
            return Kind.Table
        elif parsed_doctype in ["module"]:
            return Kind.Module
        else:
            return None

    def _print_object(self) -> str:
        generics = ", ".join(map(str, self.generics))
        if generics:
            generics = f"<{generics}>"
        return f"= alias{generics}({self.type})"

    def _print_object_tail(self) -> str:
        return ""


@dataclass(kw_only=True, repr=False, eq=False)
class Enum(Object):
    """
    A lua enum.

    """

    priority = 2

    #: Enum type.
    type: str

    #: Generic parameters of a class.
    generics: list[Param] = dataclasses.field(default_factory=list)

    def get_kind(self, parsed_doctype: str | None) -> Kind | None:
        if parsed_doctype in [None, "enum"]:
            return Kind.Enum
        elif parsed_doctype in ["data", "const", "attribute"]:
            return Kind.Data
        elif parsed_doctype in ["table"]:
            return Kind.Table
        elif parsed_doctype in ["module"]:
            return Kind.Module
        else:
            return None

    def _print_object(self) -> str:
        generics = ", ".join(map(str, self.generics))
        if generics:
            generics = f"<{generics}>"
        return f"= enum{generics}({self.type})"

    def _print_object_tail(self) -> str:
        return ""


class Parser:
    #: Lua version used by this runtime.
    runtime_version: str | None = None

    #: Name of the function that will be invoked as a class constructor.
    class_default_function_name: str | None = None

    #: Whether to require first parameter of the constructor to be `self`.
    class_default_force_non_colon: bool = False

    #: Whether to force constructor to return `self`.
    class_default_force_return_self: bool = False

    #: Name of the ``require`` function.
    auto_require_function: str | None = None

    #: Separator used with the ``require`` function.
    auto_require_separator: str | None = None

    #: Whether we need to clean up LuaLs-generated junk.
    needs_cleanup = False

    def __init__(self):
        #: Root of the object tree.
        self.root = Object(needs_cleanup=self.needs_cleanup)

        #: All files seen while parsing docs.
        self.files: set[pathlib.Path] = set()

    def parse(self, json, path: str | pathlib.Path):
        """
        Parse jua-ls json output.

        """

        raise NotImplementedError()

    def add(self, path: str, o: Object):
        """
        Add an object to the object tree.

        """

        root = self.root
        *components, name = path.split(".")
        if not components:
            o.is_toplevel = True
        for component in components:
            if component in root.children:
                root = root.children[component]
            else:
                root.children[component] = root = Object(
                    needs_cleanup=self.needs_cleanup
                )
        self.add_child(root, name, o)

    def merge_objects(self, a: Object, b: Object) -> Object:
        """
        Merge two objects with the same name.

        """

        a, b = sorted([a, b], key=lambda x: (-x.is_foreign, -x.priority, x.line))
        for name, child in b.children.items():
            self.add_child(a, name, child)

        a.is_deprecated = a.is_deprecated or b.is_deprecated
        a.deprecation_reason = a.deprecation_reason or b.deprecation_reason
        a.is_nodiscard = a.is_nodiscard or b.is_nodiscard
        a.nodiscard_reason = a.nodiscard_reason or b.nodiscard_reason
        a.is_async = a.is_async or b.is_async
        a.visibility = a.visibility or b.visibility
        a.see.extend(b.see)
        a.files.update(b.files)
        a.docstring_file = a.docstring_file or b.docstring_file
        a.is_foreign = a.is_foreign and b.is_foreign
        a.line = a.line if a.line is not None else b.line
        a.inferred_options.update(b.inferred_options)
        a.inferred_doctype = a.inferred_doctype or b.inferred_doctype
        a.using.extend(b.using)

        if not a.docstring:
            a.docstring = b.docstring
            a.docstring_file = b.docstring_file
            a.needs_cleanup = b.needs_cleanup
        elif b.docstring and len(a.docstring) < len(b.docstring) and not b.is_foreign:
            # Sometimes, `@see` directives are only included in one definition.
            a.docstring = b.docstring
            a.docstring_file = b.docstring_file
            a.needs_cleanup = b.needs_cleanup
        return a

    def add_child(self, o: Object, name: str, child: Object):
        """
        Add child to an object, merging objects if necessary.

        """

        if name not in o.children:
            o.children[name] = child
        else:
            o.children[name] = self.merge_objects(o.children[name], child)


class LuaLsParser(Parser):
    needs_cleanup = True

    def parse(self, json, path: str | pathlib.Path):
        if not isinstance(json, list):
            return

        self.path = pathlib.Path(path).expanduser().resolve()

        for ns in json:
            self._parse_toplevel(ns)

    def _parse_toplevel(self, ns):
        if not isinstance(ns, dict):
            return

        o = self._parse_definitions(ns.get("defines", []))

        for field in ns.get("fields", []):
            if "name" not in field:
                continue

            self.add_child(o, field["name"], self._parse_field(field))

        if (
            isinstance(o, Class)
            and self.class_default_function_name
            and self.class_default_function_name in o.children
            and isinstance(o.children[self.class_default_function_name], Function)
        ):
            o.constructor_name = self.class_default_function_name
            o.constructor = _t.cast(
                Function, o.children.pop(self.class_default_function_name)
            )
            if self.class_default_force_non_colon:
                o.constructor.implicit_self = False
                if o.constructor.params and o.constructor.params[0].name == "self":
                    o.constructor.params.pop(0)

        self.add(ns.get("name", ""), o)

    def _parse_definitions(self, ns) -> Object:
        if not ns or not isinstance(ns, list):
            return Object(needs_cleanup=True)
        first, *rest = ns
        first = self._parse_definition(first)
        for o in rest:
            first = self.merge_objects(first, self._parse_definition(o))
        return first

    def _parse_definition(self, ns) -> Object:
        if not isinstance(ns, dict):
            return Object(needs_cleanup=True)

        match ns.get("type"):
            case "doc.class":
                res = Class(needs_cleanup=True)
                for base in ns.get("extends", []):
                    if "view" in base:
                        typ = self._normalize_type(base.get("view", None) or "unknown")
                        res.bases.append(typ)
                res.docstring = ns.get("desc")
            case "doc.alias":
                typ = self._normalize_type(ns.get("view", None) or "unknown")
                res = Alias(type=typ, needs_cleanup=True)
                _process_alias_doc(res, ns.get("desc"))
            case _:
                return self._parse_field(ns)

        res.is_deprecated = bool(ns.get("deprecated", False))
        res.is_async = bool(ns.get("async", False))
        res.visibility = Visibility(ns["visible"]) if "visible" in ns else None
        self._set_path(res, ns.get("file"))
        res.line = ns.get("start", [None, None])[0]

        return res

    def _parse_field(self, ns) -> Object:
        implicit_self = ns.get("type") == "setmethod"
        if "extends" not in ns or not isinstance(ns["extends"], dict):
            return Object(needs_cleanup=True)
        extends = ns["extends"]

        match extends.get("type"):
            case "function":
                res = Function(needs_cleanup=True)
                for param in extends.get("args", []):
                    name = param.get("name")
                    if param.get("type") == "...":
                        name = "..."
                    if not isinstance(name, str):
                        name = None
                    typ = self._normalize_type(param.get("view", None) or "unknown")
                    res.params.append(
                        Param(
                            name, typ, docstring=param.get("desc"), needs_cleanup=True
                        )
                    )
                for param in extends.get("returns", []):
                    name = param.get("name")
                    if param.get("type") == "...":
                        name = "..."
                    if not isinstance(name, str):
                        name = None
                    typ = self._normalize_type(param.get("view", None) or "unknown")
                    res.returns.append(
                        Param(
                            name, typ, docstring=param.get("desc"), needs_cleanup=True
                        )
                    )
                res.implicit_self = implicit_self
            case _:
                typ = self._normalize_type(ns.get("view", None) or "unknown")
                res = Data(type=typ, needs_cleanup=True)

        res.is_deprecated = bool(ns.get("deprecated", False))
        res.is_async = bool(ns.get("async", False))
        res.visibility = Visibility(ns["visible"]) if "visible" in ns else None
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


class EmmyLuaParser(Parser):
    _VISIBILITY_MAP = {
        "public": Visibility.Public,
        "protected": Visibility.Protected,
        "private": Visibility.Private,
        "internal": Visibility.Private,  # XXX: what?
        "package": Visibility.Package,
    }

    _RUNTIME_MAP = {
        "Lua5.1": "5.1",
        "Lua5.2": "5.2",
        "Lua5.3": "5.3",
        "Lua5.4": "5.4",
        "Lua5.5": "5.5",
        "LuaJIT": "jit",
        "LuaLatest": "5.4",
    }

    def parse(self, json, path: str | pathlib.Path):
        self.path = pathlib.Path(path).expanduser().resolve()

        class_default_config = json["config"]["runtime"].get("classDefaultCall")
        if class_default_config and class_default_config.get("functionName"):
            self.class_default_function_name = class_default_config["functionName"]
            self.class_default_force_non_colon = class_default_config["forceNonColon"]
            self.class_default_force_return_self = class_default_config[
                "forceReturnSelf"
            ]
        self.runtime_version = self._RUNTIME_MAP.get(
            json["config"]["runtime"]["version"], None
        )
        self.auto_require_function = json["config"]["completion"]["autoRequireFunction"]
        self.auto_require_separator = json["config"]["completion"][
            "autoRequireSeparator"
        ]

        self._parse_modules(json["modules"])
        self._parse_types(json["types"])
        self._parse_globals(json["globals"])

    def _parse_modules(self, modules):
        for data in modules:
            res = Object()
            self._set_common(res, data)
            self._set_path(res, data["file"])
            self._parse_members(res, data["members"])
            res.using = data["using"]
            res.require_type = data["typ"] or ""
            res.require_function = self.auto_require_function
            res.require_separator = self.auto_require_separator
            self.add(data["name"], res)

    def _parse_types(self, types):
        for data in types:
            if data["type"] == "class":
                self._parse_class(data)
            elif data["type"] == "enum":
                self._parse_enum(data)
            elif data["type"] == "alias":
                self._parse_alias(data)

    def _parse_class(self, data):
        res = Class()
        self._set_common(res, data)
        self._set_locs(res, data)
        res.bases = data["bases"]
        self._parse_generics(res, data.get("generics", []))
        self._parse_members(res, data["members"])

        if (
            self.class_default_function_name
            and self.class_default_function_name in res.children
            and isinstance(res.children[self.class_default_function_name], Function)
        ):
            res.constructor_name = self.class_default_function_name
            res.constructor = _t.cast(
                Function, res.children.pop(self.class_default_function_name)
            )
            if self.class_default_force_non_colon:
                res.constructor.implicit_self = False
                if res.constructor.params and res.constructor.params[0].name == "self":
                    res.constructor.params.pop(0)

        self.add(data["name"], res)

    def _parse_enum(self, data):
        res = Enum(type=data["typ"] or "unknown")
        self._set_common(res, data)
        self._set_locs(res, data)
        self._parse_generics(res, data.get("generics", []))
        self._parse_members(res, data["members"])

        self.add(data["name"], res)

    def _parse_alias(self, data):
        res = Alias(type=data["typ"] or "unknown")
        self._set_common(res, data)
        self._set_locs(res, data)
        self._parse_generics(res, data.get("generics", []))
        self._parse_members(res, data["members"])

        self.add(data["name"], res)

    def _parse_globals(self, globals):
        for data in globals:
            if data["type"] == "table":
                self._parse_global_table(data)
            elif data["type"] == "field":
                self._parse_global_field(data)

    def _parse_global_table(self, data):
        res = Table()
        self._set_common(res, data)
        self._set_loc(res, data)
        self._parse_members(res, data["members"])

        self.add(data["name"], res)

    def _parse_global_field(self, data):
        res = Data(type=data["typ"])
        self._set_common(res, data)
        self._set_loc(res, data)
        res.lit = data["literal"]

        self.add(data["name"], res)

    def _parse_members(self, res: Object, members):
        for data in members:
            if data["type"] == "fn":
                self._parse_fn(res, data)
            elif data["type"] == "field":
                self._parse_field(res, data)

    def _parse_fn(self, parent: Object, data):
        res = Function()
        self._set_common(res, data)
        self._set_loc(res, data)
        self._parse_generics(res, data.get("generics", []))
        for param in data["params"]:
            res.params.append(
                Param(name=param["name"], type=param["typ"], docstring=param["desc"])
            )
        for param in data["returns"]:
            res.returns.append(
                Param(name=param["name"], type=param["typ"], docstring=param["desc"])
            )
        res.overloads = data["overloads"]
        res.implicit_self = data["is_meth"]
        if res.implicit_self and (not res.params or res.params[0].name != "self"):
            res.params.insert(0, Param(name="self", type=None))

        self.add_child(parent, data["name"], res)

    def _parse_field(self, parent: Object, data):
        res = Data(type=data["typ"])
        self._set_common(res, data)
        self._set_loc(res, data)
        res.lit = data["literal"]

        self.add_child(parent, data["name"], res)

    def _parse_generics(self, res: Class | Alias | Enum | Function, generics):
        for data in generics:
            res.generics.append(Param(name=data["name"], type=data["base"]))

    def _set_common(self, res: Object, data):
        res.docstring = data["description"]
        res.visibility = self._VISIBILITY_MAP.get(data["visibility"], None)
        for tag in data.get("tag_content", None) or []:
            match tag["tag_name"]:
                case "see":
                    res.see.append(tag["content"].strip())
                case "doc":
                    value: str = tag["content"].strip()
                    if value:
                        [name, *args] = value.split(maxsplit=1)
                        res.inferred_options[name.strip()] = "".join(args)
                case "doctype":
                    res.inferred_doctype = tag["content"].strip()
                case _:
                    pass
        res.is_async = data.get("is_async", False)
        res.is_deprecated = data["deprecated"]
        res.deprecation_reason = data["deprecation_reason"]
        res.is_nodiscard = data.get("is_nodiscard", False)
        res.nodiscard_reason = data.get("nodiscard_message", None)

    def _set_path(self, res: Object, path: str | None) -> pathlib.Path | None:
        if path:
            resolved = pathlib.Path(self.path, path).resolve()
            res.files = {resolved}
            res.docstring_file = resolved
            res.is_foreign = not resolved.is_relative_to(self.path)
            self.files.add(resolved)
        else:
            return None

    def _set_loc(self, res: Object, data):
        if loc := data.get("loc", None):
            res.files = {pathlib.Path(self.path, loc["file"])}
            res.is_foreign = all(
                not file.is_relative_to(self.path) for file in res.files
            )
            res.docstring_file = pathlib.Path(self.path, loc["file"]).resolve()
            res.line = loc["line"] - 1

    def _set_locs(self, res: Object, data):
        if locs := data.get("loc", []):
            res.files = {pathlib.Path(self.path, loc["file"]).resolve() for loc in locs}
            res.is_foreign = all(
                not file.is_relative_to(self.path) for file in res.files
            )
            res.docstring_file = pathlib.Path(self.path, locs[0]["file"]).resolve()
            res.line = locs[0]["line"] - 1
