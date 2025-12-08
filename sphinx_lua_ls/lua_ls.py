"""
Wrapper around the Lua-LS executable; able to download lua-ls if it's not installed.

"""

import datetime
import json
import math
import os
import pathlib
import platform
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import typing as _t

import github
import requests
import requests.adapters
import urllib3
from sphinx.errors import SphinxError
from sphinx.util import logging
from sphinx.util.console import bold, red  # type: ignore

KNOWN_BROKEN_LUA_LS_RELEASES = ["3.16.0"]
KNOWN_BROKEN_EMMYLUA_RELEASES = []


_PathLike: _t.TypeAlias = str | os.PathLike[str]


_logger = logging.getLogger("sphinx_lua_ls")


class LuaLsError(SphinxError):
    """
    Raised when LuaLs is unavailable, or when installation fails.

    """

    category = "Can't find Lua Language Server (see the message above)"


class LuaLsRunError(LuaLsError, subprocess.CalledProcessError):
    """
    Raised when LuaLs process fails.

    """

    category = "Lua Language Server run failed (see the message above)"

    def __str__(self):
        if self.returncode and self.returncode < 0:
            try:
                returncode = f"signal {signal.Signals(-self.returncode)}"
            except ValueError:
                returncode = f"unknown signal {self.returncode}"
        else:
            returncode = f"code {self.returncode}"

        msg = f"LuaLs run failed with {returncode}"
        stderr = self.stderr
        if self.stderr:
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            msg += f"\n\nStderr:\n{stderr}"
        stdout = self.stdout
        if self.stdout:
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            msg += f"\n\nStdout:\n{stdout}"
        return msg


