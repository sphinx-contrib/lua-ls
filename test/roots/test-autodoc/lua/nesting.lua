--- @meta

--- @class nesting_base
--- @field inherited integer Description.

--- Description
--- !doctype module
--- @class nesting
local nesting = {}

--- @type integer
nesting.undoc = 0

--- Description.
--- @private
--- @type integer
nesting.private = 0

--- Description.
--- @protected
--- @type integer
nesting.protected = 0

--- Description.
--- @package
--- @type integer
nesting.package = 0

--- Description.
--- @type integer
nesting.__special = 0

--- Description.
--- @class nesting.class: nesting_base
nesting.class = {}

--- @type integer
nesting.class.undoc = 0

--- Description.
--- @private
--- @type integer
nesting.class.private = 0

--- Description.
--- @protected
--- @type integer
nesting.class.protected = 0

--- Description.
--- @package
--- @type integer
nesting.class.package = 0

--- Description.
--- @type integer
nesting.class.__special = 0
