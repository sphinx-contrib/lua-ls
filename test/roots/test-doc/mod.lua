--- This is a module.
---
--- !doctype module
--- @see autodoc.data
--- @see autodoc.brokenRef
--- @class autodoc
autodoc = {}

--- Module data.
---
--- @type integer
autodoc.data = 1

--- @type integer
autodoc.undocData = 1

--- Function foo.
---
--- @param a string param a
--- @param b string? param b
--- @return boolean? # doc for boolean return
--- @return nil | fun(a: string?): integer fn some function
function autodoc.foo(a, b) return false, nil end

--- This is a class.
--- @class autodoc.Class
autodoc.Class = {}

--- Class attribute.
--- @type integer
autodoc.Class.data = 1

--- Private class attribute.
--- @type string
--- @private
autodoc.Class.private = "meow ^^"

--- Class attribute with sub-items.
---
--- !doctype table
--- @class autodoc.Class.namespace
autodoc.Class.namespace = {}

--- Namespace attribute.
--- @type integer
autodoc.Class.namespace.data = 1

--- :lua:class:`Class` staticmethod.
function autodoc.Class.stm() end

--- :lua:class:`Class` method.
function autodoc.Class:mth() end

--- This is a subclass.
--- @class autodoc.SubClass: autodoc.Class
autodoc.SubClass = {}

--- Overridden method should not show up unless explicitly requested.
function autodoc.SubClass:mth() end

--- This is a class with fields.
--- @class autodoc.ClassWithFields
--- @field foo integer? docs for foo
--- @field bar string docs for bar
--- @operator concat(string): autodoc.ClassWithFields

--- This is an alias.
--- @alias autodoc.simpleAlias integer
autodoc.simpleAlias = {}

--- Alias attribute.
--- @type integer
autodoc.simpleAlias.data = 1

--- This is an alias enum.
--- @alias autodoc.aliasEnum
--- | 1
--- | 2
--- | 3
autodoc.aliasEnum = {}

--- This is a data that is documented as const.
---
--- !doctype const
--- @type any
autodoc.dataToConst = nil
