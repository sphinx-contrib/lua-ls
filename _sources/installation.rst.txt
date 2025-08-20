Installation
============

You'll need a Python installation and a Sphinx project to start with Sphinx-LuaLs.

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

1. Install ``sphinx-lua-ls`` using Pip:

   .. code-block:: console

      $ pip install sphinx-lua-ls

2. Add it to the ``extensions`` list in your ``conf.py``,
   and specify the location of your Lua project:

   .. code-block:: python

      extensions = [
          "sphinx_lua_ls",
      ]

      # Path to the folder containing the `.emmyrc.json`/`.luarc.json` file,
      # relative to the directory with `conf.py`.
      lua_ls_project_root = "../"

3. Configure which language analyzer you want to use:

   .. tab-set::
      :sync-group: backend

      .. tab-item:: EmmyLua
         :sync: emmylua

         Set :py:data:`lua_ls_backend` to ``"emmylua"`` in your ``conf.py``:

         .. code-block:: python

            lua_ls_backend = "emmylua"

         .. tip::

            Add the following settings to your ``.emmyrc.json`` to enable syntax
            highlighting and Go To Definition for comments:

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
                           "syntax": "rst"
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
                           "syntax": "myst"
                        }
                     }

      .. tab-item:: LuaLs
         :sync: luals

         Set :py:data:`lua_ls_backend` to ``"luals"`` in your ``conf.py``:

         .. code-block:: python

            lua_ls_backend = "luals"

4. If you plan to use Markdown in code comments, install the `MySt`_ plugin for Sphinx
   and add it to the ``extensions`` list in your ``conf.py``.

.. _instructions at github:
   https://github.com/EmmyLuaLs/emmylua-analyzer-rust?tab=readme-ov-file#-installation

.. _MySt:
   https://myst-parser.readthedocs.io/en/latest/index.html
