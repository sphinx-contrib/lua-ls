Sphinx-LuaLS
============

Sphinx-LuaLS features domain for `Lua`_ and automatic documentation generator
based on `Lua Language Server`_.

.. _Lua: https://lua.org
.. _Lua Language Server: https://lua_ls.github.io/

See an example output: `logging`.

Installation
------------

You'll need a Python installation and a Sphinx project to start with Sphinx-LuaLS.

.. dropdown:: If you're new to Python and Sphinx

   1. **Installing Python**

      We recommend using `PyEnv`_ to manage python installations on your system.

      Similar to LuaRocks, it creates executables for Python, Pip (Package Installer
      for Python), and other tools. When run, these executables determine which
      Python environment to use, and invoke the appropriate command.

      Following its `installation`_ guide, install PyEnv, configure your shell,
      and install build dependencies.

      Make sure that PyEnv shims are in your path by checking them with ``which``:

      .. code-block:: console

         $ which python
         /home/user/.pyenv/shims/python
         $ which pip
         /home/user/.pyenv/shims/pip

      Once ready, you can install Python 3.12:

      .. code-block:: console

         $ pyenv install 3.12.2

      To avoid installing Python packages globally, we recommend using virtual
      environments. It is a good practice to create a separate environment
      for each project:

      .. code-block:: console

         $ pyenv virtualenv 3.12.2 my-project

      Once a new environment is created, you'll need to activate it. Navigate to your
      project directory and run the following command:

      .. code-block:: console

         $ pyenv local my-project

      This will create a file called ``.python-version``. Every time you run an executable
      that was installed by PyEnv, it will look for a ``.python-version`` file
      to determine which environment to use. Thus, when running Python from your project's
      directory, it will always use the right virtual environment.

   2. **Installing Sphinx**

      You can now install Sphinx using Pip:

      .. code-block:: console

         $ pip install sphinx

      To make your life easier, you can create a file named ``requirements.txt``,
      and list all of the dependencies there:

      .. code-block:: console

         $ echo "sphinx~=8.0" > requirements.txt

      Now, you can install all dependencies at once:

      .. code-block:: console

         $ pip install -r requirements.txt

   3. **Creating a Sphinx project**

      Sphinx comes with a tool for creating new projects. Make a directory for your
      documentation and run the ``sphinx-quickstart`` command in it:

      .. code-block:: console

         $ mkdir docs/
         $ cd docs/
         $ sphinx-quickstart

      Once finished, you'll see several files generated. ``Makefile`` contains commands
      to build documentation, ``conf.py`` contains configuration, and ``index.rst``
      is the main document.

      Try building documentation and see the results:

      .. code-block:: console

         $ make html
         $ open build/html/index.html

.. _PyEnv: https://github.com/pyenv/pyenv
.. _installation: https://github.com/pyenv/pyenv#installation

Install ``sphinx-lua-ls`` using Pip:

.. code-block:: console

   $ pip install sphinx-lua-ls

Add it to the ``extensions`` list in your ``conf.py``,
and specify the location of your Lua project:

.. code-block:: python

   extensions = [
       "sphinx_lua_ls",
   ]

   # Path to the folder containing the `.luarc.json` file,
   # relative to the directory with `conf.py`.
   lua_ls_project_root = "../"

If you plan to use Markdown in code comments, install the `MySt`_ plugin for Sphinx.

.. _MySt: https://myst-parser.readthedocs.io/en/latest/index.html

Quickstart
----------

Use :rst:dir:`lua:module` to indicate which module you're documenting.
After it, use :rst:dir:`lua:data`, :rst:dir:`lua:function`, :rst:dir:`lua:class`,
and others to document module's contents.

.. code-block:: rst

   .. lua:module:: soundboard

   .. lua:class:: Sound

      A sound that can be played by the sound board.

      .. lua:staticmethod:: new(id: string) -> sound: Sound

         Create a new sound.

         :param string id: id of a sound.
         :return Sound sound: a new class instance.

      .. lua:method:: play(self: Sound)

         Plays the sound.

.. dropdown:: Example output

   .. lua:module:: soundboard

   .. lua:class:: Sound

      A sound that can be played by the sound board.

      .. lua:staticmethod:: new(id: string) -> sound: Sound

         Create a new sound.

         :param string id: id of a sound.
         :return Sound sound: a new class instance.

      .. lua:method:: play(self: Sound)

         Plays the sound.

   .. lua:currentmodule:: None

