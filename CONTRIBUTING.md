# Contributing to Sphinx-LuaLs

## Set up your environment

1. Check out the repo:

   ```shell
   git clone git@github.com:taminomara/sphinx-lua-ls.git
   ```

2. Create a virtual environment with python `3.12` or newer.

3. Install Sphinx-LuaLs in development mode, and install dev dependencies:

   ```shell
   pip install -e . --group dev
   ```

4. Install pre-commit hooks:

   ```shell
   pre-commit install
   ```

5. If you're not on linux, install [EmmyLua Doc Cli].

[EmmyLua Doc Cli]: https://github.com/EmmyLuaLs/emmylua-analyzer-rust/?tab=readme-ov-file#-installation

## Run tests

To run tests, simply run `pytest` and `pyright`:

```shell
pytest  # Run unit tests.
pyright  # Run type check.
```

To fix code style, you can manually run pre-commit hooks:

```shell
pre-commit run -a  # Fix code style.
```

To regenerate data for regression tests, run

```shell
pytest --regen-all
```


## Build docs

Just run `sphinx` as usual, nothing special is required:

```shell
cd docs/
make html
```

Sphinx-LuaLs will download the latest version of Lua Language Server for you.
