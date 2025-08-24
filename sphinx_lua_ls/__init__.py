import fnmatch
import pathlib
import re
import typing as _t

import sphinx.addnodes
import sphinx.application
import sphinx.builders
import sphinx.builders.html
import sphinx.domains
import sphinx.errors
from sphinx.util.display import progress_message
from sphinx.util.fileutil import copy_asset_file

import sphinx_lua_ls.apidoc
import sphinx_lua_ls.autodoc
import sphinx_lua_ls.autoindex
import sphinx_lua_ls.config
import sphinx_lua_ls.domain
import sphinx_lua_ls.inherited
import sphinx_lua_ls.intersphinx
import sphinx_lua_ls.lua_ls
import sphinx_lua_ls.objtree
from sphinx_lua_ls._version import __version__, __version_tuple__
from sphinx_lua_ls.pygments import LuaLexer


def run_lua_ls(app: sphinx.application.Sphinx):
    domain: sphinx_lua_ls.domain.LuaDomain = app.env.get_domain("lua")  # type: ignore

    root_dir = domain.config.project_root
    project_directories = domain.config.project_directories
    if project_directories is None:
        project_directories = [root_dir]
    project_directories.sort()

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

    min_version = domain.config.min_version
    if min_version is None:
        if domain.config.backend == "luals":
            min_version = "3.0.0"
        else:
            min_version = "0.11.0"

    cwd = pathlib.Path.cwd()
    try:
        runner = sphinx_lua_ls.lua_ls.resolve(
            backend=domain.config.backend,
            min_version=min_version,
            cwd=root_dir,
            reporter=sphinx_lua_ls.lua_ls.SphinxProgressReporter(app.verbosity),
            install=domain.config.auto_install,
            cache_path=domain.config.auto_install_location,
        )
    except sphinx_lua_ls.lua_ls.LuaLsError as e:
        raise
    except Exception as e:
        raise sphinx.errors.ExtensionError(str(e)) from e

    if domain.config.backend == "luals":
        parser = sphinx_lua_ls.objtree.LuaLsParser()
    else:
        parser = sphinx_lua_ls.objtree.EmmyLuaParser()

    configs = []
    if (path := pathlib.Path(root_dir, ".emmyrc.json")).exists():
        configs.append(path)
    if (path := pathlib.Path(root_dir, ".luarc.json")).exists():
        configs.append(path)
    parser.files.update(configs)

    for dir in project_directories:
        try:
            relpath = dir.relative_to(cwd, walk_up=True)
        except ValueError:
            relpath = dir
        with progress_message(f"running lua language server in {relpath or '.'}"):
            parser.class_default_function_name = (
                domain.config.class_default_function_name
            )
            parser.class_default_force_non_colon = (
                domain.config.class_default_force_non_colon
            )
            parser.class_default_force_return_self = (
                domain.config.class_default_force_return_self
            )
            parser.parse(runner.run(dir, configs=configs), dir)
            parser.files.update(map(pathlib.Path, dir.rglob("*.lua")))

    domain.objtree = parser.root
    domain.data["objtree_roots"] = project_directories
    domain.data["objtree_paths"] = {p: p.stat().st_mtime_ns for p in parser.files}

    if parser.runtime_version and not domain.config.lua_version:
        domain.config.lua_version = parser.runtime_version


def run_apidoc(
    app: sphinx.application.Sphinx,
):
    domain = _t.cast(sphinx_lua_ls.domain.LuaDomain, app.env.get_domain("lua"))
    cwd = pathlib.Path.cwd()
    for name, params in domain.config.apidoc_roots.items():
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
                outdir=app.outdir,
                domain=domain,
                dir=params["path"],
                fullname=name,
                objtree=domain.objtree,
                options=params["options"],
                depth=params["max_depth"],
                mod_filter=mod_filter,
                format=params["format"],
                separate_members=params["separate_members"],
            )


def copy_asset_files(app: sphinx.application.Sphinx, exc: Exception | None):
    if isinstance(app.builder, sphinx.builders.html.StandaloneHTMLBuilder) and not exc:
        custom_file = pathlib.Path(__file__).parent / "static/lua.css"
        static_dir = app.outdir / "_static"
        copy_asset_file(custom_file, static_dir)


def suppress_auto_ref_warnings(
    app: sphinx.application.Sphinx,
    domain: sphinx.domains.Domain,
    node: sphinx.addnodes.pending_xref,
):
    if node["refdomain"] == "lua" and node["reftype"] == "_auto":
        return True


def setup(app: sphinx.application.Sphinx):
    app.add_domain(sphinx_lua_ls.domain.LuaDomain)

    app.add_config_value("lua_ls_backend", None, rebuild="env")
    app.add_config_value("lua_ls_project_root", None, rebuild="env")
    app.add_config_value("lua_ls_project_directories", None, rebuild="env")
    app.add_config_value("lua_ls_auto_install", True, rebuild="")
    app.add_config_value("lua_ls_auto_install_location", None, rebuild="")
    app.add_config_value("lua_ls_min_version", None, rebuild="env")
    app.add_config_value("lua_ls_lua_version", None, rebuild="html")
    app.add_config_value("lua_ls_default_options", None, rebuild="env")
    app.add_config_value("lua_ls_apidoc_roots", None, rebuild="")
    app.add_config_value("lua_ls_apidoc_default_options", None, rebuild="")
    app.add_config_value("lua_ls_apidoc_max_depth", None, rebuild="")
    app.add_config_value("lua_ls_apidoc_ignored_modules", None, rebuild="")
    app.add_config_value("lua_ls_apidoc_format", None, rebuild="")
    app.add_config_value("lua_ls_apidoc_separate_members", None, rebuild="")
    app.add_config_value("lua_ls_class_default_function_name", None, rebuild="env")
    app.add_config_value("lua_ls_class_default_force_non_colon", None, rebuild="env")
    app.add_config_value("lua_ls_class_default_force_return_self", None, rebuild="env")
    app.add_config_value("lua_ls_maximum_signature_line_length", 50, rebuild="env")

    app.add_directive_to_domain(
        "lua", "autoobject", sphinx_lua_ls.autodoc.AutoObjectDirective
    )
    app.add_directive_to_domain(
        "lua", "autoindex", sphinx_lua_ls.autoindex.AutoIndexDirective
    )
    app.add_directive_to_domain(
        "lua",
        "other-inherited-members",
        sphinx_lua_ls.inherited.InheritedMembersDirective,
    )

    app.connect("builder-inited", sphinx_lua_ls.config.set_options)
    app.connect("builder-inited", run_lua_ls)
    app.connect("builder-inited", run_apidoc)
    app.connect("missing-reference", sphinx_lua_ls.intersphinx.resolve_std_reference)
    app.connect("build-finished", copy_asset_files)
    app.connect("warn-missing-reference", suppress_auto_ref_warnings)

    app.add_post_transform(sphinx_lua_ls.autoindex.AutoIndexTransform)
    app.add_post_transform(sphinx_lua_ls.inherited.InheritedMembersTransform)

    app.add_lexer("lua", LuaLexer)

    app.add_css_file("lua.css")

    return {
        "version": __version__,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
