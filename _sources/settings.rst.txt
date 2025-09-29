Settings
========

.. py:data:: lua_ls_project_root
   :type: str

   Path to a directory with ``.luarc.json`` file, relative to the location
   of ``conf.py``. Lua analyzer will be launched from here.

.. py:data:: lua_ls_project_directories
   :type: list[str]

   List of directories where lua analyzer will run,
   relative to :py:data:`lua_ls_project_root`.

   By default, consists of a single :py:data:`lua_ls_project_root`.

.. py:data:: lua_ls_backend
   :type: str

   Controls which lua analyzer is used. Can be either ``"emmylua"`` or ``"luals"``.

.. py:data:: lua_ls_auto_install
   :type: bool

   Controls whether Sphinx-LuaLs should try downloading lua analyzer (LuaLs or EmmyLua)
   from github if it isn't installed already. This setting is enabled by default.

.. py:data:: lua_ls_auto_install_location
   :type: str

   Controls where the lua analyzer will be installed. By default,
   Sphinx-LuaLs uses a folder in the temporary directory provided by the os.
   For unix, it is ``/tmp/python_lua_ls_cache``.

.. py:data:: lua_ls_min_version
   :type: str

   Controls the minimum version of the used lua analyzer.

   Analyzer version should be greater than or equal to this version.

   For LuaLs, default value is ``3.0.0``, for EmmyLua it's ``0.11.0``.

.. py:data:: lua_ls_max_version
   :type: str | None

   Controls the maximum version of the used lua analyzer.

   Analyzer version should be strictly less than this version.

   For LuaLs, default value is ``4.0.0``, for EmmyLua it's ``2.0.0``.
   Use ``None`` to allow any version.

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

   If using defaults for the ``:members:``, ``:exclude-members:``, and other
   list options, setting the option on a directive will override the default.
   Instead, to extend the default list with the per-directive option,
   the list may be prepended with a plus sign (``+``), as follows:

   .. code-block:: rst

      .. lua:autoobject:: Noodle
         :members: eat
         :private-members: +_spicy, _garlickly

   Also, the defaults can be disabled per-directive with the negated form,
   ``:no-option:`` as an option of the directive:

   .. code-block:: rst

      .. lua:autoobject:: foo
         :no-undoc-members:

.. py:data:: class_default_function_name
   :type: str

   Allows specifying which class method represents a class constructor.

   Class constructors are documented separately, depending on
   :rst:dir:`lua:autoobject:class-doc-from`
   and :rst:dir:`lua:autoobject:class-signature` options.

   If using EmmyLua as lua analyzer, this option will be inferred from ``.emmyrc.json``.

.. py:data:: class_default_force_non_colon
   :type:

   If ``True``, Sphinx-LuaLs will remove ``self`` from class constructor's signature.

   If using EmmyLua as lua analyzer, this option will be inferred from ``.emmyrc.json``.

.. py:data:: class_default_force_return_self
   :type:

   If ``True``, Sphinx-LuaLs will replace class constructor's return type with ``self``.

   If using EmmyLua as lua analyzer, this option will be inferred from ``.emmyrc.json``.

.. py:data:: lua_ls_lua_version
   :type: str

   Controls which documentation version is used when linking
   to standard library functions. Does not otherwise affect parsing or generation.

   Can be either ``"5.1"``, ``"5.2"``, ``"5.3"``, ``"5.4"``, or ``"jit"``.

   By default, Sphinx-LuaLs will choose this setting
   based on your ``.emmyrc.json``/``.luarc.json`` file.

.. py:data:: lua_ls_apidoc_roots
   :type: dict[str, str | dict[str, Any]]

   Roots for `apidoc <apidoc.html>`_. Keys are full module names
   that should be generated, and values are directories (relative to the location
   of ``conf.py``) where ``.rst`` files are placed.

   Additionally, you can override other apidoc settings for each root. For this,
   make root's value a dictionary with keys ``path``,
   :py:data:`max_depth <lua_ls_apidoc_max_depth>`,
   :py:data:`options <lua_ls_apidoc_default_options>`,
   :py:data:`ignored_modules <lua_ls_apidoc_ignored_modules>`,
   :py:data:`separate_members <lua_ls_apidoc_separate_members>`,
   and :py:data:`format <lua_ls_apidoc_format>`:

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

.. py:data:: lua_ls_apidoc_separate_members
   :type: bool

   If set to ``True``, module members will be rendered on separate pages.

   .. warning::

      **Windows users**

      This option might not work correctly on case-insensitive file systems.

      It will generate a separate file for every member of a module;
      if there are members that only differ in case (i.e. ``Class`` vs ``class``),
      one of them will overwrite the file for another.

      If you're on Windows, and you experience difficulties because of it,
      `make your source and output directories case-insensitive`_
      and add the following hack to your ``conf.py``:

      .. code-block:: python

         # This evil code forces Python to treat
         # windows filenames as case-sensitive.
         import pathlib
         pathlib.PureWindowsPath._str_normcase = property(str)

.. _make your source and output directories case-insensitive:
   https://learn.microsoft.com/en-us/windows/wsl/case-sensitivity

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

.. py:data:: lua_ls_maximum_signature_line_length
   :type: int | None

   Controls maximum width after which long signatures will be wrapped.

   Default value is ``50``, which is suitable for most Sphinx themes.

   Setting this value to ``None`` will cause signature formatter
   to use Sphinx's global setting ``maximum_signature_line_length``.
   If ``maximum_signature_line_length`` is also ``None``,
   signature wrapping will be disabled.
