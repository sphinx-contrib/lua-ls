# Changelog

## v3.0.0

- **Breaking change:** changed how `apidoc` generates file names to avoid collisions.

- Supported [EmmyLua] as an alternative backend for documentation export.

  EmmyLua was recently re-implemented in Rust, and its new language server
  provides some substantial benefits:

  - it has stronger and more flexible type system,
  - it handles aliases and enums way better than LuaLs,
  - it supports namespaces,
  - it exports way more metadata, including function overloads and class constructors,
  - you don't have to annotate modules with `@class` and `!doctype` anymore.

  I plan to use EmmyLua as the default language server since *v3.0.0*.

- Long object signatures are now broken into multiple lines.

- Supported using arbitrary types as object names, i.e.:

  ```rst
  .. lua:data:: [integer]: string
  ```

- Added `:globals:` flag for the `lua:autoobject` directive. It will allow
  automatically documenting global variables defined in a module.

- The `lua:autoindex` directive now lists globals defined in a module.

- Added support for documenting class constructors:

  ```rst
  .. lua:class:: Foo(a, b, ...)
  ```

- Added directive for enums.

- Supported generic parameters for functions, classes, aliases and enums:

  ```rst
  .. lua:class:: Foo<T>
  ```

- Improved linking to Lua language documentation to take into account
  whether an item is supported for the given Lua version.

- Added the `lua:lua` role to compensate for MySt not supporting default roles.

  If Lua is your primary domain cross-referencing from markdown can be done like this:

  ```md
  Reference to a {lua}`logging.Logger.info`.
  ```

- Added the `lua:other-inherited-members` directive and `:inherited-members-table:`
  flag for the `lua:autoobject` directive.

  These allow listing all members that were inherited by a class but weren't
  documented within the class body (see [#3]).

- Supported markdown output for `apidoc`.

- Added option to separate module members into their own files for `apidoc`.

[EmmyLua]: https://github.com/EmmyLuaLs/emmylua-analyzer-rust/
[#3]: https://github.com/taminomara/sphinx-lua-ls/issues/3

**Migrating to 3.0.0:**

- If you're using `apidoc`, you'll need to update links to your documentation.

- You'll need to explicitly specify which language server to use
  by including `lua_ls_backend` to your `conf.py`.

## v2.0.1

- Fixed documentation not being rebuilt after changing lua source code.

## v2.0.0

- **Breaking change:** don't implicitly convert classes that're derived from `table`
  to modules. Users should use a `!doctype` comment instead.

- **Breaking change:** disallow nesting modules inside classes.

- Added `autoindex` directive.

- Added `apidoc` functionality.

- Improved test coverage and fixed found bugs.

**Migrating to 2.0.0:**

In your Lua code base, perform global replace by regexp:

```
^(\s*)---\s*@class\s*(.+): table$
```

to

```
$1--- !doctype module
$1--- @class $2
```

Make sure that you only use `!doctype module` on the top-level
tables that can be imported via `require`. On other objects,
use `!doctype table` instead, otherwise you'll get errors that modules are not allowed within other objects.

## v1.1.0

- Added support for `!doc` and `!doctype` comments.

- Added `:include-protected:` and `:include-package:` options for `lua:autoobject`.

- Allowed referring `lua:const` objects from `lua:attr` role.

- Fixed a bug when default options would not properly propagate
  when using `lua:autoobject` with `:recurse:`.

- Fixed a bug when `lua:autoobject` would deduce incorrect module paths
  when applied to non-toplevel modules.

- Fixed a bug when docstring for a class would be used for undocumented function
  parameters that have this class as their type.

- Fixed types when `lua:autoobject` would infer incorrect types for `data`.

## v1.0.0

Initial release.