Reference documented entities using the :rst:role:`lua:data`, :rst:role:`lua:func`,
and :rst:role:`lua:class` roles:

.. code-block:: rst

   Here's a reference to the :lua:class:`soundboard.Sound` class.

.. dropdown:: Example output

   Here's a reference to the :lua:class:`soundboard.Sound` class.

Use :rst:role:`lua:autoobject` to extract documentation from source code.
Its options are similar to the ones used by python ``autodoc``:

.. code-block:: rst

   .. lua:autoobject:: logging.Logger

.. dropdown:: Example output

   .. lua:autoobject:: logging.Logger
      :no-index:

Declaring objects
-----------------

.. rst:directive:: .. lua:data:: name: type
                   .. lua:const:: name: type
                   .. lua:attribute:: name: type

   Directives for documenting variables. Accepts name of the variable,
   and an optional type:

   .. code-block:: rst

      .. lua:data:: name: string

         Person's name.

   .. dropdown:: Example output

      .. lua:data:: name: string
         :no-index:

         Person's name.

.. rst:directive:: .. lua:table:: name

   Directive for documenting tables that serve as namespaces.
   It works like :rst:dir:`data`, but can contain nested members.

.. rst:directive:: .. lua:function:: name(param: type) -> type
                   .. lua:method:: name(param: type) -> type
                   .. lua:classmethod:: name(param: type) -> type
                   .. lua:staticmethod:: name(param: type) -> type

   Directives for documenting functions and class methods. Accepts function name,
   optional parenthesized list of parameters, and an optional return type:

   .. code-block:: rst

      .. lua:function:: doABarrelRoll(times: integer) -> success: boolean

         Does a barrel roll given amount of times. Returns ``true`` if successful.

   .. dropdown:: Example output

      .. lua:function:: doABarrelRoll(times: integer) -> success: boolean
         :no-index:

         Does a barrel roll given amount of times. Returns ``true`` if successful.

.. rst:directive:: .. lua:class:: name: bases

   For documenting classes and metatables. Accepts a class name and an optional list
   of base classes:

   .. code-block:: rst

      .. lua:class:: Logger: LogFilter, LogSink

         The user-facing interface for logging messages.

   .. dropdown:: Example output

      .. lua:class:: Logger: LogFilter, LogSink
         :no-index:

         The user-facing interface for logging messages.

.. rst:directive:: .. lua:alias:: name = type

   For documenting type aliases. Accepts name of the alias and its type:

   .. code-block:: rst

      .. lua:alias:: LogLevel = integer

         Verbosity level of a log message.

   .. dropdown:: Example output

      .. lua:alias:: LogLevel = integer
         :no-index:

         Verbosity level of a log message.

.. rst:directive:: .. lua:module:: name

   Specifies beginning of a module. Other objects declared after this directive
   will be automatically attached to this module.

   This directive doesn't accept any content, it just creates an anchor.

   Modules are something you can `require`. If you need to document a namespace
   inside of a module, use a :rst:dir:`lua:table` instead.

.. rst:directive:: .. lua:currentmodule:: name

   Switches current module without making an index entry or an anchor.
   If ``name`` is ``None``, sets current module to be the global namespace.

.. note::

   **Setting the default domain**

   You can avoid prefixing directives and roles with ``lua:`` if you set Lua
   as your default domain. For this, declare ``primary_domain`` in your ``conf.py``:

   .. code-block:: python

      primary_domain = "lua"

All directives that document Lua objects accept the standard parameters:

.. rst:directive:option:: no-index

   Render the documentation, but don't add it to the index
   and don't create anchors. You will not be able to reference
   un-indexed objects.

.. rst:directive:option:: private
                          protected
                          package
                          virtual
                          abstract
                          async
                          global

   Adds a corresponding annotation before object's name:

   .. code-block:: rst

      .. lua:function:: fetch(url: string) -> code: integer, content: string?
         :async:

         Fetches content from the given url.

   .. dropdown:: Example output

      .. lua:function:: fetch(url: string) -> code: integer, content: string?
         :async:
         :no-index:

         Fetches content from the given url.

.. rst:directive:option:: annotation

   Allows adding custom short annotations.

