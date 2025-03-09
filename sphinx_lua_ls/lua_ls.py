"""
Wrapper around the Lua-LS executable; able to download lua-ls if it's not installed.

"""

import datetime
import json
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
from sphinx.util import logging
from sphinx.util.console import bold  # type: ignore

_PathLike: _t.TypeAlias = str | os.PathLike[str]


_logger = logging.getLogger("sphinx_lua_ls")


class LuaLsError(Exception):
    """
    Raised when LuaLS is unavailable, or when installation fails.

    """


class LuaLsRunError(LuaLsError, subprocess.CalledProcessError):
    """
    Raised when LuaLS process fails.

    """

    def __str__(self):
        if self.returncode and self.returncode < 0:
            try:
                returncode = f"signal {signal.Signals(-self.returncode)}"
            except ValueError:
                returncode = f"unknown signal {self.returncode}"
        else:
            returncode = f"code {self.returncode}"

        msg = f"LuaLS run failed with {returncode}"
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
        _lua_ls_path: pathlib.Path,
        _path: str,
        _quiet: bool = True,
        _env: dict[str, str] | None = None,
        _cwd: _PathLike | None = None,
    ):
        self._lua_ls_path = _lua_ls_path
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
    ) -> _t.Any:
        """
        Renter the given VHS file.

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

        :raises LuaLsRunError: VHS process failed with non-zero return code.

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

        with tempfile.TemporaryDirectory() as output_path:
            args: list[str | _PathLike] = [
                self._lua_ls_path,
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
                raise LuaLsRunError(
                    e.returncode,
                    e.cmd,
                    e.output,
                    e.stderr,
                ) from None

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
            self.progress(f"lua_ls installation failed: {exc_val}", 0, 0, 0)
            self.write("\n")
        elif self._prev_len > 0:
            self.progress(f"lua_ls installed", 0, 0, 0)
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
    cache_path: _PathLike | None = None,
    min_version: str = "3.0.0",
    quiet: bool = True,
    env: dict[str, str] | None = None,
    cwd: _PathLike | None = None,
    install: bool = True,
    reporter: ProgressReporter = ProgressReporter(),
    timeout: int = 15,
    retry: _t.Optional[urllib3.Retry] = None,
):
    """
    Find a system LuaLS installation or download LuaLS from GitHub.

    If LuaLS is not installed, or it's outdated, try to download it
    and install it into `cache_path`.

    Automatic download only works on 64-bit Linux.
    MacOS users will be presented with an instruction to use `brew`,
    and other systems users will get a link to LuaLS installation guide.

    :param cache_path:
        path where LuaLS binaries should be downloaded to.
    :param min_version:
        minimal LuaLS version required.
    :param quiet:
        if true (default), any output from the LuaLS binary is hidden.
    :param env:
        overrides environment variables for the LuaLS process.
    :param cwd:
        overrides current working directory for the LuaLS process.
    :param install:
        if false, disables installing LuaLS from GitHub.
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
        resolved LuaLS installation.
    :raises LuaLsError:
        LuaLS not available or installation failed.

    """

    if cache_path is None:
        cache_path = default_cache_path()
    else:
        cache_path = pathlib.Path(cache_path)
    cache_path = cache_path.expanduser().resolve()

    _logger.debug("using lua_ls cache path: %s", cache_path, type="lua-ls")

    if retry is None:
        retry = urllib3.Retry(10, backoff_factor=0.1)

    reporter.start()
    try:
        lua_ls_path, path = _check_and_install(
            min_version, cache_path, _get_path(env), install, reporter, timeout, retry
        )
    finally:
        reporter.finish(*sys.exc_info())

    return LuaLs(
        _lua_ls_path=lua_ls_path,
        _path=path,
        _quiet=quiet,
        _env=env,
        _cwd=cwd,
    )


def default_cache_path() -> pathlib.Path:
    """
    Return default path where LuaLS binaries should be downloaded to.

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
    version: str, lua_ls_path: _PathLike
) -> _t.Tuple[bool, _t.Optional[str]]:
    version_tuple = tuple(int(c) for c in version.split("."))
    try:
        _logger.debug("checking version of %a", lua_ls_path, type="lua-ls")
        system_version_text_b = subprocess.check_output([lua_ls_path, "--version"])
        system_version_text = system_version_text_b.decode().strip()
        if match := re.search(r"(\d+\.\d+\.\d+)", system_version_text):
            system_version = match.group(1)
            system_version_tuple = tuple(int(c) for c in system_version.split("."))
            if system_version_tuple >= version_tuple:
                return True, system_version
            else:
                _logger.debug(
                    "%s is outdated (got %s, required %s)",
                    lua_ls_path,
                    system_version,
                    version,
                    type="lua-ls",
                )
                return False, system_version
        else:
            _logger.debug(
                "%s printed invalid version %r",
                lua_ls_path,
                system_version_text,
                type="lua-ls",
            )
    except (subprocess.SubprocessError, OSError, UnicodeDecodeError):
        _logger.debug(
            "%s failed to print its version", lua_ls_path, exc_info=True, type="lua-ls"
        )

    return False, None


