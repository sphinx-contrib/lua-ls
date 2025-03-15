--- @meta

--- Description
--- !doctype module
--- @class autodoc
autodoc = {}

--- Cross-reference target.
--- @class T

--- Description
---
function autodoc.function_simple() end

--- Description
function autodoc.function_untyped_args(a, b, c) end

--- Description
--- @param a integer
--- @param b string
function autodoc.function_typed_args(a, b) end

--- Description
--- @param a integer?
--- @param b string?
function autodoc.function_typed_optional_args(a, b) end

--- Description
--- @param T T
function autodoc.function_typed_args_crossrefs(T) end

--- Description
--- @return integer
function autodoc.function_return_type() end

--- Description
--- @return integer, boolean
function autodoc.function_return_types() end

--- Description
--- @return integer?
function autodoc.function_optional_return_types() end

--- Description
--- @return integer a
--- @return boolean b
function autodoc.function_named_return_types() end

--- Description
--- @return integer? a
function autodoc.function_named_optional_return_types() end

--- Description
--- @return T
function autodoc.function_return_types_crossrefs() end

--- Description
--- @param x table<string, T>
--- @param y fun(x: T, ...): (T: T, ...)
--- @return table<string, string> a
--- @return fun(a: integer, ...): (a: integer, ...) ...
function autodoc.function_complex_types(x, y) end

--- Description
--- @param x integer Description x
--- @param y string? Description y
--- @return integer a Description a
--- @return string? b Description b
function autodoc.function_param_return_doc(x, y) end

--- Description
--- @return integer # Description a
--- @return string? # Description b
function autodoc.function_unnamed_return_doc() end

--- Description
--- @type integer
autodoc.data_simple = 0

--- Description
--- @type table
autodoc.data_nested = {}

--- .. error::
---
---    This should not be generated!
---
--- @type integer
autodoc.data_nested.not_visible = 0

--- Description
--- !doctype table
--- @class autodoc.table_simple
autodoc.table_simple = {}

--- Description
--- !doctype table
--- @class autodoc.table_nested
autodoc.table_nested = {}

--- Description
--- @type integer
autodoc.table_nested.table_data = 0

--- Description.
--- @alias autodoc.alias_simple integer

--- Description.
--- @class autodoc.class_simple
autodoc.class_simple = {}

--- Description.
--- @class autodoc.class_one_base: T
autodoc.class_one_base = {}

--- Description.
--- @class autodoc.class_multiple_bases: T, { [string]: integer }
autodoc.class_multiple_bases = {}

--- Description
--- @class autodoc.class_members
autodoc.class_members = {}

--- Description.
--- @type integer
autodoc.class_members.data = 0

--- Description
function autodoc.class_members:method() end

--- Description
--- !doctype classmethod
function autodoc.class_members:classmethod() end

--- Description
function autodoc.class_members.staticmethod() end

--- Description
function autodoc.class_members.staticmethod_with_args(a, b, c) end