.. rst:directive:option:: deprecated

   Marks object as deprecated in index and when cross-referencing.
   This will not add any text to the documented object, you'll need
   to use the ``deprecated`` directive for this:

   .. code-block:: rst

      .. lua:data:: fullname: string
         :deprecated:

         Person's full name.

         .. deprecated:: 3.2

            Use ``name`` and ``surname`` instead.

   .. dropdown:: Example output

      .. lua:data:: fullname: string
         :deprecated:
         :no-index:

         Person's full name.

         .. deprecated:: 3.2

            Use ``name`` and ``surname`` instead.

.. rst:directive:option:: synopsis

   Allows adding a small description that's reflected
   in the :rst:dir:`lua:autoindex` output.

.. rst:directive:option:: module

   Allows overriding current module for a single object. This is useful
   for documenting global variables that are declared in a module.

   This option should not be used inside of a class or an alias.

Cross-referencing objects
-------------------------

.. rst:role:: lua:obj

   You can reference any documented object through the :rst:role:`lua:obj` role.

   Given an object path, Lua domain will first search for an object with this path
   in the outer-most class, then in the current module, and finally
   in the global namespace.

   So, if you reference an object ``Sound.id`` from documentation of a class
   ``SoundBoard.Helper`` located in the module ``soundboard``, Lua domain will
   first check ``soundboard.SoundBoard.Helper.Sound.id``,
   then ``soundboard.Sound.id``, and finally ``Sound.id``.

   If you specify a fully qualified object name, and would like to hide its prefix,
   you can add a tilde (``~``) to the object's path:

   .. code-block:: rst

      Reference to a :lua:obj:`~logging.Logger`.

   .. dropdown:: Example output

      Reference to a :lua:obj:`~logging.Logger`.

.. rst:role:: lua:func
              lua:data
              lua:const
              lua:class
              lua:alias
              lua:meth
              lua:attr
              lua:mod

   These are additional roles that you can use to reference a Lua object.

   Lua domain does not allow having multiple objects with the same full name.
   Thus, all of these roles work exactly the same as :rst:role:`lua:obj`.
   The only difference is that they will warn you if the type of the referenced object
   doesn't match the role's type.

.. note::

   **Setting the default role**

   When you use backticks without explicitly specifying a role, Sphinx uses the default
   role to resolve it. Setting :rst:role:`lua:obj` as the default
   role can reduce boilerplate in documentation.

   In ``conf.py``, declare ``default_role``:

   .. code-block:: python

      default_role = "lua:obj"

   Now, you can reference any object with just backticks:

   .. code-block:: rst

      Reference to a `logging.Logger.info`.

   .. dropdown:: Example output

      Reference to a `logging.Logger.info`.

Autodoc directives
------------------

