Declaring objects
=================

Modules
-------

.. rst:directive:: .. lua:module:: name

   Specifies beginning of a module. Other objects declared after this directive
   will be automatically attached to this module.

   This directive doesn't accept any content, it just creates an anchor.

   Modules are something you can `require`. If you need to document a namespace
   inside of a module, use a :rst:dir:`lua:table` instead.

.. rst:directive:: .. lua:currentmodule:: name

   Switches current module without making an index entry or an anchor.
   If ``name`` is ``None``, sets current module to be the global namespace.

   This directive can't be used inside other lua objects.


Objects
-------

.. rst:directive:: .. lua:data:: name: type
                   .. lua:const:: name: type
                   .. lua:attribute:: name: type

   Directives for documenting variables. Accepts name of the variable,
   and an optional type:

   .. tab-set::
      :sync-group: lang

      .. tab-item:: RST
         :sync: rst

         .. code-block:: rst

            .. lua:data:: name: string

               Person's name.

      .. tab-item:: Markdown
         :sync: md

         .. code-block:: myst

            ```{lua:data} name: string
            Person's name.
            ```

   .. dropdown:: Example output

      .. lua:data:: name: string
         :no-index:

         Person's name.

   Using type instead of a name is also supported:

   .. tab-set::
      :sync-group: lang

      .. tab-item:: RST
         :sync: rst

         .. code-block:: rst

            .. lua:data:: [integer]: string

               Array contents.

      .. tab-item:: Markdown
         :sync: md

         .. code-block:: myst

            ```{lua:data} [integer]: string
            Array contents.
            ```

   .. dropdown:: Example output

      .. lua:data:: [integer]: string
         :no-index:

         Array contents.

.. rst:directive:: .. lua:table:: name

   Directive for documenting tables that serve as namespaces.
   It works like :rst:dir:`lua:data`, but can contain nested members.

.. rst:directive:: .. lua:function:: name<generics>(param: type): type
                   .. lua:method:: name<generics>(param: type): type
                   .. lua:classmethod:: name<generics>(param: type): type
                   .. lua:staticmethod:: name<generics>(param: type): type

   Directives for documenting functions and class methods:

   .. tab-set::
      :sync-group: lang

      .. tab-item:: RST
         :sync: rst

         .. code-block:: rst

            .. lua:function:: doABarrelRoll(times: integer): (success: boolean)

               Does a barrel roll given amount of times. Returns ``true`` if successful.

      .. tab-item:: Markdown
         :sync: md

         .. code-block:: myst

            ```{lua:function} doABarrelRoll(times: integer): (success: boolean)
            Does a barrel roll given amount of times. Returns ``true`` if successful.
            ```

   .. dropdown:: Example output

      .. lua:function:: doABarrelRoll(times: integer): (success: boolean)
         :no-index:

         Does a barrel roll given amount of times. Returns ``true`` if successful.

   This directive can also document multiple function overloads at once:

   .. tab-set::
      :sync-group: lang

      .. tab-item:: RST
         :sync: rst

         .. code-block:: rst

            .. lua:function:: table.insert<T>(array: T[], item: T): integer
                              table.insert<T>(array: T[], index: integer, item: T): integer

               Insert a value into an array.

      .. tab-item:: Markdown
         :sync: md

         .. code-block:: myst

            ```{eval-rst}
            .. lua:function:: table.insert<T>(array: T[], item: T): integer
                              table.insert<T>(array: T[], index: integer, item: T): integer

               Insert a value into an array.
            ```

         .. note::

            MySt doesn't support directives with multiple arguments,
            so we use ``eval-rst`` to bypass it.

   .. dropdown:: Example output

      .. lua:function:: table.insert<T>(array: T[], item: T): integer
                        table.insert<T>(array: T[], index: integer, item: T): integer
         :no-index:

         Insert a value into an array.

