import pathlib

import pytest
from bs4 import BeautifulSoup


@pytest.mark.sphinx("html", testroot="doc")
@pytest.mark.parametrize(
    "src",
    [
        "src/annotations.html",
        "src/autodoc.html",
        "src/directives.html",
        "src/modules.html",
        "src/refs.html",
    ],
)
def test_regression(app, src, file_regression):
    app.build()

    path = pathlib.Path(app.outdir) / src

    soup = BeautifulSoup(path.read_text("utf8"), "html.parser")
    content = soup.select("div.body")[0]
    file_regression.check(
        content.prettify(),
        basename=pathlib.Path(src).stem,
        extension=".html",
        encoding="utf8",
    )
