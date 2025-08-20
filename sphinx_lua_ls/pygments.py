from pygments.lexer import bygroups, inherit
from pygments.lexers.scripting import LuaLexer as _LuaLexer  # type: ignore
from pygments.token import *  # type: ignore


class LuaLexer(_LuaLexer):
    tokens = {
        "ws": [
            (
                r"(--\[(?P<level>=*)\[\s*)(@\w+)(.*?\](?P=level)\])",
                bygroups(
                    Comment.Multiline, None, Keyword.Comment, Comment.Multiline, None
                ),
            ),
            (
                r"(---\s*)(@\w+)(.*)$",
                bygroups(Comment.Multiline, Keyword.Comment, Comment.Multiline),
            ),
            inherit,
        ],
    }
