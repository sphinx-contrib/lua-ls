--- A generic logging module, just to demonstrate you documentation.
---
--- .. lua:autoobject:: LOG_LEVEL
---    :global:
---
--- !doctype module
--- @class logging
logging = {}

--- Represents message severity.
---
--- @alias logging.Level integer
logging.Level = {}

--- For debug messages, hidden by default.
---
--- @type logging.Level
logging.Level.Debug = 1

--- For info messages.
---
--- @type logging.Level
logging.Level.Info = 2

--- For warnings, when behavior may be different from what users expect.
---
--- @type logging.Level
logging.Level.Warning = 3

--- For errors, when the system stops working.
---
--- @type logging.Level
logging.Level.Error = 4

--- Default log level.
---
--- @type logging.Level
LOG_LEVEL = LOG_LEVEL or logging.Level.Info

--- An object for logging messages.
---
--- @class logging.Logger
logging.Logger = {}

--- Create a new logger.
---
--- @param name string name of the logger, will be added to every message.
--- @param level logging.Level? level of the logger, equals to `LOG_LEVEL` by default.
--- @return logging.Logger
function logging.Logger.new(name, level) return {} end

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

return logging
