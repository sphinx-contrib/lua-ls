--- @meta

--- Description
--- !doctype module
--- @class annotations
local annotations = {}

--- Description.
--- @private
function annotations.annotation_private() end

--- Description.
--- @protected
function annotations.annotation_protected() end

--- Description.
--- @package
function annotations.annotation_package() end

--- Description.
--- @async
function annotations.annotation_async() end

--- Description.
--- @deprecated
function annotations.annotation_deprecated() end

--- Description.
--- @see annotations text
--- @deprecated
function annotations.see_one() end

--- Description.
--- @see xyz text
--- @deprecated
function annotations.see_one_broken() end

--- Description.
--- @see annotations.annotation_private text 1
--- @see annotations.annotation_protected text 2
--- @deprecated
function annotations.see_many() end

--- Description.
--- @see xyz text 1
--- @see abc text 2
--- @deprecated
function annotations.see_many_broken() end

--- @see load
function annotations.see_no_text() end
