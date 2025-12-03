import pytest

from sphinx_lua_ls.lua_ls import _should_skip


@pytest.mark.parametrize(
    "version,skips,expected",
    [
        (
            (1, 0, 0),
            [],
            False,
        ),
        (
            (1, 0, 0),
            [(1, 0, 0)],
            True,
        ),
        (
            (1, 0),
            [(1, 0, 0)],
            True,
        ),
        (
            (1, 0, 0),
            [(1, 0)],
            True,
        ),
        (
            (1, 0, 5),
            [(1, 0)],
            True,
        ),
        (
            (1, 1, 0),
            [(1, 0)],
            False,
        ),
    ],
)
def test_should_skip(version, skips, expected):
    assert _should_skip(version, skips) == expected
