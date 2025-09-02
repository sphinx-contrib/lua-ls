Cross-referencing objects
=========================

.. rst:role:: lua:obj
              lua:lua

   You can reference any documented object through the :rst:role:`lua:obj` role.

   Given an object path, Sphinx-LuaLs will first search for an object with this path
   in the outer-most class, then in the current module, and finally
   in the global namespace.

   So, if you reference an object ``Sound.id`` from documentation of a class
   ``SoundBoard.Helper`` located in the module ``soundboard``, Lua domain will
   first check ``soundboard.SoundBoard.Helper.Sound.id``,
   then ``soundboard.Sound.id``, and finally ``Sound.id``.

   If you specify a fully qualified object name, and would like to hide its prefix,
   you can add a tilde (``~``) to the object's path:

   .. tab-set::
      :sync-group: lang

      .. tab-item:: RST
         :sync: rst

         .. code-block:: rst

            Reference to a :lua:obj:`~logging.Logger`.

      .. tab-item:: Markdown
         :sync: md

         .. code-block:: myst

            Reference to a {lua:obj}`~logging.Logger`.

   .. dropdown:: Example output

      Reference to a :lua:obj:`~logging.Logger`.

.. rst:role:: lua:func
              lua:data
              lua:const
              lua:class
              lua:alias
              lua:enum
              lua:meth
              lua:attr
              lua:mod

   These are additional roles that you can use to reference a Lua object.

   Lua domain does not allow having multiple objects with the same full name.
   Thus, all of these roles work exactly the same as :rst:role:`lua:obj`.
   The only difference is that they will warn you if the type of the referenced object
   doesn't match the role's type.
