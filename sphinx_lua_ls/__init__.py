import fnmatch
import pathlib
import re
from typing import Any, Type, TypeVar

import sphinx.application
import sphinx.errors
from sphinx.errors import ConfigError
from sphinx.util.display import progress_message
from sphinx.util.fileutil import copy_asset_file

import sphinx_lua_ls.apidoc
import sphinx_lua_ls.autodoc
import sphinx_lua_ls.autoindex
import sphinx_lua_ls.domain
import sphinx_lua_ls.intersphinx
import sphinx_lua_ls.lua_ls
import sphinx_lua_ls.objtree
from sphinx_lua_ls._version import __version__, __version_tuple__

T = TypeVar("T")


def _type(name: str, value, types: Type[T] | tuple[Type[T], ...]) -> T:
    if not isinstance(value, types):
        if not isinstance(types, tuple):
            types = (types,)
        raise ConfigError(
            f"{name} should be {' or '.join(map(str, types))}, got {type(value)} instead"
        )
    return value


def _version(name: str, value) -> str:
    _type(name, value, str)
    if not re.match(r"\d+(\.\d+)*", value):
        raise ConfigError(f"incorrect {name}: {value}")
    return value


def _path(name: str, value, root: str | pathlib.Path) -> pathlib.Path:
    if value is None:
        value = ""
    _type(name, value, (str, pathlib.Path))
    try:
        return pathlib.Path(root, value).expanduser().resolve()
    except ValueError as e:
        raise ConfigError(f"incorrect lua_ls_project_root: {e}") from None


def _paths(name: str, value, root: str | pathlib.Path) -> list[pathlib.Path]:
    if value is None:
        value = []
    _type(name, value, list)
    return [_path(f"{name}[{i}]", v, root) for i, v in enumerate(value)]


def _options(name: str, value) -> dict[str, Any]:
    if value is None:
        value = {}
    _type(name, value, dict)
    new_value = {}
    for key, option in value.items():
        parser = sphinx_lua_ls.autodoc.AutoObjectDirective.option_spec.get(key, None)
        if parser is None:
            raise ConfigError(f"unknown option in {name}: {key}")
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
    options: dict[str, Any],
    excludes: set[str],
) -> dict[str, dict[str, Any]]:
    if value is None:
        value = []
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


def check_options(app: sphinx.application.Sphinx):
    config = app.config

    domain: sphinx_lua_ls.domain.LuaDomain = app.env.get_domain("lua")  # type: ignore
    domain.config.clear()

    domain.config["project_root"] = _path(
        "lua_ls_project_root", config["lua_ls_project_root"], app.srcdir
    )
    if config["lua_ls_project_directories"] is not None:
        domain.config["project_directories"] = _paths(
            "lua_ls_project_directories",
            config["lua_ls_project_directories"],
            domain.config["project_root"],
        )
    else:
        domain.config.pop("project_directories", None)
    domain.config["auto_install"] = _type(
        "lua_ls_auto_install", config["lua_ls_auto_install"], bool
    )
    if config["lua_ls_auto_install_location"] is not None:
        domain.config["auto_install_location"] = _path(
            "lua_ls_auto_install_location",
            config["lua_ls_auto_install_location"],
            pathlib.Path("/"),
        )
    else:
        domain.config["auto_install_location"] = None
    domain.config["min_version"] = _version(
        "lua_ls_min_version", config["lua_ls_min_version"]
    )
    domain.config["lua_version"] = _version(
        "lua_ls_lua_version", config["lua_ls_lua_version"]
    )
    domain.config["default_options"] = _options(
        "lua_ls_default_options", config["lua_ls_default_options"]
    )
    domain.config["apidoc_default_options"] = domain.config["default_options"].copy()
    domain.config["apidoc_default_options"].update(
        _options(
            "lua_ls_apidoc_default_options", config["lua_ls_apidoc_default_options"]
        )
    )
    domain.config["apidoc_max_depth"] = _type(
        "lua_ls_apidoc_max_depth", config["lua_ls_apidoc_max_depth"], int
    )
    domain.config["apidoc_ignored_modules"] = _excludes(
        "lua_ls_apidoc_ignored_modules", config["lua_ls_apidoc_ignored_modules"]
    )
    domain.config["apidoc_roots"] = _api_roots(
        "lua_ls_apidoc_roots",
        config["lua_ls_apidoc_roots"],
        app.srcdir,
        domain.config["apidoc_max_depth"],
        domain.config["apidoc_default_options"],
        domain.config["apidoc_ignored_modules"],
    )


