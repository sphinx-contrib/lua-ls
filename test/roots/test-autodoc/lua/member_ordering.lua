--- @meta

--- Description
--- !doctype module
--- @class member_ordering
local member_ordering = {}

--- Description
function member_ordering.a() end

--- Description
--- @class member_ordering.c
member_ordering.c = {}

--- Description
--- @type integer
member_ordering.c.b = 0

--- Description
--- @type integer
member_ordering.c.a = 0

--- Description
function member_ordering.b() end
