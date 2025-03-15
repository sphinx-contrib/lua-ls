import datetime

import sphinx_lua_ls

project = 'Sphinx-LuaLS'
copyright = f"{datetime.date.today().year}, Tamika Nomara"
author = 'Tamika Nomara'
release = version = sphinx_lua_ls.__version__

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.githubpages",
    "sphinx_design",
    "sphinx_lua_ls",
]

templates_path = ['_templates']
exclude_patterns = []

primary_domain = "lua"
default_role = "lua:obj"

lua_ls_project_root = "../example"

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_extra_path = ["_extra/robots.txt"]
html_theme_options = {
    "source_repository": "https://github.com/taminomara/sphinx-lua-ls",
    "source_branch": "main",
    "source_directory": "docs/source",
}
