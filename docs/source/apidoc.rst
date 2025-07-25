Generating API references
=========================

:rst:dir:`lua:autoobject` allows recursively generating documentation,
however it all ends up on a single page. If you want to give a separate page
for every module, you'll need to create multiple ``.rst`` or ``.md`` files.
Fortunately, Sphinx-LuaLs can do this for you.

Add :py:data:`lua_ls_apidoc_roots` option to the ``conf.py``, and provide a mapping
from module names to directories (relative to the location of ``conf.py``)
where generated ``.rst`` or ``.md`` files should be placed.

For example, to generate API reference for module ``moduleName``
in directory ``moduleDirectory``, add the following:

.. tab-set::
   :sync-group: lang

   .. tab-item:: RST
      :sync: rst

      .. code-block:: python

         lua_ls_apidoc_roots = {
            "moduleName": "moduleDirectory",
         }

   .. tab-item:: Markdown
      :sync: md

      .. code-block:: python

         lua_ls_apidoc_format = "md"
         lua_ls_apidoc_roots = {
            "moduleName": "moduleDirectory",
         }

Upon start, Sphinx-LuaLs will recursively create ``.rst`` or ``.md`` files
in ``moduleDirectory``. ``moduleDirectory/index`` will contain reference for
``moduleName``. Then, for every submodule of ``moduleName``, there will be another
``.rst`` or ``.md`` generated.

.. warning::

   Do not add any other files to ``moduleDirectory``, otherwise they will be deleted.

   It is best to add ``moduleDirectory`` to your ``.gitignore`` file.

Don't forget to include ``moduleDirectory/index`` into a table of contents
in your main ``index.rst``/``index.md``.

Settings
--------

You can override default settings using :py:data:`lua_ls_apidoc_max_depth`,
:py:data:`lua_ls_apidoc_default_options`,
:py:data:`lua_ls_apidoc_ignored_modules`,
:py:data:`lua_ls_apidoc_separate_members`,
and :py:data:`lua_ls_apidoc_format`;
see `settings <settings.html>`_ for more info.

For example, here's how to enable documentation for members without description,
protected members, and global variables:

.. code-block:: python

   lua_ls_apidoc_default_options = {
      # Document members without description.
      "undoc-members": "",
      # Document protected members.
      "protected-members": "",
      # Document module's global variables.
      "globals": "",
      # Override default ordering.
      "member-order": "alphabetical",
      "module-member-order": "groupwise",
      # Add table with inherited members for classes.
      "inherited-members-table": "",
   }