@_t.final
class LuaLs:
    """
    Interface for a lua-language-server installation.

    Do not create directly, use :func:`resolve` instead.

    """

    def __init__(
        self,
        *,
        _backend: _t.Literal["emmylua", "luals"],
        _bin_path: pathlib.Path,
        _path: str,
        _quiet: bool = True,
        _env: dict[str, str] | None = None,
        _cwd: _PathLike | None = None,
    ):
        self._backend = _backend
        self._bin_path = _bin_path
        self._path = _path
        self._quiet = _quiet
        self._env = _env
        self._cwd = _cwd

    def run(
        self,
        input_path: _PathLike,
        *,
        quiet: bool | None = None,
        env: dict[str, str] | None = None,
        cwd: _PathLike | None = None,
        configs: list[_PathLike] | None = None,
    ) -> _t.Any:
        """
        Run lua ls.

        :param input_path:
            path to the directory/file that needs documentation.
        :param quiet:
            redefine `quiet` for this invocation. (see :func:`resolve`).
        :param env:
            redefine `env` for this invocation. (see :func:`resolve`).
        :param cwd:
            redefine `cmd` for this invocation. (see :func:`resolve`).
        :return:
            parsed documentation.

        :raises LuaLsRunError: Lua ls process failed with non-zero return code.

        """

        if quiet is None:
            quiet = self._quiet

        if env is None:
            env = self._env
        if env is None:
            env = os.environ.copy()
        else:
            env = env.copy()
        env["PATH"] = self._path

        if cwd is None:
            cwd = self._cwd

        if cwd is None:
            cwd = os.getcwd()

        with tempfile.TemporaryDirectory() as output_path:
            args: list[str | _PathLike]
            if self._backend == "emmylua":
                args = [
                    self._bin_path,
                    "-f",
                    "json",
                    "-o",
                    output_path,
                ]
                if configs:
                    args.append("-c")
                    args.extend(configs)
                args.append(input_path)
            else:
                args = [
                    self._bin_path,
                    "--doc",
                    input_path,
                    "--doc_out_path",
                    output_path,
                ]

            try:
                _logger.debug(
                    "running lua-language-server with args %r", args, type="lua-ls"
                )
                subprocess.run(
                    args,
                    capture_output=quiet,
                    env=env,
                    cwd=cwd,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                err = LuaLsRunError(
                    e.returncode,
                    e.cmd,
                    e.output,
                    e.stderr,
                )
                _logger.error("%s", err, type="lua-ls")
                raise err from None

            return json.loads(pathlib.Path(output_path, "doc.json").read_text())


class ProgressReporter:
    """
    Interface for reporting installation progress.

    """

    def start(self):
        """
        Called when installation starts.

        """

    def progress(self, desc: str, dl_size: int, total_size: int, speed: float, /):
        """
        Called to update current progress.

        :param desc:
            description of the currently performed operation.
        :param dl_size:
            when the installer downloads files, this number indicates
            number of bytes downloaded so far. Otherwise, it is set to zero.
        :param total_size:
            when the installer downloads files, this number indicates
            total number of bytes to download. Otherwise, it is set to zero.
        :param speed:
            when the installer downloads files, this number indicates
            current downloading speed, in bytes per second. Otherwise,
            it is set to zero.

        """

    def finish(self, exc_type, exc_val, exc_tb):
        """
        Called when installation finishes.

        """


class DefaultProgressReporter(ProgressReporter):
    """
    Default reporter that prints progress to stderr.

    """

    _prev_len = 0

    def __init__(self, stream: _t.TextIO | None = None):
        self.stream = stream or sys.stderr

    def progress(self, desc: str, dl_size: int, total_size: int, speed: float, /):
        desc = self.format_desc(desc)

        if total_size:
            desc += self.format_progress(dl_size, total_size, speed)

        self.write(desc.ljust(self._prev_len) + "\r")

        self._prev_len = len(desc)

    def finish(self, exc_type, exc_val, exc_tb):
        if exc_val:
            self.progress(f"installation failed: {red(exc_val)}", 0, 0, 0)
            self.write("\n")
        elif self._prev_len > 0:
            self.progress(f"installed", 0, 0, 0)
            self.write("\n")

    def format_desc(self, desc: str) -> str:
        return desc

    def format_progress(self, dl_size: int, total_size: int, speed: float) -> str:
        dl_size_mb = dl_size / 1024**2
        total_size_mb = total_size / 1024**2
        speed_mb = speed / 1024**2

        return f": {dl_size_mb:.1f}/{total_size_mb:.1f}MB - {speed_mb:.2f}MB/s"

    def write(self, msg: str):
        self.stream.write(msg)
        self.stream.flush()


class SphinxProgressReporter(DefaultProgressReporter):
    _prev_desc = None
    _prev_len = 0

    def __init__(self, verbosity: int):
        super().__init__()

        self._verbosity = verbosity

    def progress(self, desc: str, dl_size: int, total_size: int, speed: float, /):
        if self._verbosity:
            if desc != self._prev_desc:
                _logger.info("%s", desc, type="lua-ls")
        else:
            super().progress(desc, dl_size, total_size, speed)

        self._prev_desc = desc

    def format_desc(self, desc: str) -> str:
        return bold(desc + "...")

    def format_progress(self, dl_size: int, total_size: int, speed: float) -> str:
        dl_size_mb = dl_size / 1024**2
        total_size_mb = total_size / 1024**2
        speed_mb = speed / 1024**2
        progress = dl_size / total_size

        return f" [{progress: >3.0%}] {dl_size_mb:.1f}/{total_size_mb:.1f}MB ({speed_mb:.1f}MB/s)"

    def write(self, msg: str):
        _logger.info(msg, nonl=True, type="lua-ls")


def resolve(
    *,
    backend: _t.Literal["emmylua", "luals"],
    min_version: str | None,
    max_version: str | None,
    skip_versions: list[str] | None,
    cache_path: _PathLike | None = None,
    quiet: bool = True,
    env: dict[str, str] | None = None,
    cwd: _PathLike | None = None,
    install: bool = True,
    reporter: ProgressReporter = ProgressReporter(),
    timeout: int = 15,
    retry: _t.Optional[urllib3.Retry] = None,
):
    """
    Find a system LuaLs/EmmyLua installation or download it from GitHub.

    If language server is not installed, or it's outdated, try to download it
    and install it into `cache_path`.

    :param backend:
        which language server to use.
    :param cache_path:
        path where LuaLs binaries should be downloaded to.
    :param min_version:
        minimal LuaLs version required.
    :param max_version:
        maximal LuaLs version required. Version is not limited is `None`.
    :param skip_versions:
        list of known broken versions.
    :param quiet:
        if true (default), any output from the LuaLs binary is hidden.
    :param env:
        overrides environment variables for the LuaLs process.
    :param cwd:
        overrides current working directory for the LuaLs process.
    :param install:
        if false, disables installing LuaLs from GitHub.
    :param reporter:
        a hook that will be called to inform user about installation
        progress. See :class:`ProgressReporter` for API documentation,
        and :class:`DefaultProgressReporter` for an example.
    :param timeout:
        timeout in seconds for connecting to GitHub APIs.
    :param retry:
        retry policy for reading from GitHub and downloading releases.
        The default retry polity uses exponential backoff
        to avoid rate limiting.
    :return:
        resolved LuaLs installation.
    :raises LuaLsError:
        LuaLs not available or installation failed.

    """

    if cache_path is None:
        cache_path = default_cache_path()
    else:
        cache_path = pathlib.Path(cache_path)
    cache_path = cache_path.expanduser().resolve()

    _logger.debug("using cache path: %s", cache_path, type="lua-ls")

    if retry is None:
        retry = urllib3.Retry(10, backoff_factor=0.1)

    print(min_version, max_version, skip_versions)
    if min_version is None:
        if backend == "luals":
            min_version = "3.0.0"
        else:
            min_version = "0.11.0"
    if max_version == "__auto__":
        if backend == "luals":
            max_version = "4.0.0"
        else:
            max_version = "2.0.0"
    if skip_versions is None:
        if backend == "luals":
            skip_versions = KNOWN_BROKEN_LUA_LS_RELEASES
        else:
            skip_versions = KNOWN_BROKEN_EMMYLUA_RELEASES

    reporter.start()
    try:
        bin_path, path = _check_and_install(
            backend,
            min_version,
            max_version,
            skip_versions,
            cache_path,
            _get_path(env),
            install,
            reporter,
            timeout,
            retry,
        )
    finally:
        reporter.finish(*sys.exc_info())

    return LuaLs(
        _backend=backend,
        _bin_path=bin_path,
        _path=path,
        _quiet=quiet,
        _env=env,
        _cwd=cwd,
    )


def default_cache_path() -> pathlib.Path:
    """
    Return default path where LuaLs binaries should be downloaded to.

    Currently it is equal to ``pathlib.Path(tempfile.gettempdir()) / "python_lua_ls_cache"``.

    """

    if path := os.environ.get("LUA_LS_CACHE_PATH", None):
        return pathlib.Path(path)
    else:
        return pathlib.Path(tempfile.gettempdir()) / "python_lua_ls_cache"


def _get_path(env: dict[str, str] | None) -> str:
    path = (env or {}).get("PATH", None)
    if path is None:
        path = os.environ.get("PATH", None)
    if path is None:
        try:
            path = os.confstr("CS_PATH")
        except (AttributeError, ValueError):
            pass
    if path is None:
        path = os.defpath or ""
    return path


def _check_version(
    min_version: str,
    max_version: str | None,
    skip_versions: list[str],
    bin_path: _PathLike,
) -> _t.Tuple[bool, _t.Optional[str]]:
    min_version_tuple = tuple(int(c) for c in min_version.split("."))
    skip_version_tuples = [
        tuple(int(c) for c in version.split(".")) for version in skip_versions
    ]
    if max_version:
        max_version_tuple = tuple(int(c) for c in max_version.split("."))
        if max_version_tuple <= min_version_tuple:
            raise LuaLsError(
                "lua_ls_min_version is greater or equal to lua_ls_max_version: "
                f"{min_version} > {max_version}"
            )
    else:
        max_version_tuple = (math.inf,)
    try:
        _logger.debug("checking version of %a", bin_path, type="lua-ls")
        system_version_text_b = subprocess.check_output([bin_path, "--version"])
        system_version_text = system_version_text_b.decode().strip()
        if match := re.search(r"(\d+\.\d+\.\d+)", system_version_text):
            system_version = match.group(1)
            system_version_tuple = tuple(int(c) for c in system_version.split("."))
            if (
                min_version_tuple <= system_version_tuple < max_version_tuple
                and not _should_skip(system_version_tuple, skip_version_tuples)
            ):
                return True, system_version
            else:
                _logger.debug(
                    "%s is outdated (got %s, required %s..%s, skip=%r)",
                    bin_path,
                    system_version,
                    min_version,
                    max_version,
                    skip_versions,
                    type="lua-ls",
                )
                return False, system_version
        else:
            _logger.debug(
                "%s printed invalid version %r",
                bin_path,
                system_version_text,
                type="lua-ls",
            )
            return False, system_version_text
    except (subprocess.SubprocessError, OSError, UnicodeDecodeError):
        _logger.debug(
            "%s failed to print its version", bin_path, exc_info=True, type="lua-ls"
        )

    return False, None


def _check_and_install(
    backend: _t.Literal["emmylua", "luals"],
    min_version: str,
    max_version: str | None,
    skip_versions: list[str],
    cache_path: pathlib.Path,
    path: str,
    install: bool,
    reporter: ProgressReporter,
    timeout: int,
    retry: urllib3.Retry,
) -> _t.Tuple[pathlib.Path, str]:
    if min_version.startswith("v"):
        min_version = min_version[1:]
    if max_version and max_version.startswith("v"):
        max_version = max_version[1:]
    skip_versions = [version.removeprefix("v") for version in skip_versions]

    if backend == "emmylua":
        bin_name = "emmylua_doc_cli"
    else:
        bin_name = "lua-language-server"

    system_bin_path = shutil.which(bin_name, path=path)
    system_version = None
    if system_bin_path:
        can_use_system_lua_ls, system_version = _check_version(
            min_version, max_version, skip_versions, system_bin_path
        )
        if can_use_system_lua_ls:
            _logger.debug(
                "using pre-installed %s at %s",
                bin_name,
                system_bin_path,
                type="lua-ls",
            )
            return pathlib.Path(system_bin_path).expanduser().resolve(), path
        elif not install and system_version == "<Unknown>":
            _logger.warning(
                "found %s at %s, but its version is %r; "
                "trying to use it anyway because lua_ls_auto_install=False",
                bin_name,
                system_bin_path,
                system_version,
                type="lua-ls",
            )
            return pathlib.Path(system_bin_path).expanduser().resolve(), path
    else:
        _logger.debug("pre-installed %s not found", bin_name, type="lua-ls")

    machine = platform.machine().lower()
    if "arm" in machine:
        machine = "arm"

    if backend == "emmylua":
        return _install_emmylua(
            min_version,
            max_version,
            skip_versions,
            cache_path,
            path,
            install,
            reporter,
            timeout,
            retry,
            machine,
            sys.platform,
            system_bin_path,
            system_version,
        )
    else:
        return _install_lua_ls(
            min_version,
            max_version,
            skip_versions,
            cache_path,
            path,
            install,
            reporter,
            timeout,
            retry,
            machine,
            sys.platform,
            system_bin_path,
            system_version,
        )


def _make_version_message(
    min_version: str, max_version: str | None, skip_versions: list[str]
) -> str:
    if max_version:
        msg = f"a version between {min_version} and {max_version}"
    else:
        msg = f"version {min_version} or newer"
    if skip_versions:
        msg += ", and not " + ", ".join(skip_versions)
    return msg


def _install_lua_ls(
    min_version: str,
    max_version: str | None,
    skip_versions: list[str],
    cache_path: pathlib.Path,
    path: str,
    install: bool,
    reporter: ProgressReporter,
    timeout: int,
    retry: urllib3.Retry,
    machine: str,
    platform: str,
    system_bin_path: str | None,
    system_version: str | None,
    verify: bool = True,
):
    # Check system compatibility.

    release_names = {
        ("darwin", "arm"): "-darwin-arm64.tar.gz",
        ("darwin", "x86_64"): "-darwin-x64.tar.gz",
        ("linux", "arm"): "-linux-arm64.tar.gz",
        ("linux", "x86_64"): "-linux-x64.tar.gz",
        ("win32", "amd64"): "-win32-x64.zip",
    }

    release_name = release_names.get((platform, machine), None)
    if not install or not release_name:
        if system_bin_path:
            version = _make_version_message(min_version, max_version, skip_versions)
            raise LuaLsError(
                f"you have lua-language-server {system_version}, "
                f"but {version} is required; "
                f"see upgrade instructions "
                f"at https://lua_ls.github.io/#other-install"
            )
        else:
            raise LuaLsError(
                f"lua-language-server is not installed on your system; "
                f"see installation instructions "
                f"at https://lua_ls.github.io/#other-install"
            )

    # Check cached lua-ls

    cache_path.mkdir(parents=True, exist_ok=True)

    if platform == "win32":
        bin_path = cache_path / "bin/lua-language-server.exe"
    else:
        bin_path = cache_path / "bin/lua-language-server"
    if bin_path.exists():
        bin_path.chmod(bin_path.stat().st_mode | stat.S_IEXEC)
        can_use_cached_binary, _ = _check_version(
            min_version, max_version, skip_versions, bin_path
        )
        if can_use_cached_binary:
            _logger.debug("using cached lua-language-server", type="lua-ls")
            return bin_path, path

    # Download binary release.

    api = github.Github(retry=retry, timeout=timeout)

    filter = lambda name: name.endswith(release_name)

    with tempfile.TemporaryDirectory() as tmp_dir_s:
        tmp_dir = pathlib.Path(tmp_dir_s)

        try:
            tmp_file = _download_release(
                min_version,
                max_version,
                skip_versions,
                api,
                timeout,
                retry,
                "lua-language-server",
                "LuaLs/lua-language-server",
                tmp_dir,
                filter,
                reporter,
                platform,
                machine,
            )

            reporter.progress(f"processing lua-language-server", 0, 0, 0)

            _logger.debug("unpacking lua-language-server", type="lua-ls")

            shutil.unpack_archive(tmp_file, cache_path)

            if platform == "win32":
                bin_path = cache_path / "bin/lua-language-server.exe"
            else:
                bin_path = cache_path / "bin/lua-language-server"
            bin_path.chmod(bin_path.stat().st_mode | stat.S_IEXEC)
        except Exception as e:
            raise LuaLsError(
                f"lua-language-server install failed: {e}; "
                f"please install it manually -- see "
                f"https://lua_ls.github.io/#other-install"
            )

    if verify:
        can_use_cached_lua_ls, cached_version = _check_version(
            min_version, max_version, skip_versions, bin_path
        )
        if not can_use_cached_lua_ls:
            if cached_version is not None:
                version = _make_version_message(min_version, max_version, skip_versions)
                raise LuaLsError(
                    f"downloaded lua-language-server printed version {cached_version}, "
                    f"but {version} is required; are you sure lua_ls_min_version "
                    f"and lua_ls_max_version are correct?",
                )
            else:
                raise LuaLsError(
                    "downloaded lua-language-server failed to print its version"
                )
    elif not bin_path.exists():
        raise LuaLsError(
            f"downloaded latest lua-language-server is broken: "
            f"can't find {bin_path}",
        )

    return bin_path, path


def _install_emmylua(
    min_version: str,
    max_version: str | None,
    skip_versions: list[str],
    cache_path: pathlib.Path,
    path: str,
    install: bool,
    reporter: ProgressReporter,
    timeout: int,
    retry: urllib3.Retry,
    machine: str,
    platform: str,
    system_bin_path: str | None,
    system_version: str | None,
    verify: bool = True,
):
    release_names = {
        ("darwin", "arm"): "-darwin-arm64.tar.gz",
        ("darwin", "x86_64"): "-darwin-x64.tar.gz",
        ("linux", "arm"): "-linux-arm64.tar.gz",
        ("linux", "x86_64"): "-linux-x64.tar.gz",
        ("win32", "amd64"): "-win32-x64.zip",
    }

    release_name = release_names.get((platform, machine), None)
    if not install or not release_name:
        if system_bin_path:
            version = _make_version_message(min_version, max_version, skip_versions)
            raise LuaLsError(
                f"you have emmylua_doc_cli {system_version}, but {version} is required; "
                f"see upgrade instructions "
                f"at https://github.com/EmmyLuaLs/emmylua-analyzer-rust?tab=readme-ov-file#-installation"
            )
        else:
            raise LuaLsError(
                f"emmylua_doc_cli is not installed on your system; "
                f"see installation instructions "
                f"at https://github.com/EmmyLuaLs/emmylua-analyzer-rust?tab=readme-ov-file#-installation"
            )

    # Check cached lua-ls

    cache_path.mkdir(parents=True, exist_ok=True)

    if platform == "win32":
        bin_path = cache_path / "emmylua_doc_cli.exe"
    else:
        bin_path = cache_path / "emmylua_doc_cli"
    if bin_path.exists():
        bin_path.chmod(bin_path.stat().st_mode | stat.S_IEXEC)
        can_use_cached_binary, _ = _check_version(
            min_version, max_version, skip_versions, bin_path
        )
        if can_use_cached_binary:
            _logger.debug("using cached emmylua_doc_cli", type="lua-ls")
            return bin_path, path

    # Download binary release.

    api = github.Github(retry=retry, timeout=timeout)

    filter = lambda name: name.startswith("emmylua_doc_cli") and name.endswith(
        release_name
    )

    with tempfile.TemporaryDirectory() as tmp_dir_s:
        tmp_dir = pathlib.Path(tmp_dir_s)

        try:
            tmp_file = _download_release(
                min_version,
                max_version,
                skip_versions,
                api,
                timeout,
                retry,
                "emmylua_doc_cli",
                "EmmyLuaLs/emmylua-analyzer-rust",
                tmp_dir,
                filter,
                reporter,
                platform,
                machine,
            )

            reporter.progress(f"processing emmylua_doc_cli", 0, 0, 0)

            _logger.debug("unpacking emmylua_doc_cli", type="lua-ls")

            shutil.unpack_archive(tmp_file, cache_path)

            if platform == "win32":
                bin_path = cache_path / "emmylua_doc_cli.exe"
            else:
                bin_path = cache_path / "emmylua_doc_cli"
            bin_path.chmod(bin_path.stat().st_mode | stat.S_IEXEC)
        except Exception as e:
            raise LuaLsError(
                f"emmylua_doc_cli install failed: {e}; "
                f"please install it manually -- see "
                f"https://github.com/EmmyLuaLs/emmylua-analyzer-rust?tab=readme-ov-file#-installation"
            )

    if verify:
        can_use_cached_lua_ls, cached_version = _check_version(
            min_version, max_version, skip_versions, bin_path
        )
        if not can_use_cached_lua_ls:
            if cached_version is not None:
                version = _make_version_message(min_version, max_version, skip_versions)
                raise LuaLsError(
                    f"downloaded emmylua_doc_cli printed version {cached_version}, "
                    f"but {version} is required; are you sure lua_ls_min_version "
                    f"and lua_ls_max_version are correct?",
                )
            else:
                raise LuaLsError(
                    "downloaded emmylua_doc_cli failed to print its version"
                )
    elif not bin_path.exists():
        raise LuaLsError(
            f"downloaded latest emmylua_doc_cli is broken: " f"can't find {bin_path}",
        )

    return bin_path, path


def _download_release(
    min_version: str,
    max_version: str | None,
    skip_versions: list[str],
    api: github.Github,
    timeout: int,
    retry: urllib3.Retry,
    name: str,
    repo_name: str,
    dest: pathlib.Path,
    filter: _t.Callable[[str], bool],
    reporter: ProgressReporter,
    platform: str,
    machine: str,
):
    min_version_tuple = tuple(int(c) for c in min_version.split("."))
    skip_version_tuples = [
        tuple(int(c) for c in version.split(".")) for version in skip_versions
    ]
    if max_version:
        max_version_tuple = tuple(int(c) for c in max_version.split("."))
    else:
        max_version_tuple = (math.inf,)

    reporter.progress(f"resolving {name}", 0, 0, 0)

    repo = api.get_repo(repo_name)

    for release in repo.get_releases():
        if release.draft or release.prerelease:
            continue

        _logger.debug("found %s release %s", name, release.tag_name, type="lua-ls")

        if match := re.search(r"(\d+\.\d+\.\d+)", release.tag_name):
            release_version = match.group(1)
            release_version_tuple = tuple(int(c) for c in release_version.split("."))
            if not (
                min_version_tuple <= release_version_tuple < max_version_tuple
                and not _should_skip(release_version_tuple, skip_version_tuples)
            ):
                _logger.debug(
                    "release is outside of allowed version range", type="lua-ls"
                )
                continue
        else:
            _logger.debug("can't parse release tag", type="lua-ls")
            continue

        for asset in release.assets:
            _logger.debug("trying %s asset %s", name, asset.name, type="lua-ls")
            if filter(asset.name):
                _logger.debug("found %s asset %s", name, asset.name, type="lua-ls")
                basename = asset.name
                browser_download_url = asset.browser_download_url
                break
        else:
            raise LuaLsError(f"unable to find {name} release for {platform}-{machine}")

        break
    else:
        version = _make_version_message(min_version, max_version, skip_versions)
        raise LuaLsError(f"unable to find {name} release for {version}")

    _logger.debug("downloading %s from %s", name, browser_download_url, type="lua-ls")

    with requests.Session() as session:
        adapter = requests.adapters.HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        with requests.get(browser_download_url, stream=True, timeout=timeout) as stream:
            stream.raise_for_status()

            try:
                size = int(stream.headers["content-length"])
            except (KeyError, ValueError):
                size = -1
            downloaded = 0

            reporter.progress(f"downloading {name}", downloaded, size, 0)

            start = datetime.datetime.now()

            with open(dest / basename, "wb") as dest_file:
                for chunk in stream.iter_content(64 * 1024):
                    dest_file.write(chunk)
                    if size:
                        # note: this does not take content-encoding into account.
                        # our contents are not encoded, though, so this is fine.
                        time = (datetime.datetime.now() - start).total_seconds()
                        downloaded += len(chunk)
                        speed = downloaded / time if time else 0
                        reporter.progress(
                            f"downloading {name}", downloaded, size, speed
                        )

    return dest / basename


def _should_skip(version: tuple[int, ...], skip_versions: list[tuple[int, ...]]):
    for skip_version in skip_versions:
        if len(version) < len(skip_version):
            version += (0,) * (len(skip_version) - len(version))
        if skip_version == version[: len(skip_version)]:
            return True
    return False


if __name__ == "__main__":

    def main():
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--runtime", choices=["luals", "emmylua"], default="luals")
        parser.add_argument("platform")
        parser.add_argument("machine")
        parser.add_argument("--min", default="0.0.0")
        parser.add_argument("--max", default=None)
        parser.add_argument("--skip", action="append", default=None)
        parser.add_argument("path", type=pathlib.Path)

        _logger.setLevel("DEBUG")
        _logger.logger.addHandler(
            logging.NewLineStreamHandler(logging.SafeEncodingWriter(sys.stderr))
        )

        args = parser.parse_args()

        if args.skip is None:
            if args.runtime == "luals":
                args.skip = KNOWN_BROKEN_LUA_LS_RELEASES
            else:
                args.skip = KNOWN_BROKEN_EMMYLUA_RELEASES

        match args.runtime:
            case "luals":
                _install_lua_ls(
                    args.min,
                    args.max,
                    args.skip,
                    args.path,
                    _get_path(None),
                    True,
                    DefaultProgressReporter(),
                    15,
                    urllib3.Retry(10, backoff_factor=0.1),
                    args.machine,
                    args.platform,
                    None,
                    None,
                    False,
                )
            case "emmylua":
                _install_emmylua(
                    args.min,
                    args.max,
                    args.skip,
                    args.path,
                    _get_path(None),
                    True,
                    DefaultProgressReporter(),
                    15,
                    urllib3.Retry(10, backoff_factor=0.1),
                    args.machine,
                    args.platform,
                    None,
                    None,
                    False,
                )
            case _:
                parser.error(f"unknown runtime {args.runtime}")

    main()
