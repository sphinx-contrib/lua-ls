--- Description.
local mod = {}

--- Description.
function mod.foo() end

--- Description.
--- @type integer
MOD_GLOBAL = 0

--- Potentially shadows a global.
--- @type integer
mod.MOD_GLOBAL = 0

--- Description.
--- @class Foo

--- Potentially shadows a global.
--- @class mod.Foo

return mod
