import pathlib
import re

import sphinx.addnodes
import sphinx.application
import sphinx.config
import sphinx.environment
import sphinx.errors
import sphinx.ext.intersphinx
from sphinx.util.display import progress_message

import sphinx_luals.autodoc
import sphinx_luals.domain
from sphinx_luals import doctree, intersphinx, lua_ls
from sphinx_luals._version import __version__, __version_tuple__


def check_options(
    app: sphinx.application.Sphinx,
    config: sphinx.config.Config,
):
    lua_version = config["luals_lua_version"]
    if not isinstance(lua_version, str):
        raise sphinx.config.ConfigError(
            f"expected luals_lua_version to be a str, got {type(lua_version)} instead"
        )
    if not re.match(r"\d+(\.\d+)*", lua_version):
        raise sphinx.config.ConfigError(f"incorrect luals_lua_version: {lua_version}")

    project_root = config["luals_project_root"]
    if project_root is None:
        project_root = ""
    if not isinstance(lua_version, (str, pathlib.Path)):
        raise sphinx.config.ConfigError(
            f"expected luals_project_root to be a str, got {type(project_root)} instead"
        )
    try:
        project_root = config["luals_project_root"] = pathlib.Path(
            app.srcdir, project_root
        ).resolve()
    except ValueError as e:
        raise sphinx.config.ConfigError(f"incorrect luals_project_root: {e}") from None

    project_directories = config["luals_project_directories"]
    if project_directories is None:
        project_directories = config["luals_project_directories"] = []
    if not isinstance(project_directories, list):
        raise sphinx.config.ConfigError(
            f"expected luals_project_directories to be a list, got {type(project_directories)} instead"
        )
    for i, project_directory in enumerate(project_directories):
        if not isinstance(project_directory, (str, pathlib.Path)):
            raise sphinx.config.ConfigError(
                f"expected luals_project_directories[{i}] to be a list, got {type(project_directory)} instead"
            )
        try:
            project_directories[i] = pathlib.Path(
                project_root, project_directory
            ).resolve()
        except ValueError as e:
            raise sphinx.config.ConfigError(
                f"incorrect luals_project_directories[{i}]: {e}"
            ) from None

    auto_install = config["luals_auto_install"]
    if not isinstance(auto_install, bool):
        raise sphinx.config.ConfigError(
            f"expected luals_auto_install to be a bool, got {type(auto_install)} instead"
        )

    auto_install_location = config["luals_auto_install_location"]
    if auto_install_location is not None:
        if not isinstance(auto_install_location, (str, pathlib.Path)):
            raise sphinx.config.ConfigError(
                f"expected luals_auto_install_location to be a str, got {type(auto_install_location)} instead"
            )
        try:
            auto_install_location = config["auto_install_location"] = pathlib.Path(
                auto_install_location
            ).resolve()
        except ValueError as e:
            raise sphinx.config.ConfigError(
                f"incorrect luals_auto_install_location: {e}"
            ) from None

    min_version = config["luals_min_version"]
    if not isinstance(min_version, str):
        raise sphinx.config.ConfigError(
            f"expected luals_min_version to be a str, got {type(min_version)} instead"
        )
    if not re.match(r"\d+(\.\d+)*", min_version):
        raise sphinx.config.ConfigError(f"incorrect luals_min_version: {min_version}")

    default_options = config["luals_default_options"]
    if default_options is None:
        default_options = config["luals_default_options"] = {}
    if not isinstance(default_options, dict):
        raise sphinx.config.ConfigError(
            f"expected luals_default_options to be a dict, got {type(default_options)} instead"
        )
    for name, value in default_options.items():
        parser = sphinx_luals.autodoc.AutoObjectDirective.option_spec.get(name, None)
        if parser is None:
            raise sphinx.config.ConfigError(
                f"unknown option in luals_default_options: {name}"
            )
        if value is not None and not isinstance(value, str):
            raise sphinx.config.ConfigError(
                f"expected luals_default_options[{name!r} to be a string, got {type(value)} instead"
            )
        try:
            default_options[name] = parser(value)
        except Exception as e:
            raise sphinx.config.ConfigError(
                f"incorrect option {name} in luals_default_options: {e}"
            ) from None


@progress_message("running lua language server")
def run_lua_ls(
    app: sphinx.application.Sphinx,
    env: sphinx.environment.BuildEnvironment,
    docnames: list[str],
):
    root_dir = app.config["luals_project_root"]
    project_directories = app.config["luals_project_directories"] or [root_dir]

    try:
        runner = lua_ls.resolve(
            min_version=app.config["luals_min_version"],
            cwd=root_dir,
            reporter=lua_ls.SphinxProgressReporter(app.verbosity),
            install=app.config["luals_auto_install"],
            cache_path=app.config["luals_auto_install_location"],
        )
    except lua_ls.LuaLsError as e:
        raise sphinx.errors.ExtensionError(str(e))

    parser = doctree.Parser()
    for dir in project_directories:
        parser.parse(runner.run(dir))

    setattr(env, "luals_doc_root", parser.root)


def setup(app: sphinx.application.Sphinx):
    app.add_domain(sphinx_luals.domain.LuaDomain)

    app.add_config_value("luals_project_root", None, rebuild="env")
    app.add_config_value("luals_project_directories", None, rebuild="env")
    app.add_config_value("luals_auto_install", True, rebuild="")
    app.add_config_value("luals_auto_install_location", None, rebuild="")
    app.add_config_value("luals_min_version", "3.0.0", rebuild="env")
    app.add_config_value("luals_lua_version", "5.4", rebuild="env")
    app.add_config_value("luals_default_options", None, rebuild="env")

    app.add_directive_to_domain(
        "lua", "autoobject", sphinx_luals.autodoc.AutoObjectDirective
    )

    app.connect("config-inited", check_options)
    app.connect("env-before-read-docs", run_lua_ls)
    app.connect("missing-reference", intersphinx.resolve_std_reference)

    return {
        "version": __version__,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
