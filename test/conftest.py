import os
import pathlib

import pytest

pytest_plugins = "sphinx.testing.fixtures"

os.environ["_LUA_LS_FIX_FLAKY_ALIAS_TESTS"] = ""


@pytest.fixture(scope="session")
def rootdir():
    return pathlib.Path(__file__).parent.resolve() / "roots"


"""

TODO:

options
    lua_ls_min_version
        fails to build
    lua_ls_auto_install
        fails to build
    lua_ls_project_root
        outside of srcdir
    lua_ls_default_options
        no override from object
        override from object
    lua_ls_apidoc_roots
        enabled
        override options
        override max depth
        override ignored modules
    lua_ls_apidoc_default_options
        enabled
        override options
    lua_ls_apidoc_max_depth
    lua_ls_apidoc_ignored_modules
        simple
        glob
autodoc
    !doc options
        applied
        override defaults
        unknown option
        invalid option
    !doctype options
        override doctype when compatible
        fail when incompatible
    nesting
        recursive apply default options
autoindex
    not found
    not a module
    relative path
rebuild
    no changes
    on change to dependent file
    on new file
    apidoc removes files

"""
