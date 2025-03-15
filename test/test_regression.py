import pathlib

import pytest
from bs4 import BeautifulSoup


@pytest.mark.sphinx("html", testroot="doc")
@pytest.mark.test_params(shared_result="test_regression")
@pytest.mark.parametrize(
    "src",
    [
        "src/annotations.html",
        "src/autoindex.html",
        "src/directives.html",
        "src/modules.html",
        "src/refs.html",
    ],
)
def test_regression(app, src, file_regression):
    app.build()
    path = pathlib.Path(app.outdir) / src
    soup = BeautifulSoup(path.read_text("utf8"), "html.parser")
    content = soup.select_one("div.regression")
    assert content
    file_regression.check(
        content.prettify(),
        basename="doc-" + pathlib.Path(src).stem,
        extension=".html",
        encoding="utf8",
    )


@pytest.mark.sphinx("html", testroot="intersphinx")
@pytest.mark.parametrize(
    "ver",
    [
        pytest.param("5.4", marks=pytest.mark.sphinx(confoverrides={})),
        pytest.param(
            "5.1", marks=pytest.mark.sphinx(confoverrides={"lua_ls_lua_version": "5.1"})
        ),
    ],
)
def test_intersphinx(app, ver):
    app.build()
    path = pathlib.Path(app.outdir) / "index.html"
    soup = BeautifulSoup(path.read_text("utf8"), "html.parser")
    ref = soup.select_one("div.regression a.reference")
    assert ref
    assert ref.attrs["href"].startswith(f"https://www.lua.org/manual/{ver}")  # type: ignore


@pytest.mark.sphinx("html", testroot="autodoc")
@pytest.mark.test_params(shared_result="test_autodoc_regression")
@pytest.mark.parametrize(
    "src",
    [
        "src/annotations.html",
        "src/autoindex.html",
        "src/member_ordering.html",
        "src/module_title.html",
        "src/nested_modules.html",
        "src/nesting_recursive.html",
        "src/nesting.html",
        "src/object_types.html",
        "src/relative_resolve.html",
    ],
)
def test_autodoc_regression(app, src, file_regression):
    app.build()
    path = pathlib.Path(app.outdir) / src
    soup = BeautifulSoup(path.read_text("utf8"), "html.parser")
    content = soup.select_one("div.regression")
    assert content
    file_regression.check(
        content.prettify(),
        basename="autodoc-" + pathlib.Path(src).stem,
        extension=".html",
        encoding="utf8",
    )


@pytest.mark.sphinx("html", testroot="autodoc-settings")
@pytest.mark.parametrize(
    "name",
    [
        pytest.param(
            "simple",
            marks=pytest.mark.sphinx(
                confoverrides={"lua_ls_default_options": {"members": ""}}
            ),
        ),
        pytest.param(
            "no-recursion",
            marks=pytest.mark.sphinx(
                confoverrides={"lua_ls_default_options": {"members": "meep"}}
            ),
        ),
        pytest.param(
            "annotation",
            marks=pytest.mark.sphinx(
                confoverrides={"lua_ls_default_options": {"members": "", "private": ""}}
            ),
        ),
    ],
)
def test_autodoc_settings(app, name, file_regression):
    app.build()
    path = pathlib.Path(app.outdir) / "index.html"
    soup = BeautifulSoup(path.read_text("utf8"), "html.parser")
    content = soup.select_one("div.regression")
    assert content
    file_regression.check(
        content.prettify(),
        basename=f"autodoc-settings-{name}.html",
        extension=".html",
        encoding="utf8",
    )


@pytest.mark.sphinx("html", testroot="autodoc-roots")
@pytest.mark.parametrize(
    "name",
    [
        pytest.param(
            "default",
            marks=pytest.mark.sphinx(
                confoverrides={"lua_ls_project_directories": None}
            ),
        ),
        pytest.param(
            "single-root",
            marks=pytest.mark.sphinx(
                confoverrides={"lua_ls_project_directories": ["root_1"]}
            ),
        ),
        pytest.param(
            "no-roots",
            marks=pytest.mark.sphinx(confoverrides={"lua_ls_project_directories": []}),
        ),
    ],
)
def test_autodoc_roots(app, name, file_regression):
    app.build()
    path = pathlib.Path(app.outdir) / "index.html"
    soup = BeautifulSoup(path.read_text("utf8"), "html.parser")
    content = soup.select_one("div.regression")
    assert content
    file_regression.check(
        content.prettify(),
        basename=f"autodoc-roots-{name}.html",
        extension=".html",
        encoding="utf8",
    )