def _check_and_install(
    version: str,
    cache_path: pathlib.Path,
    path: str,
    install: bool,
    reporter: ProgressReporter,
    timeout: int,
    retry: urllib3.Retry,
) -> _t.Tuple[pathlib.Path, str]:
    if version.startswith("v"):
        version = version[1:]

    # Check system lua_ls

    system_lua_ls_path = shutil.which("lua-language-server", path=path)
    system_version = None
    if system_lua_ls_path:
        can_use_system_lua_ls, system_version = _check_version(
            version, system_lua_ls_path
        )
        if can_use_system_lua_ls:
            _logger.debug(
                "using pre-installed lua-language-server at %s",
                system_lua_ls_path,
                type="lua-ls",
            )
            return pathlib.Path(system_lua_ls_path).expanduser().resolve(), path
    else:
        _logger.debug("pre-installed lua-language-server not found", type="lua-ls")

    machine = platform.machine().lower()
    if "arm" in machine:
        machine = "arm"

    return _install(
        version,
        cache_path,
        path,
        install,
        reporter,
        timeout,
        retry,
        machine,
        sys.platform,
        system_lua_ls_path,
        system_version,
    )


def _install(
    version: str,
    cache_path: pathlib.Path,
    path: str,
    install: bool,
    reporter: ProgressReporter,
    timeout: int,
    retry: urllib3.Retry,
    machine: str,
    platform: str,
    system_lua_ls_path: str | None,
    system_version: str | None,
    verify: bool = False,
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
        if system_lua_ls_path:
            raise LuaLsError(
                f"you have lua-language-server {system_version}, "
                f"but version {version} or newer is required; "
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
        can_use_cached_lua_ls, _ = _check_version(version, bin_path)
        if can_use_cached_lua_ls:
            _logger.debug("using cached lua-language-server", type="lua-ls")
            return bin_path, path

    # Download binary release.

    api = github.Github(retry=retry, timeout=timeout)

    _install_lua_ls(api, timeout, retry, cache_path, reporter, release_name, platform)

    if verify:
        can_use_cached_lua_ls, _ = _check_version(version, bin_path)
        if not can_use_cached_lua_ls:
            raise LuaLsError(
                "downloaded latest lua-language-server is outdated; "
                "are you sure min_lua_ls_version is correct?",
            )
    elif not bin_path.exists():
        raise LuaLsError(
            f"downloaded latest lua-language-server is broken: "
            f"can't find {bin_path}",
        )

    return bin_path, path


def _install_lua_ls(
    api: github.Github,
    timeout: int,
    retry: urllib3.Retry,
    cache_path: pathlib.Path,
    reporter: ProgressReporter,
    release_name: str,
    platform: str,
):
    filter = lambda name: name.endswith(release_name)

    with tempfile.TemporaryDirectory() as tmp_dir_s:
        tmp_dir = pathlib.Path(tmp_dir_s)

        try:
            tmp_file = _download_latest_release(
                api,
                timeout,
                retry,
                "lua-language-server",
                "LuaLS/lua-language-server",
                tmp_dir,
                filter,
                reporter,
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
            raise LuaLsError(f"lua-language-server install failed: {e}")


def _download_latest_release(
    api: github.Github,
    timeout: int,
    retry: urllib3.Retry,
    name: str,
    repo_name: str,
    dest: pathlib.Path,
    filter: _t.Callable[[str], bool],
    reporter: ProgressReporter,
):
    reporter.progress(f"resolving {name}", 0, 0, 0)

    repo = api.get_repo(repo_name)

    for release in repo.get_releases():
        if release.draft or release.prerelease:
            continue

        _logger.debug("found %s release %s", name, release.tag_name, type="lua-ls")

        for asset in release.assets:
            _logger.debug("trying %s asset %s", name, asset.name, type="lua-ls")
            if filter(asset.name):
                _logger.debug("found %s asset %s", name, asset.name, type="lua-ls")
                basename = asset.name
                browser_download_url = asset.browser_download_url
                break
        else:
            raise LuaLsError(
                f"unable to find {name} release for platform {sys.platform}"
            )

        break
    else:
        raise LuaLsError(f"unable to find latest {name} release")

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


if __name__ == "__main__":

    def main():
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("platform")
        parser.add_argument("machine")
        parser.add_argument("path", type=pathlib.Path)

        _logger.setLevel("DEBUG")
        _logger.logger.addHandler(
            logging.NewLineStreamHandler(logging.SafeEncodingWriter(sys.stderr))
        )

        args = parser.parse_args()

        _install(
            "3.0.0",
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

    main()