.. rst:directive:: .. lua:class:: name<generics>: bases
                   .. lua:class:: name<generics>(param: type): type

   For documenting classes and metatables:

   .. tab-set::
      :sync-group: lang

      .. tab-item:: RST
         :sync: rst

         .. code-block:: rst

            .. lua:class:: Logger: LogFilter, LogSink

               The user-facing interface for logging messages.

      .. tab-item:: Markdown
         :sync: md

         .. code-block:: myst

            ```{lua:class} Logger: LogFilter, LogSink
            The user-facing interface for logging messages.
            ```

   .. dropdown:: Example output

      .. lua:class:: Logger: LogFilter, LogSink
         :no-index:

         The user-facing interface for logging messages.

   This directive can also document constructors:

   .. tab-set::
      :sync-group: lang

      .. tab-item:: RST
         :sync: rst

         .. code-block:: rst

            .. lua:class:: Logger: LogFilter, LogSink
                           Logger(level: LogLevel)

               The user-facing interface for logging messages.

      .. tab-item:: Markdown
         :sync: md

         .. code-block:: myst

            ```{eval-rst}
            .. lua:class:: Logger: LogFilter, LogSink
                           Logger(level: LogLevel)

               The user-facing interface for logging messages.
            ```

         .. note::

            MySt doesn't support directives with multiple arguments,
            so we use ``eval-rst`` to bypass it.

   .. dropdown:: Example output

      .. lua:class:: Logger: LogFilter, LogSink
                     Logger(level: LogLevel)
         :no-index:

         The user-facing interface for logging messages.

.. rst:directive:: .. lua:alias:: name<generics> = type
                   .. lua:enum:: name

   For documenting type aliases and enums:

   .. tab-set::
      :sync-group: lang

      .. tab-item:: RST
         :sync: rst

         .. code-block:: rst

            .. lua:alias:: LogLevel = integer

               Verbosity level of a log message.

      .. tab-item:: Markdown
         :sync: md

         .. code-block:: myst

            ```{lua:alias} LogLevel = integer
            Verbosity level of a log message.
            ```

   .. dropdown:: Example output

      .. lua:alias:: LogLevel = integer
         :no-index:

         Verbosity level of a log message.


Parameters
----------

All directives that document Lua objects accept the standard parameters:

.. rst:directive:option:: no-index
                          no-index-entry
                          no-contents-entry
                          no-typesetting

    The `standard Sphinx options`__ available to all object descriptions.

    __ https://www.sphinx-doc.org/en/master/usage/domains/index.html#basic-markup

.. rst:directive:option:: private
                          protected
                          package
                          virtual
                          abstract
                          async
                          global

   Adds a corresponding annotation before object's name:

   .. tab-set::
      :sync-group: lang

      .. tab-item:: RST
         :sync: rst

         .. code-block:: rst

            .. lua:function:: fetch(url: string): (code: integer, content: string?)
               :async:

               Fetches content from the given url.

      .. tab-item:: Markdown
         :sync: md

         .. code-block:: myst

            ```{lua:function} fetch(url: string): (code: integer, content: string?)
            :async:
            Fetches content from the given url.
            ```

   .. dropdown:: Example output

      .. lua:function:: fetch(url: string): (code: integer, content: string?)
         :async:
         :no-index:

         Fetches content from the given url.

.. rst:directive:option:: annotation: <text>

   Allows adding custom short annotations.

.. rst:directive:option:: deprecated

   Marks object as deprecated in index and when cross-referencing.
   This will not add any text to the documented object, you'll need
   to use the ``deprecated`` directive for this:

   .. tab-set::
      :sync-group: lang

      .. tab-item:: RST
         :sync: rst

         .. code-block:: rst

            .. lua:data:: fullname: string
               :deprecated:

               Person's full name.

               .. deprecated:: 3.2

                  Use ``name`` and ``surname`` instead.

      .. tab-item:: Markdown
         :sync: md

         .. code-block:: myst

            ````{lua:data} fullname: string
            :deprecated:

            Person's full name.

              ```{deprecated} 3.2
              Use ``name`` and ``surname`` instead.
              ```

            ````

   .. dropdown:: Example output

      .. lua:data:: fullname: string
         :deprecated:
         :no-index:

         Person's full name.

         .. deprecated:: 3.2

            Use ``name`` and ``surname`` instead.

.. rst:directive:option:: synopsis: <text>

   Allows adding a small description that's reflected
   in the :rst:dir:`lua:autoindex` output.

.. rst:directive:option:: module: <name>

   Allows overriding current module for a single object. This is useful
   for documenting global variables that are declared in a module.
