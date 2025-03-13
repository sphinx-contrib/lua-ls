import pathlib
import re
from typing import Any

import sphinx.addnodes
import sphinx.application
import sphinx.config
import sphinx.environment
import sphinx.errors
import sphinx.ext.intersphinx
from sphinx.errors import ConfigError
from sphinx.util.display import progress_message

import sphinx_lua_ls.apidoc
import sphinx_lua_ls.autodoc
import sphinx_lua_ls.autoindex
import sphinx_lua_ls.domain
import sphinx_lua_ls.intersphinx
import sphinx_lua_ls.lua_ls
import sphinx_lua_ls.objtree
from sphinx_lua_ls._version import __version__, __version_tuple__


def _version(name: str, value) -> str:
    if not isinstance(value, str):
        raise ConfigError(f"{name} should be str, got {type(value)} instead")
    if not re.match(r"\d+(\.\d+)*", value):
        raise ConfigError(f"incorrect {name}: {value}")
    return value


def _path(name: str, value, root: str | pathlib.Path) -> pathlib.Path:
    if value is None:
        value = ""
    if not isinstance(value, (str, pathlib.Path)):
        raise ConfigError(f"{name} should be str, got {type(value)} instead")
    try:
        return pathlib.Path(root, value).expanduser().resolve()
    except ValueError as e:
        raise ConfigError(f"incorrect lua_ls_project_root: {e}") from None


def _paths(name: str, value, root: str | pathlib.Path) -> list[pathlib.Path]:
    if value is None:
        value = []
    if not isinstance(value, list):
        raise ConfigError(f"{name} should be list, got {type(value)} instead")
    return [_path(f"{name}[{i}]", v, root) for i, v in enumerate(value)]


def _bool(name: str, value) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{name} should be bool, got {type(value)} instead")
    return value


def _int(name: str, value) -> int:
    if not isinstance(value, int):
        raise ConfigError(f"{name} should be int, got {type(value)} instead")
    return value


def _options(name: str, value) -> dict[str, Any]:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ConfigError(f"{name} should be dict, got {type(value)} instead")
    new_value = {}
    for key, option in value.items():
        parser = sphinx_lua_ls.autodoc.AutoObjectDirective.option_spec.get(key, None)
        if parser is None:
            raise ConfigError(f"unknown option in {name}: {key}")
        if option is not None and not isinstance(option, str):
            raise ConfigError(
                f"{name}[{key!r}] should be str, got {type(option)} instead"
            )
        try:
            new_value[key] = parser(option)
        except Exception as e:
            raise ConfigError(f"incorrect {name}[{key!r}]: {e}") from None
    return new_value


def _api_roots(
    name: str, value, root: str | pathlib.Path, max_depth: int, options: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    if value is None:
        value = []
    if not isinstance(value, dict):
        raise ConfigError(f"{name} should be list, got {type(value)} instead")
    new_value = {}
    for mod in value:
        api_root = value[mod]
        if isinstance(api_root, str):
            api_root = {"path": _path(f"{name}[{mod!r}]", api_root, root)}
        if not isinstance(api_root, dict):
            raise ConfigError(
                f"{name}[{mod!r}] should be dict or str, got {type(api_root)} instead"
            )

        new_api_root = {}
        new_api_root["path"] = _path(
            f"{name}[{mod!r}]['path']", api_root.pop("path", None), root
        )
        if not new_api_root["path"].is_relative_to(root):
            raise ConfigError(
                f"api root {name}[{mod!r}] lays outside of src root: {str(new_api_root['path'])}"
            )
        new_api_root["options"] = _options(
            f"{name}[{mod!r}]['options']", api_root.pop("options", None)
        )
        for option_name, option_value in options.items():
            if option_name not in new_api_root["options"]:
                new_api_root["options"][option_name] = option_value
        new_api_root["max_depth"] = _int(
            f"{name}[{mod!r}]['max_depth']", api_root.pop("max_depth", max_depth)
        )
        if api_root:
            raise ConfigError(
                f"unknown keys in {name}[{mod!r}]: {', '.join(map(str, api_root))}"
            )
        new_value[mod] = new_api_root
    return new_value


def check_options(app: sphinx.application.Sphinx):
    config = app.config

    domain: sphinx_lua_ls.domain.LuaDomain = app.env.get_domain("lua")  # type: ignore
    domain.config.clear()

    domain.config["project_root"] = _path(
        "lua_ls_project_root", config["lua_ls_project_root"], app.srcdir
    )
    domain.config["project_directories"] = _paths(
        "lua_ls_project_directories",
        config["lua_ls_project_directories"],
        domain.config["project_root"],
    )
    domain.config["auto_install"] = _bool(
        "lua_ls_auto_install", config["lua_ls_auto_install"]
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
    domain.config["apidoc_default_options"] = _options(
        "lua_ls_apidoc_default_options", config["lua_ls_apidoc_default_options"]
    )
    domain.config["apidoc_max_depth"] = _int(
        "lua_ls_apidoc_max_depth", config["lua_ls_apidoc_max_depth"]
    )
    domain.config["apidoc_roots"] = _api_roots(
        "lua_ls_apidoc_roots",
        config["lua_ls_apidoc_roots"],
        app.srcdir,
        domain.config["apidoc_max_depth"],
        domain.config["apidoc_default_options"],
    )


def run_lua_ls(app: sphinx.application.Sphinx):
    domain: sphinx_lua_ls.domain.LuaDomain = app.env.get_domain("lua")  # type: ignore

    root_dir = domain.config["project_root"]
    project_directories = sorted(domain.config["project_directories"] or [root_dir])

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
        with progress_message(
            f"running lua language server in {dir.relative_to(cwd, walk_up=True) or '.'}"
        ):
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
        root: sphinx_lua_ls.objtree.Object = app.env.domaindata["lua"]["objtree"]
        with progress_message(
            f"running lua apidoc in {params['path'].relative_to(cwd, walk_up=True) or '.'}"
        ):
            sphinx_lua_ls.apidoc.generate(
                params["path"],
                name,
                root,
                params["options"],
                params["max_depth"],
            )


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

    app.add_post_transform(sphinx_lua_ls.autoindex.AutoIndexTransform)

    return {
        "version": __version__,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
