import dataclasses
import pathlib
import re
import typing as _t
from dataclasses import dataclass

import sphinx.application
from sphinx.errors import ConfigError
from sphinx.util import logging

import sphinx_lua_ls.autodoc
import sphinx_lua_ls.domain

_logger = logging.getLogger("sphinx_lua_ls")

T = _t.TypeVar("T")
A = _t.ParamSpec("A")


@dataclass
class LuaDomainConfig:
    project_root: pathlib.Path
    backend: _t.Literal["emmylua", "luals"] = "luals"
    project_directories: list[pathlib.Path] | None = None
    auto_install: bool = True
    auto_install_location: pathlib.Path | None = None
    min_version: str | None = None
    max_version: str | None = None
    skip_versions: list[str] | None = None
    lua_version: str | None = None
    default_options: dict[str, _t.Any] = dataclasses.field(default_factory=dict)
    apidoc_default_options: dict[str, _t.Any] = dataclasses.field(default_factory=dict)
    apidoc_max_depth: int = 4
    apidoc_ignored_modules: set[str] = dataclasses.field(default_factory=set)
    apidoc_format: _t.Literal["rst", "md"] = "rst"
    apidoc_separate_members: bool = False
    apidoc_roots: dict[str, dict[str, _t.Any]] = dataclasses.field(default_factory=dict)
    class_default_function_name: str | None = None
    class_default_force_non_colon: bool = False
    class_default_force_return_self: bool = False
    maximum_signature_line_length: int | None = 50


def _type(name: str, value, types: _t.Type[T] | tuple[_t.Type[T], ...]) -> T:
    if not isinstance(value, types):
        if not isinstance(types, tuple):
            types = (types,)
        raise ConfigError(
            f"{name} should be {' or '.join(map(str, types))}, got {type(value)} instead"
        )
    return value


def _str_choices(name: str, value, choices: list[str]) -> str:
    value = _type(name, value, str)
    if value not in choices:
        raise ConfigError(
            f"{name} should be one of {', '.join(map(repr, choices))}, got {value!r} instead"
        )
    return value


def _version(name: str, value) -> str:
    _type(name, value, str)
    if not re.match(r"\d+(\.\d+)*", value):
        raise ConfigError(f"incorrect {name}: {value}")
    return value


def _path(name: str, value, root: str | pathlib.Path) -> pathlib.Path:
    _type(name, value, (str, pathlib.Path))
    try:
        return pathlib.Path(root, value).expanduser().resolve()
    except ValueError as e:
        raise ConfigError(f"incorrect lua_ls_project_root: {e}") from None


def _list(
    name: str,
    value,
    checker: _t.Callable[_t.Concatenate[str, object, A], T],
    *args: A.args,
    **kwargs: A.kwargs,
) -> list[T]:
    if value is None:
        value = []
    _type(name, value, list)
    return [checker(f"{name}[{i}]", v, *args, **kwargs) for i, v in enumerate(value)]


def _options(name: str, value) -> dict[str, _t.Any]:
    if value is None:
        value = {}
    _type(name, value, dict)
    new_value = {}
    for key, option in value.items():
        parser = sphinx_lua_ls.autodoc.AutoObjectDirective.option_spec.get(key, None)
        if parser is None:
            raise ConfigError(f"unknown option in {name}: :{key}:")
        if key not in sphinx_lua_ls.domain.GLOBAL_OPTIONS:
            raise ConfigError(
                f"incorrect option in {name}: :{key}: can't be set from config"
            )
        _type(f"{name}[{key!r}]", option, str)
        try:
            new_value[key] = parser(option)
        except Exception as e:
            raise ConfigError(f"incorrect {name}[{key!r}]: {e}") from None
    return new_value


def _api_roots(
    name: str,
    value,
    root: str | pathlib.Path,
    max_depth: int,
    options: dict[str, _t.Any],
    excludes: set[str],
    format: str,
    separate_members: bool,
) -> dict[str, dict[str, _t.Any]]:
    if value is None:
        value = {}
    _type(name, value, dict)
    new_value = {}
    for mod in value:
        api_root = value[mod]
        if isinstance(api_root, str):
            api_root = {"path": _path(f"{name}[{mod!r}]", api_root, root)}
        _type(f"{name}[{mod!r}]", api_root, (dict, str))

        new_api_root = {}
        new_api_root["path"] = _path(
            f"{name}[{mod!r}]['path']", api_root.pop("path", None), root
        )
        if not new_api_root["path"].is_relative_to(root):
            raise ConfigError(
                f"api root {name}[{mod!r}] lays outside of src root: {str(new_api_root['path'])}"
            )
        new_api_root["options"] = options.copy()
        new_api_root["options"].update(
            _options(f"{name}[{mod!r}]['options']", api_root.pop("options", None))
        )
        new_api_root["max_depth"] = _type(
            f"{name}[{mod!r}]['max_depth']", api_root.pop("max_depth", max_depth), int
        )
        new_api_root["ignored_modules"] = _excludes(
            f"{name}[{mod!r}]['ignored_modules']",
            api_root.pop("ignored_modules", excludes),
        )
        new_api_root["format"] = _str_choices(
            f"{name}[{mod!r}]['format']", api_root.pop("format", format), ["rst", "md"]
        )
        new_api_root["separate_members"] = _type(
            f"{name}[{mod!r}]['separate_members']",
            api_root.pop("separate_members", separate_members),
            bool,
        )
        if api_root:
            raise ConfigError(
                f"unknown keys in {name}[{mod!r}]: {', '.join(map(str, api_root))}"
            )
        new_value[mod] = new_api_root
    return new_value


