--- @meta

--- Description
---
--- .. lua:autoobject:: foo
---
--- !doctype module
--- @class relative_resolve
local relative_resolve = {}

--- Description.
---
--- .. lua:autoobject:: bar
---
--- @class relative_resolve.foo
relative_resolve.foo = {}

--- Description.
--- @type integer
relative_resolve.foo.bar = 0
