# Contributing to Sphinx-LuaLs

## Set up your environment

We use [`uv`] and [`poe`] to run tasks, but it is possible to use pure pip as well.

[`uv`]: https://docs.astral.sh/uv/
[`poe`]: https://poethepoet.natn.io/index.html

### Using pip

1. Create a virtual environment with python `3.13` or newer
   (some of dev tools don't work with older pythons).

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

4. If you're not on linux, install [EmmyLua Doc Cli].


## Run commands

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

To build docs, just use `poe`:

```shell
poe doc  # Build HTML.
poe doc-watch  # Run sphinx-autobuild.
```

Sphinx-LuaLs will download the latest version of Lua Language Server for you.


## Release

1. Make sure that "Unreleased" section in `CHANGELOG.md` is up to date.

2. Run `poe release major|minor|patch` to bump version in changelog
   and create a release tag.

3. Push a git tag. You'll need a repository admin role to do so.

4. From here, release happens automatically. PyPi package will be uploaded from
   CI job, and documentation will be updated by Read the Docs build.
