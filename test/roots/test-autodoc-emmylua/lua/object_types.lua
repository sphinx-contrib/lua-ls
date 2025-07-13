--- @meta

--- Description
local object_types = {}

--- Cross-reference target.
--- @class T

--- Description
---
function object_types.function_simple() end

--- Description
function object_types.function_untyped_args(a, b, c) end

--- Description
--- @param a integer
--- @param b string
function object_types.function_typed_args(a, b) end

--- Description
--- @param a integer?
--- @param b string?
function object_types.function_typed_optional_args(a, b) end

--- Description
--- @param T T
function object_types.function_typed_args_crossrefs(T) end

--- Description
--- @return integer
function object_types.function_return_type() end

--- Description
--- @return integer, boolean
function object_types.function_return_types() end

--- Description
--- @return integer?
function object_types.function_optional_return_types() end

--- Description
--- @return integer a
--- @return boolean b
function object_types.function_named_return_types() end

--- Description
--- @return integer? a
function object_types.function_named_optional_return_types() end

--- Description
--- @return T
function object_types.function_return_types_crossrefs() end

--- Description
--- @param x table<string, T>
--- @param y fun(x: T, ...): (T: T, ...)
--- @return table<string, string> a
--- @return fun(a: integer, ...): (a: integer, ...) ...
function object_types.function_complex_types(x, y) end

--- Description
--- @param x integer Description x
--- @param y string? Description y
--- @return integer a Description a
--- @return string? b Description b
function object_types.function_param_return_doc(x, y) end

--- Description
--- @return integer # Description a
--- @return string? # Description b
function object_types.function_unnamed_return_doc() end

--- Description
--- @type integer
object_types.data_simple = 0

--- Description
--- @type table
object_types.data_nested = {}

--- .. error::
---
---    This should not be generated!
---
--- @type integer
object_types.data_nested.not_visible = 0

--- Description
--- !doctype table
--- @class object_types.table_simple
object_types.table_simple = {}

--- Description
--- !doctype table
--- @class object_types.table_nested
object_types.table_nested = {}

--- Description
--- @type integer
object_types.table_nested.table_data = 0

--- Description.
--- @alias object_types.alias_simple integer

--- Description.
--- @class object_types.class_simple
object_types.class_simple = {}

--- Description.
--- @class object_types.class_one_base: T
object_types.class_one_base = {}

--- Description.
--- @class object_types.class_multiple_bases: T, { [string]: integer }
object_types.class_multiple_bases = {}

--- Description
--- @class object_types.class_members
object_types.class_members = {}

--- Description.
--- @type integer
object_types.class_members.data = 0

--- Description
function object_types.class_members:method() end

--- Description
--- !doctype classmethod
function object_types.class_members:classmethod() end

--- Description
function object_types.class_members.staticmethod() end

--- Description
function object_types.class_members.staticmethod_with_args(a, b, c) end

return object_types