.. rst:directive:: .. lua:autoobject:: name

   You can automatically generate documentation for any object by invoking
   the :rst:dir:`lua:autoobject` directive.

   Tables are exported as :rst:dir:`data` by default, meaning that their contents
   are not documented.

   To enable documentation within a table, annotate is as a class.
   You can change how autodoc infers its type by adding a ``!doctype`` comment.

   Thus, a typical Lua module will look like this:

   .. code-block:: lua

      --- This is a module. Notice that we've declared it as a class
      --- and added a `doctype`.
      ---
      --- !doctype module
      --- @class library
      local library = {}

      --- Nested namespaces should also be declared as classes.
      ---
      --- !doctype table
      --- @class library.namespace
      library.namespace = {}

      --- Other objects are documented as usual.
      function library.foo() end

      --- And so on...
      function library.namespace.bar() end

      return library

   .. note::

      By default, autodoc will parse object comments as ReStructured Text,
      not as MarkDown. If you plan to use Markdown in code comments,
      install the `MySt`_ plugin for Sphinx and invoke include
      :rst:dir:`lua:autoobject` from a markdown file.

      Make sure to separate comment markers from documentation with a space.
      Otherwise, autodoc will not be able to tell your comments apart from content
      automatically generated by Lua Language Server:

      .. code-block:: lua

         --- This is OK: separated by a space.
         local x = 0;

         ---This is NOT OK: no separation.
         local x = 0;

   .. warning::

      Currently, Lua Language Server does not export all available information.

      1. ``@see`` markers can sometimes be broken. We recommend using
         the :rst:dir:`seealso` directive instead.

      2. ``@deprecated`` markers do not add any note to the documentation.
         We recommend providing an explicit message
         with the ``deprecated`` directive.

      3. ``@nodiscard`` and ``@operator`` markers are not exported.

      4. Export of enums (``@enum``) is completely broken.
         We recommend using ``@alias`` instead:

         .. code-block:: lua

            --- Instead of enums, we use aliases.
            ---
            --- .. lua:data:: Debug
            ---
            ---    Document alias members in its body.
            ---
            --- And so on...
            ---
            --- @alias LogLevel integer
            LogLevel = {
               Debug = 1,
               -- ...
            }

   :rst:dir:`lua:autoobject` supports same settings as other lua directives,
   as well as some additional ones:

   .. rst:directive:option:: members

      If enabled, autodoc will also document object's members. You can pass a list
      of comma-separated names to specify which members should be documented.
      Otherwise, this option will document all public non-special members
      which have a description.

   .. rst:directive:option:: undoc-members

      Include undocumented members to the object's description. By default,
      they are skipped even if :rst:dir:`members` is passed.

      Accepts a comma-separated list of names; if list is empty,
      adds all undoc members.

   .. rst:directive:option:: private-members
                             protected-members
                             package-members

      Include non-public members to the object's description.

      Accepts a comma-separated list of names; if list is empty,
      adds all non-public members.

   .. rst:directive:option:: special-members

      Include special members to the object's description. That is, generate
      documentation for members whose names start with double underscore.

      Accepts a comma-separated list of names; if list is empty,
      adds all special members.

   .. rst:directive:option:: inherited-members

      For classes, includes members inherited from base classes.

      Accepts a comma-separated list of names; if list is empty,
      adds all inherited members.

   .. rst:directive:option:: exclude-members

      A comma-separated list of members that should not be documented.

   .. rst:directive:option:: recursive

      If enabled, autodoc will recursively generate documentation
      for all objects nested within the root. That is, object's members,
      their members, and so on.

      If :rst:dir:`lua:autoobject:undoc-members`,
      :rst:dir:`lua:autoobject:private-members`,
      :rst:dir:`lua:autoobject:special-members`,
      or :rst:dir:`lua:autoobject:inherited-members`
      are given as flags, they are propagated to all documented objects.

      If they're given as list, they are not propagated.

      Options from :py:data:`lua_ls_default_options` are applied to all recursively
      documented objects.

   .. rst:directive:option:: member-order

      Controls how members are sorted. There are three options available:

      - ``alphabetical``: members are sorted in lexicographical order of their names;

      - ``groupwise``: members are grouped by their type. Within each group, they are
        ordered by name;

      - ``bysource``: members are sorted in the same order as they appear in code.
        This is the default option.

      .. warning::

         Currently, Lua Language Server does not export position information
         for enums (``@enum``). If ordering by source, enums will be placed
         at the end of the documentation.

   .. rst:directive:option:: module-member-order

      Overrides :rst:dir:`lua:autoobject:member-order` for modules.

   .. rst:directive:option:: title

      For modules, controls whether a title is inserted between module description
      and documentation of its members.

   .. rst:directive:option:: index-table

      Adds :rst:dir:`lua:autoindex` to the toplevel module.

   .. rst:directive:option:: index-title

      Allows overriding title of the :rst:dir:`lua:autoindex` section.

.. rst:directive:: .. lua:autoindex:: name

   Creates a table that references all documented objects in the module ``name``.
   This is useful for creating module's table of contents.

   Module name must be absolute, even if this directive appears after
   :rst:dir:`lua:module`.

Controlling generation from code comments
-----------------------------------------

When using :rst:dir:`lua:autoobject` in recursive mode, it is sometimes necessary
to override its options for some objects. To do this, you can include specially
formatted comments to your documentation.

To override any :rst:dir:`lua:autoobject` setting for a particular object,
use ``!doc`` comments. For example, here we enable :rst:dir:`lua:autoobject:special-members`
and exclude ``__tostring`` for class ``Foo``:

.. code-block:: lua

   --- Some class documentation...
   ---
   --- !doc special-members
   --- !doc exclude-members: __tostring
   --- @class Foo

