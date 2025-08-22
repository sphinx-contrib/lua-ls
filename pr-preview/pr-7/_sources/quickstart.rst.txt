Quickstart
==========

Declaring objects
-----------------

Use :rst:dir:`lua:module` to indicate which module you're documenting.
After it, use :rst:dir:`lua:data`, :rst:dir:`lua:function`, :rst:dir:`lua:class`,
and others to document module's contents.


.. tab-set::
   :sync-group: lang

   .. tab-item:: RST
      :sync: rst

      .. code-block:: rst

         .. lua:module:: soundboard

         .. lua:class:: Sound

            A sound that can be played by the sound board.

   .. tab-item:: Markdown
      :sync: md

      .. code-block:: myst

         ```{lua:module} soundboard
         ```

         ```{lua:class} Sound
         A sound that can be played by the sound board.
         ```

.. dropdown:: Example output

   .. lua:module:: soundboard

   .. lua:class:: Sound

      A sound that can be played by the sound board.

   .. lua:currentmodule:: None

.. _primary-domain:

.. tip::

   **Setting the primary domain**

   You can avoid prefixing directives and roles with ``lua:`` if you set Lua
   as your primary domain. For this, declare ``primary_domain`` in your ``conf.py``:

   .. code-block:: python

      primary_domain = "lua"

   This will significantly reduce boilerplate in documentation:

   .. tab-set::
      :sync-group: lang

      .. tab-item:: RST
         :sync: rst

         .. code-block:: rst

            Cross-reference to :lua:`Sound`.

            .. class:: Sound

               A sound that can be played by the sound board.

      .. tab-item:: Markdown
         :sync: md

         .. code-block:: myst

            Cross-reference to {lua}`Sound`.

            ```{class} Sound
            A sound that can be played by the sound board.
            ```

   .. dropdown:: Setting up primary domain in EmmyLua

      To enable accurate Go To Definition behavior for comments,
      add ``rstPrimaryDomain`` setting to your ``.emmyrc.json``:

      .. tab-set::
         :sync-group: lang

         .. tab-item:: RST
            :sync: rst

            .. code-block:: json

               {
                  "diagnostics": {
                     "enables": ["unknown-doc-tag"]
                  },
                  "doc": {
                     "knownTags": ["doctype", "doc"],
                     "syntax": "rst",
                     "rstPrimaryDomain": "lua"
                  }
               }

         .. tab-item:: Markdown
            :sync: md

            .. code-block:: json

               {
                  "diagnostics": {
                     "enables": ["unknown-doc-tag"]
                  },
                  "doc": {
                     "knownTags": ["doctype", "doc"],
                     "syntax": "myst",
                     "rstPrimaryDomain": "lua"
                  }
               }


Cross-referencing objects
-------------------------

Reference documented entities using the :rst:role:`lua:data`, :rst:role:`lua:func`,
and :rst:role:`lua:class` roles:


.. tab-set::
   :sync-group: lang

   .. tab-item:: RST
      :sync: rst

      .. code-block:: rst

         Here's a reference to the :lua:class:`soundboard.Sound` class.

   .. tab-item:: Markdown
      :sync: md

      .. code-block:: myst

         Here's a reference to the {lua:class}`soundboard.Sound` class.

.. dropdown:: Example output

   Here's a reference to the :lua:class:`soundboard.Sound` class.

.. _default-role:

.. tip::

   **Setting the default role**

   .. tab-set::
      :sync-group: lang

      .. tab-item:: RST
         :sync: rst

         When you use backticks without explicitly specifying a role, Sphinx uses the default
         role to resolve it. Setting :rst:role:`lua:obj` as the default
         role can reduce boilerplate in documentation.

         In ``conf.py``, declare ``default_role``:

         .. code-block:: python

            default_role = "lua:obj"

         Now, you can reference any object with just backticks:

         .. code-block:: rst

            Reference to a `logging.Logger.info`.

      .. tab-item:: Markdown
         :sync: md

         MySt plugin doesn't support default roles. However, if you set ``lua``
         as the :ref:`primary domain <primary-domain>`, you'll be able to use :rst:role:`lua:lua` like so:

         .. code-block:: myst

            Reference to a {lua}`logging.Logger.info`.

   .. dropdown:: Setting up default role in EmmyLua

      To enable accurate Go To Definition behavior for comments,
      add ``rstDefaultRole`` setting to your ``.emmyrc.json``:

      .. tab-set::
         :sync-group: lang

         .. tab-item:: RST
            :sync: rst

            .. code-block:: json

               {
                  "diagnostics": {
                     "enables": ["unknown-doc-tag"]
                  },
                  "doc": {
                     "knownTags": ["doctype", "doc"],
                     "syntax": "rst",
                     "rstDefaultRole": "lua:obj"
                  }
               }

         .. tab-item:: Markdown
            :sync: md

            .. code-block:: json

               {
                  "diagnostics": {
                     "enables": ["unknown-doc-tag"]
                  },
                  "doc": {
                     "knownTags": ["doctype", "doc"],
                     "syntax": "myst",
                     "rstDefaultRole": "lua:obj"
                  }
               }


Automatic documentation generation
----------------------------------

Use :rst:dir:`lua:autoobject` to extract documentation from source code.
Its options are similar to the ones used by python ``autodoc``:


.. tab-set::
   :sync-group: lang

   .. tab-item:: RST
      :sync: rst

      .. code-block:: rst

         .. lua:autoobject:: logging.Logger
            :members:

   .. tab-item:: Markdown
      :sync: md

      .. code-block:: myst

         ```{lua:autoobject} logging.Logger
         :members:
         ```

.. dropdown:: Example output

   .. lua:autoobject:: logging.Logger
      :members:
      :no-index:
