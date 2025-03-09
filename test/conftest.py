import pathlib

import pytest

pytest_plugins = "sphinx.testing.fixtures"


@pytest.fixture(scope="session")
def rootdir():
    return pathlib.Path(__file__).parent.resolve() / "roots"


@pytest.fixture
def warnings():
    def read(app):
        return app._warning.getvalue().strip()

    return read