def _excludes(name: str, value) -> set[str]:
    if value is None:
        value = []
    _type(name, value, (list, set))
    if isinstance(value, list):
        for i in range(len(value)):
            _type(f"{name}[{i}]", value[i], str)
    else:
        for v in value:
            _type(f"{name}[{v}]", v, str)
    return set(value)


def set_options(app: sphinx.application.Sphinx):
    config = app.config

    project_root = _path(
        "lua_ls_project_root", config["lua_ls_project_root"] or "", app.confdir
    )

    domain_config = LuaDomainConfig(project_root=project_root)

    if config["lua_ls_backend"] is not None:
        domain_config.backend = _t.cast(
            _t.Literal["emmylua", "luals"],
            _str_choices(
                "lua_ls_backend", config["lua_ls_backend"], ["luals", "emmylua"]
            ),
        )
    else:
        _logger.warning(
            "Sphinx-LuaLs will use EmmyLua as the default language server since v4.0. "
            "To keep using LuaLs, set `lua_ls_backend='luals' in your conf.py`",
            type="lua-ls",
        )

    if config["lua_ls_project_directories"] is not None:
        domain_config.project_directories = _list(
            "lua_ls_project_directories",
            config["lua_ls_project_directories"],
            _path,
            domain_config.project_root,
        )

    if config["lua_ls_auto_install"] is not None:
        domain_config.auto_install = _type(
            "lua_ls_auto_install", config["lua_ls_auto_install"], bool
        )

    if config["lua_ls_auto_install_location"] is not None:
        domain_config.auto_install_location = _path(
            "lua_ls_auto_install_location",
            config["lua_ls_auto_install_location"],
            pathlib.Path("/"),
        )

    if config["lua_ls_min_version"] is not None:
        domain_config.min_version = _version(
            "lua_ls_min_version", config["lua_ls_min_version"]
        )
    if config["lua_ls_max_version"] is not None:
        domain_config.max_version = (
            _version("lua_ls_max_version", config["lua_ls_max_version"])
            if config["lua_ls_max_version"] != "__auto__"
            else "__auto__"
        )
    if config["lua_ls_skip_versions"] is not None:
        domain_config.skip_versions = _list(
            "lua_ls_skip_versions", config["lua_ls_skip_versions"], _version
        )

    if config["lua_ls_lua_version"]:
        domain_config.lua_version = _str_choices(
            "lua_ls_lua_version",
            config["lua_ls_lua_version"],
            ["jit", "5.1", "5.2", "5.3", "5.4", "5.5"],
        )

    domain_config.default_options = _options(
        "lua_ls_default_options", config["lua_ls_default_options"]
    )
    domain_config.apidoc_default_options = domain_config.default_options.copy()
    domain_config.apidoc_default_options.update(
        _options(
            "lua_ls_apidoc_default_options", config["lua_ls_apidoc_default_options"]
        )
    )

    if config["lua_ls_apidoc_max_depth"] is not None:
        domain_config.apidoc_max_depth = _type(
            "lua_ls_apidoc_max_depth", config["lua_ls_apidoc_max_depth"], int
        )

    if config["lua_ls_apidoc_ignored_modules"] is not None:
        domain_config.apidoc_ignored_modules = _excludes(
            "lua_ls_apidoc_ignored_modules", config["lua_ls_apidoc_ignored_modules"]
        )

    if config["lua_ls_apidoc_format"] is not None:
        domain_config.apidoc_format = _t.cast(
            _t.Literal["rst", "md"],
            _str_choices(
                "lua_ls_apidoc_format", config["lua_ls_apidoc_format"], ["rst", "md"]
            ),
        )

    if config["lua_ls_apidoc_separate_members"] is not None:
        domain_config.apidoc_separate_members = _type(
            "lua_ls_apidoc_separate_members",
            config["lua_ls_apidoc_separate_members"],
            bool,
        )

    domain_config.apidoc_roots = _api_roots(
        "lua_ls_apidoc_roots",
        config["lua_ls_apidoc_roots"],
        app.confdir,
        domain_config.apidoc_max_depth,
        domain_config.apidoc_default_options,
        domain_config.apidoc_ignored_modules,
        domain_config.apidoc_format,
        domain_config.apidoc_separate_members,
    )

    if config["lua_ls_class_default_function_name"] is not None:
        domain_config.class_default_function_name = _type(
            "lua_ls_class_default_function_name",
            config["lua_ls_class_default_function_name"],
            str,
        )

    if config["lua_ls_class_default_force_non_colon"] is not None:
        domain_config.class_default_force_non_colon = _type(
            "lua_ls_class_default_force_non_colon",
            config["lua_ls_class_default_force_non_colon"],
            bool,
        )

    if config["lua_ls_class_default_force_return_self"] is not None:
        domain_config.class_default_force_return_self = _type(
            "lua_ls_class_default_force_return_self",
            config["lua_ls_class_default_force_return_self"],
            bool,
        )

    if config["lua_ls_maximum_signature_line_length"] is not None:
        domain_config.maximum_signature_line_length = _type(
            "lua_ls_maximum_signature_line_length",
            config["lua_ls_maximum_signature_line_length"],
            int,
        )
    else:
        domain_config.maximum_signature_line_length = _type(
            "maximum_signature_line_length",
            config["maximum_signature_line_length"],
            (int, type(None)),
        )

    domain = _t.cast(sphinx_lua_ls.domain.LuaDomain, app.env.get_domain("lua"))
    domain.config = domain_config
