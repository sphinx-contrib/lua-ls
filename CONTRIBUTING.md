# Contributing to Sphinx-LuaLs

## Set up your environment

We use [`uv`] and [`poe`] to run tasks, but it is possible to use pure pip as well.

[`uv`]: https://docs.astral.sh/uv/
[`poe`]: https://poethepoet.natn.io/index.html

### Using pip

1. Create a virtual environment with python `3.12` or newer.

2. Make sure your pip is up to date:

   ```shell
   pip install -U pip
   ```

2. Install package in development mode, and install dev dependencies:

   ```shell
   pip install -e . --group dev
   ```

3. Install pre-commit hooks:

   ```shell
   prek install
   ```

4. [Install `poe`], either globally or in virtual environment:

   ```shell
   pip install poethepoet
   ```

[Install `poe`]: https://poethepoet.natn.io/installation.html

5. If you're not on linux, install [EmmyLua Doc Cli].

[EmmyLua Doc Cli]: https://github.com/EmmyLuaLs/emmylua-analyzer-rust/?tab=readme-ov-file#-installation

### Using uv

1. Sync your virtual environment:

   ```shell
   uv sync
   ```

2. Install pre-commit hooks:

   ```shell
   uv run prek install
   ```

3. [Install `poe`] if you don't have it already:

   ```shell
   uv tool install poethepoet
   ```

5. If you're not on linux, install [EmmyLua Doc Cli].


## Run tests

We use `poe` for most of the tasks:

```shell
poe lint  # Lint and fix code style.
poe test  # Run tests.
poe test-all  # Run tests for all pythons.
```

You can see all commands in `poe`'s help:

```shell
poe --help
```


## Build docs

Just run `sphinx` as usual, nothing special is required:

```shell
cd docs/
make html
```

Sphinx-LuaLs will download the latest version of Lua Language Server for you.


## Release

1. Make sure that "Unreleased" section in `changelog.md` is up to date.

2. Run `poe release auto` to bump version in changelog and create a release tag.

2. Push a git tag. You'll need a repository admin role to do so.

3. From here, release happens automatically. PyPi package will be uploaded from
   CI job, and documentation will be updated by Read the Docs build.
