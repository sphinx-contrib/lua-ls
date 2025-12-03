project = "Test"
copyright = "test"
author = "test"

extensions = ["sphinx_lua_ls"]
lua_ls_backend = "luals"
lua_ls_project_root = "lua"

# Note: 3.16 is currently broken,
# see https://github.com/LuaLS/lua-language-server/issues/3301
lua_ls_max_version = "3.15.0"
