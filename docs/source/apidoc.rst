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

.. code-block:: python

   lua_ls_apidoc_roots = {
       "moduleName": "moduleDirectory",
   }

Upon start, Sphinx-LuaLs will recursively create ``.rst`` files in ``moduleDirectory``.
``moduleDirectory/index.rst`` will contain reference for ``moduleName``.
Then, for every submodule of ``moduleName``, there will be another ``.rst`` generated.

.. warning::

   Do not add any other files to ``moduleDirectory``, otherwise they will be deleted.

   It is best to add ``moduleDirectory`` to your ``.gitignore`` file.

Don't forget to include ``moduleDirectory/index.rst`` into a table of contents
in your main ``index.rst``.
