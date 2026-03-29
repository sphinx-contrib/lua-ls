Troubleshooring
===============


Autodoc can't fund a module or object
-------------------------------------

1.  Set ``lua_ls_verbose = True`` in ``conf.py`` and run build with ``-E`` (``make html O="-E"``).

#.  Search build log for record ``Lua analysis finished. Found objects:`` and see
    if object that can't be found appears in the object tree.

#.  If it's there, check spelling and full path of the object. Error message will contain
    all candidate paths that Sphinx-LuaLs tried when resolving it.

#.  If it's not there, check your documentation markup, EmmyLua/LuaLs settings,
    and project paths and directories:

.. tab-set::
    :sync-group: backend

    .. tab-item:: EmmyLua
        :sync: emmylua

        a.  Check that :py:data:`lua_ls_project_root` and :py:data:`lua_ls_project_directories`
            point to the right places.

            You can see how Sphinx-LuaLs launched language server by grepping build
            log for message ``running lua-language-server with args``.

        #.  Make sure that you have an explicit return at the end of a module.

            If your module only sets global variables, return an empty table from it:

            .. code-blick:: lua

                -- mod.lua

                --- Module documentation.
                return {}

        #.  Alternatively, if your module exports a global variable with the same name,
            make sure to set its doctype:

            .. code-blick:: lua

                -- mod.lua

                --- Module documentation.
                ---
                --- @doctype module
                mod = {
                    -- Module contents.
                }

        #.  Make sure that your project directories are listed in ``.emmyrc.json``
            under ``workspace.workspaceRoots`` and not ``workspace.library``.

    .. tab-item:: LuaLs
        :sync: luals

        a.  Check that :py:data:`lua_ls_project_root` and :py:data:`lua_ls_project_directories`
            point to the right places.

            You can see how Sphinx-LuaLs launched language server by grepping build
            log for message ``running lua-language-server with args``.

        #.  Make sure that you've created a class named after your module, and set its
            doctype:

            .. code-blick:: lua

                -- mod.lua

                --- Module documentation.
                ---
                --- !doctype module
                --- @class mod
