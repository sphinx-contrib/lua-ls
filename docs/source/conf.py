import datetime

import sphinx_luals

project = 'Sphinx-LuaLS'
copyright = f"{datetime.date.today().year}, Tamika Nomara"
author = 'Tamika Nomara'
release = version = sphinx_luals.__version__

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.githubpages",
    "sphinx_design",
    "sphinx_luals",
]

templates_path = ['_templates']
exclude_patterns = []

primary_domain = "lua"
default_role = "lua:obj"

luals_project_root = "../example"

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "pydata_sphinx_theme"
html_extra_path = ["_extra/robots.txt"]
html_theme_options = {
    "use_edit_page_button": True,
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/taminomara/sphinx-luals",
            "icon": "fa-brands fa-square-github",
            "type": "fontawesome",
        }
   ]
}
html_context = {
    "github_user": "taminomara",
    "github_repo": "sphinx-luals",
    "github_version": "main",
    "doc_path": "docs/source",
}
