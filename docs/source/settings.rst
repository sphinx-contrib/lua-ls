Settings
========

.. py:data:: lua_ls_project_root
   :type: str

   Path to a directory with ``.luarc.json`` file, relative to the location
   of ``conf.py``. Lua Language Server will be launched from here.

.. py:data:: lua_ls_backend
   :type: str

   Controls which lua analyzer is used. Can be either ``"emmylua"`` or ``"luals"``.

.. py:data:: lua_ls_auto_install
   :type: bool

   Controls whether Sphinx-LuaLs should try downloading lua analyzer (LuaLs or EmmyLua)
   from github if it isn't installed already. This setting is enabled by default.

   .. note::

      At the moment, automatic installation does not work for EmmyLua.

.. py:data:: lua_ls_auto_install_location
   :type: str

   Controls where the lua analyzer will be installed. By default,
   Sphinx-LuaLs uses a folder in the temporary directory provided by the os.
   For unix, it is ``/tmp/python_lua_ls_cache``.

.. py:data:: lua_ls_min_version
   :type: str

   Controls the minimal version of the used lua analyzer.

.. py:data:: lua_ls_default_options
   :type: dict[str, str]

   Default values for directive options. You can override member ordering
   or enable documentation for undocumented or private members from here.
   For example:

   .. code-block:: python

      lua_ls_default_options = {
          # Enable documentation for object's members.
          # Empty string means documenting all members with non-empty description.
          "members": "",
          # Set ordering of automatically generated content to alphabetical.
          "member-order": "alphabetical",
          # And so on...
      }

.. py:data:: lua_ls_lua_version
   :type: str

   Controls which documentation version is used when linking
   to standard library functions. Does not otherwise affect parsing or generation.

   Can be either ``"5.1"``, ``"5.2"``, ``"5.3"``, ``"5.4"``, or ``"jit"``.

   By default, Sphinx-LuaLs will choose this setting
   based on your `.emmyrc.json`/`.luarc.json` file.

.. py:data:: lua_ls_apidoc_roots
   :type: dict[str, str | dict[str, Any]]

   Roots for `apidoc <automatic generation of API files>`_. Keys are full module names
   that should be generated, and values are directories (relative to the location
   of ``conf.py``) where ``.rst`` files are placed.

   Additionally, you can override other apidoc settings for each root. For this,
   make root's value a dictionary with keys ``path``,
   :py:data:`max_depth <lua_ls_apidoc_max_depth>`,
   :py:data:`options <lua_ls_apidoc_default_options>`,
   :py:data:`ignored_modules <lua_ls_apidoc_ignored_modules>`,
   and :py:data:`ignored_modules <lua_ls_apidoc_format>`:

   .. code-block:: python

      lua_ls_apidoc_roots = {
          "moduleName": {
              "path": "moduleDirectory",
              "max_depth": 2,
              "options": {
                  "undoc-members": "",
              },
              "format": "md",
          },
      }

.. py:data:: lua_ls_apidoc_default_options
   :type: dict[str, str]

   Default options for objects documented via apidoc. Override
   :py:data:`lua_ls_default_options`.

.. py:data:: lua_ls_apidoc_max_depth
   :type: int

   Maximum nesting level for files. Submodules that are deeper than this level
   will not get their own file, and instead will be generated inline.

   Default value is ``4``.

.. py:data:: lua_ls_apidoc_ignored_modules
   :type: list[str]

   List of full submodule names that should be ignored while generating APIs.
   Submodules can contain :py:mod:`fnmatch` style globs.

   For example, the following setting

   .. code-block:: python

      lua_ls_apidoc_roots = {
          "moduleName": "moduleDirectory",
      }

      lua_ls_apidoc_ignored_modules = [
         "moduleName.submoduleName"
      ]

   will generate API for module ``moduleName``, but will not include
   ``moduleName.submoduleName``.

.. py:data:: lua_ls_apidoc_format
   :type: str

   Format for generated files. Can be either ``"rst"`` or ``"md"``.

.. py:data:: lua_ls_project_directories
   :type: list[str]

   By default, Lua Language Server documents all files
   from :py:data:`lua_ls_project_root`. You can change that by providing
   a list or directories that should be documented. Autodoc will launch
   Lua Language Server using each of these directories as a target. The path
   is relative to :py:data:`lua_ls_project_root`.

   .. deprecated:: 2.1.0

      This option will be removed in *3.0.0*.

   .. note::

      This option does nothing when using EmmyLua.
