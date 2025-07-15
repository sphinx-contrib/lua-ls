--- @namespace signatures
--- @meta

--- Description.
--- @class Simple
local Simple = {}

--- Description.
--- @class Bases: table
local Bases = {}

--- Description.
--- @class Ctor
local Ctor = {}

--- Ctor description.
--- @param x integer
function Ctor:__init(x) end

--- Description.
--- @class Both: table
local Both = {}

--- Ctor description.
--- @param x integer
function Both:__init(x) end

--- Description.
--- @class CtorOverloads
local CtorOverloads = {}

--- Ctor description.
--- @param x integer
--- @overload fun(a: integer, y: integer)
function CtorOverloads:__init(x) end
