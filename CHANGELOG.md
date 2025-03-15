# Changelog

## v2.0.0

- Breaking change: don't implicitly convert classes that're derived from `table`
  to modules. Users should use a `!doctype` comment instead.
- Breaking change: disallow nesting modules inside classes.
- Added `autoindex` directive.
- Added `apidoc` functionality.
- Improved test coverage and fixed found bugs.

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
