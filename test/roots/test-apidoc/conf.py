project = "Test"
copyright = "test"
author = "test"

extensions = ["sphinx_lua_ls", "myst_parser"]
lua_ls_backend = "emmylua"
lua_ls_project_root = "lua"
lua_ls_apidoc_format = "rst"
lua_ls_apidoc_roots = {"mod": "api"}
lua_ls_apidoc_default_options = {
    "globals": "",
}
lua_ls_apidoc_separate_members = True
