import datetime

import sphinx_lua_ls

project = "Sphinx-LuaLs"
copyright = f"{datetime.date.today().year}, Tamika Nomara"
author = "Tamika Nomara"
release = version = sphinx_lua_ls.__version__

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.githubpages",
    "sphinx.ext.intersphinx",
    "sphinx_design",
    "sphinx_lua_ls",
    "myst_parser",
]

templates_path = ["_templates"]
exclude_patterns = []

primary_domain = "lua"
default_role = "lua:obj"

lua_ls_project_root = "example"
lua_ls_backend = "emmylua"

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "sphinx": ("https://www.sphinx-doc.org/", None),
}

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_extra_path = ["_extra/robots.txt"]
html_theme_options = {
    "source_repository": "https://github.com/taminomara/sphinx-lua-ls",
    "source_branch": "main",
    "source_directory": "docs/source",
}


def setup(app):
    from myst_parser._docs import MystLexer

    app.add_lexer("myst", MystLexer)
