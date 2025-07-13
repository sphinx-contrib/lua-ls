import pytest

from sphinx_lua_ls import utils


@pytest.mark.parametrize(
    "sig, expected",
    [
        ("", ("", "")),
        ("    ", ("", "")),
        ("()", ("", "")),
        ("(    )  ", ("", "")),
        ("(a, b, c) d, e, f", ("a, b, c", "d, e, f")),
        ("(a, (b), c) d, e, f", ("a, (b), c", "d, e, f")),
        ("(a, ')', c) d, e, f", ("a, ')', c", "d, e, f")),
        (
            "(a, b: table<string, number>, c) d, e, f",
            ("a, b: table<string, number>, c", "d, e, f"),
        ),
    ],
)
def test_separate_paren_prefix(sig, expected):
    assert utils.separate_paren_prefix(sig) == expected


@pytest.mark.parametrize(
    "sig, expected",
    [
        ("", []),
        ("   ", []),
        ("a, b, c", ["a", "b", "c"]),
        ("fun()", ["fun()"]),
        ("a, fun(a, b, c), b", ["a", "fun(a, b, c)", "b"]),
        ("a, [tuple, tuple, tuple], b", ["a", "[tuple, tuple, tuple]", "b"]),
        ("a, table<string, number>, b", ["a", "table<string, number>", "b"]),
        (
            "a, 'literal \\' escape, literal', b",
            ["a", "'literal \\' escape, literal'", "b"],
        ),
    ],
)
def test_separate_sig(sig, expected):
    assert utils.separate_sig(sig) == expected


@pytest.mark.parametrize(
    "sig, expected",
    [
        ("", []),
        ("    ", []),
        ("string", [("", "string")]),
        ("   string   ", [("", "string")]),
        ("string, nil", [("", "string"), ("", "nil")]),
        (
            "a, 'literal', nil, b",
            [("", "a"), ("", "'literal'"), ("", "nil"), ("", "b")],
        ),
        (
            "a, 'literal, literal', b",
            [("", "a"), ("", "'literal, literal'"), ("", "b")],
        ),
        (
            "a, 'literal \\' escape, literal', b",
            [("", "a"), ("", "'literal \\' escape, literal'"), ("", "b")],
        ),
        (
            "a, fun(arg1: type1, arg2: type2), b",
            [("", "a"), ("", "fun(arg1: type1, arg2: type2)"), ("", "b")],
        ),
        (
            "a, fun(arg1: type1, arg2: type2): integer, b",
            [("", "a"), ("", "fun(arg1: type1, arg2: type2): integer"), ("", "b")],
        ),
        (
            "a, table<string, number>, b",
            [("", "a"), ("", "table<string, number>"), ("", "b")],
        ),
        (
            "a: table<string, number>, b: integer",
            [("a", "table<string, number>"), ("b", "integer")],
        ),
        (" x : integer ", [("x", "integer")]),
        ("a.b.c: integer ", [("", "a.b.c: integer")]),
        ("a..c: integer ", [("", "a..c: integer")]),
        (
            "a + b: table<string, number>, b: integer",
            [("", "a + b: table<string, number>"), ("b", "integer")],
        ),
        ("fun(): ..., fun(): integer", [("", "fun(): ..."), ("", "fun(): integer")]),
        (
            "a: fun(): ..., b: fun(): integer",
            [("a", "fun(): ..."), ("b", "fun(): integer")],
        ),
    ],
)
def test_parse_types(sig, expected):
    assert utils.parse_types(sig) == expected
