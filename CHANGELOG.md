# Changelog

## [unreleased]

## [3.5.0]

- Added `autodata`, `autoattribute`, `autoclass`, and other `auto*` directives.

  They work like `autoobject`, but apply their doctype to the documented object
  (if `!doctype` was set in source code, it shouldn't conflict with the used directive).

  They also allow overriding object's signature, which may be useful when
  automatically generated signature is too long.

- Added `lua_ls_max_version` config option to safeguard against incompatible changes
  to documentation export format.

- Fixed a few more minor bugs in highlighting of Lua types.

## [3.4.0]

- **Potential breaking change:** use `confdir` instead of `srcdir` as base path
  for `lua_ls_project_root`.

  Prior to this change, `lua_ls_project_root` was resolved relative to the directory
  containing source `.rst` files. Documentation, however, was saying that it's resolved
  relative to the directory with `conf.py`.

  This is not an issue, because in most projects `conf.py` and source `.rst` files
  are located in the same directory. Still, I've decided to be consistent with
  other Sphinx extensions and use `confdir` instead of `srcdir`.

  This is a breaking change, but I don't believe there are any projects that
  use separate `confdir` and `srcdir` (the only reason to do this is if you're
  hosting multiple documentation sites in the same repo.) For this reason,
  this change is released as a minor version change.

## [3.3.0]

- Added an option to extend list options (like `:exclude-members:`) without overriding
  defaults:

  ```rst
  .. lua:autoobject::
     :exclude-members: +foo
  ```

  Also added `:no-*:` options to ignore defaults.

- Improved display of members which use types instead of names,
  i.e. `[<type>]` ([#19] by [@bkoropoff]).

- Added a warning for situations when `lua_ls_project_directories` contains directories
  outside of the current VCS root.

[#19]: https://github.com/taminomara/sphinx-lua-ls/pull/19

## [3.2.0]

- Updated a few dependencies. Most notably, restricted `sphinx` to `<9`.

- Fixed dashes in types being parsed as type names ([#18] by [@bkoropoff]).

- Added normalization for function syntax (`fun() -> T` is converted to `fun(): T`).

- Done some internal refactorings.

[#18]: https://github.com/taminomara/sphinx-lua-ls/pull/18
[@bkoropoff]: https://github.com/bkoropoff

## [3.1.0]

- Added pygments lexer for Lua that highlights documentation tags.

- Added option to control maximum signature length before wrapping.

- Sphinx's nitpicky mode will no longer emit warnings
  for cross-references in signatures.

- Fixed generation of URL anchors to avoid duplicates.

- Fixed some edge cases in parsing of type expressions.

## [3.0.0]

- **Breaking change:** changed how `apidoc` generates file names to avoid collisions.

- Supported [EmmyLua] as an alternative backend for documentation export.

  EmmyLua was recently re-implemented in Rust, and its new language server
  provides some substantial benefits:

  - it has stronger and more flexible type system,
  - it handles aliases and enums way better than LuaLs,
  - it supports namespaces,
  - it exports way more metadata, including function overloads and class constructors,
  - you don't have to annotate modules with `@class` and `!doctype` anymore.

  I plan to use EmmyLua as the default language server since *v4.0.0*.

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

### Migrating to 3.0.0

- If you're using `apidoc`, you'll need to update links to your documentation.

- You'll need to explicitly specify which language server to use
  by including `lua_ls_backend` to your `conf.py`.

## [2.0.1]

- Fixed documentation not being rebuilt after changing lua source code.

## [2.0.0]

- **Breaking change:** don't implicitly convert classes that're derived from `table`
  to modules. Users should use a `!doctype` comment instead.

- **Breaking change:** disallow nesting modules inside classes.

- Added `autoindex` directive.

- Added `apidoc` functionality.

- Improved test coverage and fixed found bugs.

### Migrating to 2.0.0

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

## [1.1.0]

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

## [1.0.0]

Initial release.

[unreleased]: https://github.com/taminomara/sphinx-lua-ls/compare/v3.5.0...HEAD
[3.5.0]: https://github.com/taminomara/sphinx-lua-ls/compare/v3.4.0...v3.5.0
[3.4.0]: https://github.com/taminomara/sphinx-lua-ls/compare/v3.3.0...v3.4.0
[3.3.0]: https://github.com/taminomara/sphinx-lua-ls/compare/v3.2.0...v3.3.0
[3.2.0]: https://github.com/taminomara/sphinx-lua-ls/compare/v3.1.0...v3.2.0
[3.1.0]: https://github.com/taminomara/sphinx-lua-ls/compare/v3.0.0...v3.1.0
[3.0.0]: https://github.com/taminomara/sphinx-lua-ls/compare/v2.0.1...v3.0.0
[2.0.1]: https://github.com/taminomara/sphinx-lua-ls/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/taminomara/sphinx-lua-ls/compare/v1.1.0...v2.0.0
[1.1.0]: https://github.com/taminomara/sphinx-lua-ls/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/taminomara/sphinx-lua-ls/releases/tag/v1.0.0
