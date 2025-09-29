--- @namespace logging

--- A generic logging module, just to demonstrate you documentation.
local logging = {}

--- Represents message severity.
---
--- @enum Level
logging.Level = {
    --- For debug messages, hidden by default.
    Debug = 1,

    --- For info messages.
    Info = 2,

    --- For warnings, when behavior may be different from what users expect.
    Warning = 3,

    --- For errors, when the system stops working.
    Error = 4,
}

--- Default log level.
---
--- @type Level
LOG_LEVEL = LOG_LEVEL or logging.Level.Info

--- An object for logging messages.
---
--- @class Logger
logging.Logger = {}

--- @param name string name of the logger, will be added to every message.
--- @param level logging.Level? level of the logger, equals to `LOG_LEVEL` by default.
function logging.Logger.__init(name, level) end

--- Print a debug message.
---
--- @param msg string message format string, will be processed by :func:`string.format`.
--- @param ... any parameters for message formatting.
function logging.Logger:debug(msg, ...) end

--- Print an info message.
---
--- @param msg string message format string, will be processed by :func:`string.format`.
--- @param ... any parameters for message formatting.
function logging.Logger:info(msg, ...) end

--- Print a warning message.
---
--- @param msg string message format string, will be processed by :func:`string.format`.
--- @param ... any parameters for message formatting.
function logging.Logger:warning(msg, ...) end

--- Print an error message.
---
--- @param msg string message format string, will be processed by :func:`string.format`.
--- @param ... any parameters for message formatting.
function logging.Logger:error(msg, ...) end

--- Get logger with the given name, or create one if it doesn't exist.
---
--- @param name string? logger name. Uses current module name if empty.
--- @return Logger logger logger with the given name.
function logging.getLogger(name) end

return logging