def run_lua_ls(app: sphinx.application.Sphinx):
    domain: sphinx_lua_ls.domain.LuaDomain = app.env.get_domain("lua")  # type: ignore

    root_dir = domain.config["project_root"]
    project_directories = sorted(domain.config.get("project_directories", [root_dir]))

    modified = (
        "objtree" not in domain.data
        or "objtree_roots" not in domain.data
        or "objtree_paths" not in domain.data
        or domain.data["objtree_roots"] != project_directories
    )
    if not modified:
        for path, modtime in domain.data["objtree_paths"].items():
            if not path.exists() or path.stat().st_mtime_ns > modtime:
                modified = True
                break
    if not modified:
        for dir in project_directories:
            for path in dir.rglob("*.lua"):
                if path not in domain.data["objtree_paths"]:
                    modified = True
                    break
    if not modified:
        return

    cwd = pathlib.Path.cwd()
    try:
        runner = sphinx_lua_ls.lua_ls.resolve(
            min_version=domain.config["min_version"],
            cwd=root_dir,
            reporter=sphinx_lua_ls.lua_ls.SphinxProgressReporter(app.verbosity),
            install=domain.config["auto_install"],
            cache_path=domain.config["auto_install_location"],
        )
    except sphinx_lua_ls.lua_ls.LuaLsError as e:
        raise sphinx.errors.ExtensionError(str(e))

    parser = sphinx_lua_ls.objtree.Parser()
    for dir in project_directories:
        try:
            relpath = dir.relative_to(cwd, walk_up=True)
        except ValueError:
            relpath = dir
        with progress_message(f"running lua language server in {relpath or '.'}"):
            parser.parse(runner.run(dir), dir)
            parser.files.update(dir.rglob("*.lua"))

    domain.data["objtree"] = parser.root
    domain.data["objtree_roots"] = project_directories
    domain.data["objtree_paths"] = {p: p.stat().st_mtime_ns for p in parser.files}


def run_apidoc(
    app: sphinx.application.Sphinx,
):
    domain: sphinx_lua_ls.domain.LuaDomain = app.env.get_domain("lua")  # type: ignore
    cwd = pathlib.Path.cwd()
    for name, params in domain.config["apidoc_roots"].items():
        objtree: sphinx_lua_ls.objtree.Object = app.env.domaindata["lua"]["objtree"]
        try:
            relpath = params["path"].relative_to(cwd, walk_up=True)
        except ValueError:
            relpath = params["path"]
        with progress_message(f"running lua apidoc in {relpath or '.'}"):
            ignored_modules = params["ignored_modules"]
            if ignored_modules:
                mod_filter = re.compile(
                    "|".join(f"(?:{fnmatch.translate(e)})" for e in ignored_modules)
                ).match
            else:
                mod_filter = lambda s: False
            sphinx_lua_ls.apidoc.generate(
                params["path"],
                name,
                objtree,
                params["options"],
                params["max_depth"],
                mod_filter,
            )


def copy_asset_files(app: sphinx.application.Sphinx, exc: Exception | None):
    if app.builder.format == "html" and not exc:
        custom_file = pathlib.Path(__file__).parent / "static/lua.css"
        static_dir = app.outdir / "_static"
        copy_asset_file(custom_file, static_dir)


def setup(app: sphinx.application.Sphinx):
    app.add_domain(sphinx_lua_ls.domain.LuaDomain)

    app.add_config_value("lua_ls_project_root", None, rebuild="env")
    app.add_config_value("lua_ls_project_directories", None, rebuild="env")
    app.add_config_value("lua_ls_auto_install", True, rebuild="")
    app.add_config_value("lua_ls_auto_install_location", None, rebuild="")
    app.add_config_value("lua_ls_min_version", "3.0.0", rebuild="env")
    app.add_config_value("lua_ls_lua_version", "5.4", rebuild="html")
    app.add_config_value("lua_ls_default_options", None, rebuild="env")
    app.add_config_value("lua_ls_apidoc_roots", {}, rebuild="")
    app.add_config_value("lua_ls_apidoc_default_options", None, rebuild="")
    app.add_config_value("lua_ls_apidoc_max_depth", 4, rebuild="")
    app.add_config_value("lua_ls_apidoc_ignored_modules", None, rebuild="")

    app.add_directive_to_domain(
        "lua", "autoobject", sphinx_lua_ls.autodoc.AutoObjectDirective
    )
    app.add_directive_to_domain(
        "lua", "autoindex", sphinx_lua_ls.autoindex.AutoIndexDirective
    )

    app.connect("builder-inited", check_options)
    app.connect("builder-inited", run_lua_ls)
    app.connect("builder-inited", run_apidoc)
    app.connect("missing-reference", sphinx_lua_ls.intersphinx.resolve_std_reference)
    app.connect("build-finished", copy_asset_files)

    app.add_post_transform(sphinx_lua_ls.autoindex.AutoIndexTransform)

    app.add_css_file("lua.css")

    return {
        "version": __version__,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
