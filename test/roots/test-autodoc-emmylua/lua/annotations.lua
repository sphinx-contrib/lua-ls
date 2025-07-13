--- @meta

--- Description
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

--- @see annotations
--- @deprecated
function annotations.see_one() end

--- @see xyz
--- @deprecated
function annotations.see_one_broken() end

--- @see annotations.annotation_private
--- @see annotations.annotation_protected
--- @deprecated
function annotations.see_many() end

--- @see xyz
--- @see abc
--- @deprecated
function annotations.see_many_broken() end

return annotations
