--- @meta

--- Description
local nested_modules = {}

--- Description
--- @doctype module
--- @class nested_modules.inner
nested_modules.inner = {}

--- Description.
function nested_modules.inner.foo() end

return nested_modules