You can also specify which type of object is being documented by using
a ``!doctype`` comment. For example, here we use ``!doctype const`` to indicate
that a certain variable should be documented as :rst:dir:`lua:const`:

.. code-block:: lua

   --- Some const documentation...
   ---
   --- !doctype const
   --- @type string
   foo = "bar!"

.. _apidoc:

Automatic API reference generation
----------------------------------

:rst:dir:`lua:autoobject` allows recursively generating documentation,
however it all ends up on a single page. If you want to give a separate page
for every module, you'll need to create multiple ``.rst`` files.
Fortunately, Lua autodoc can do this for you.

Add :py:data:`lua_ls_apidoc_roots` option to the ``conf.py``, and provide a mapping
from module names to directories (relative to the location of ``conf.py``)
where generated ``.rst`` files should be placed.

For example, to generate API reference for module ``moduleName``
in directory ``moduleDirectory``, add the following:

.. code-block:: python

   lua_ls_apidoc_roots = {
       "moduleName": "moduleDirectory",
   }

Upon start, autodoc will recursively create ``.rst`` files in ``moduleDirectory``.
``moduleDirectory/index.rst`` will contain reference for ``moduleName``.
Then, for every submodule of ``moduleName``, there will be another ``.rst`` generated.

.. warning::

   Do not add any other files to ``moduleDirectory``, otherwise they will be deleted.

   It is best to add ``moduleDirectory`` to your ``.gitignore`` file.

Don't forget to include ``moduleDirectory/index.rst`` into a table of contents
in your main ``index.rst``.

Settings
--------

.. py:data:: lua_ls_project_root: str

   Path to a directory with ``.luarc.json`` file, relative to the location
   of ``conf.py``. Lua Language Server will be launched from here.

.. py:data:: lua_ls_project_directories: list[str]

   By default, Lua Language Server documents all files
   from :py:data:`lua_ls_project_root`. You can change that by providing
   a list or directories that should be documented. Autodoc will launch
   Lua Language Server using each of these directories as a target. The path
   is relative to :py:data:`lua_ls_project_root`.

.. py:data:: lua_ls_auto_install: bool

   Controls whether autodoc should try downloading Lua Language Server from github
   if it isn't installed already. This setting is enabled by default.

.. py:data:: lua_ls_auto_install_location: str

   Controls where the Lua Language Server will be installed. By default,
   autodoc uses a folder in the temporary directory provided by the os.
   For unix, it is ``/tmp/python_lua_ls_cache``.

.. py:data:: lua_ls_min_version: str

   Controls the minimal version of Lua Language Server used.

.. py:data:: lua_ls_default_options: dict[str, str]

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

.. py:data:: lua_ls_lua_version: str

   Controls which documentation version is used when linking
   to standard library functions. Does not otherwise affect parsing or generation.

.. py:data:: lua_ls_apidoc_roots: dict[str, str | dict[str, Any]]

   Roots for `apidoc <automatic generation of API files>`_. Keys are full module names
   that should be generated, and values are directories (relative to the location
   of ``conf.py``) where ``.rst`` files are placed.

   Additionally, you can override other apidoc settings for each root. For this,
   make root's value a dictionary with keys ``path``,
   :py:data:`max_depth <lua_ls_apidoc_max_depth>`,
   :py:data:`options <lua_ls_apidoc_default_options>`,
   and :py:data:`ignored_modules <lua_ls_apidoc_ignored_modules>`:

   .. code-block:: python

      lua_ls_apidoc_roots = {
          "moduleName": {
              "path": "moduleDirectory",
              "max_depth": 2,
              "options": {
                  "undoc-members": "",
              }
          },
      }

.. py:data:: lua_ls_apidoc_default_options: dict[str, str]

   Default options for objects documented via apidoc. Override
   :py:data:`lua_ls_default_options`.

.. py:data:: lua_ls_apidoc_max_depth: int

   Maximum nesting level for files. Submodules that are deeper than this level
   will not get their own file, and instead will be generated inline.

   Default value is ``4``.

.. py:data:: lua_ls_apidoc_ignored_modules: list[str]

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

Example output
--------------

This output is generated with the following directive:

.. code-block:: rst

   .. lua:autoobject:: logging
      :members:
      :recursive:

.. lua:autoobject:: logging
   :members:
   :recursive:

Indices and tables
------------------

* :ref:`genindex`
* :ref:`search`
