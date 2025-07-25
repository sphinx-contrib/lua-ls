import os
import pathlib
import subprocess
import sys
import urllib.parse
from typing import Any, Callable

import jinja2
import sphinx.errors
from sphinx.util import logging

from sphinx_lua_ls.autodoc import AutoObjectDirective, _iter_children
from sphinx_lua_ls.domain import LuaDomain
from sphinx_lua_ls.objtree import Kind, Object
from sphinx_lua_ls.utils import normalize_name

_logger = logging.getLogger("sphinx_lua_ls")

_ENV = jinja2.Environment()
_ENV.filters["h1"] = lambda title: f"{title}\n{'=' * len(title)}"  # type: ignore
_ENV.filters["h2"] = lambda title: f"{title}\n{'-' * len(title)}"  # type: ignore
_ENV.filters["h3"] = lambda title: f"{title}\n{'~' * len(title)}"  # type: ignore
_ENV.filters["mangle"] = lambda name: _mangle_filename(name)  # type: ignore

_TEMPLATE_RST = _ENV.from_string(
    """{{ title | h1 }}

.. lua:currentmodule:: {{ parent_modname }}

.. lua:autoobject:: {{ fullname }}
   {% for option, value in options.items() %}:{{ option }}: {{ value }}
   {% endfor %}

{% if submodules %}
.. toctree::
   :hidden:

   {% for child_fullname in submodules %}
   {{ child_fullname | mangle }}.rst
   {% endfor %}
{% endif %}
""".lstrip()
)

_TEMPLATE_MD = _ENV.from_string(
    """# {{ title }}

```{lua:currentmodule} {{ parent_modname }}
```

```{lua:autoobject} {{ fullname }}
{% for option, value in options.items() %}:{{ option }}: {{ value }}
{% endfor %}
```

{% if submodules %}
```{toctree}
:hidden:

{% for child_fullname in submodules %}
{{ child_fullname | mangle }}.md
{% endfor %}
```
{% endif %}
""".lstrip()
)


def generate(
    outdir: pathlib.Path,
    domain: LuaDomain,
    dir: pathlib.Path,
    fullname: str,
    objtree: Object,
    options: dict[str, Any],
    depth: int,
    mod_filter: Callable[[str], Any],
    format: str,
    separate_members: bool,
):
    dir_is_case_sensitive = _make_case_sensitive(dir)
    out_is_case_sensitive = _make_case_sensitive(outdir)
    is_case_insensitive = not dir_is_case_sensitive or not out_is_case_sensitive

    options.setdefault("members", True)
    options.setdefault("recursive", True)
    options.setdefault("index-table", True)

    # Note: it's important to work with string file paths
    # due to case sensitivity issues.
    files: set[str] = set()
    _generate(
        domain=domain,
        dir=dir,
        fullname=fullname,
        objtree=objtree,
        depth=depth,
        options=options,
        mod_filter=mod_filter,
        files=files,
        format=format,
        separate_members=separate_members,
        is_toplevel=True,
    )

    if (is_case_insensitive or pathlib.Path("a") == pathlib.Path("A")) and (
        len(files) != len({f.lower() for f in files})
    ):
        msg = (
            "Running Lua apidoc on case-insensitive file system."
            "\nIf you experience issues, see documentation for potential solutions:"
            "\n    https://taminomara.github.io/sphinx-lua-ls/settings.html#lua_ls_apidoc_separate_members"
        )
        if sys.platform == "win32" and is_case_insensitive:
            msg += (
                "\nYou can make relevant directories case-sensitive by running:"
                f'\n    fsutil.exe file setCaseSensitiveInfo "{dir}" enable'
                f'\n    fsutil.exe file setCaseSensitiveInfo "{outdir}" enable'
                "\nSee more info at:"
                "\n    https://learn.microsoft.com/en-us/windows/wsl/case-sensitivity"
            )
        _logger.warning(msg, type="lua-ls")

    removed: set[str] = {str(f) for f in dir.iterdir()}
    removed -= files

    for file in removed:
        os.remove(file)


def _generate(
    domain: LuaDomain,
    dir: pathlib.Path,
    fullname: str,
    objtree: Object,
    depth: int,
    options: dict[str, Any],
    mod_filter: Callable[[str], Any],
    files: set[str],
    format: str,
    separate_members: bool,
    is_toplevel: bool,
    is_global: bool = False,
    parent_modname: str | None = None,
):
    obj = objtree.find(fullname)
    if not obj:
        raise sphinx.errors.ConfigError(f"can't find module {fullname}")

    autodoc_options = options.copy()
    for name, value in obj.parsed_options.items():
        if name in AutoObjectDirective.option_spec:
            try:
                autodoc_options[name] = AutoObjectDirective.option_spec[name](value)
            except ValueError as e:
                raise sphinx.errors.DocumentError(
                    f"invalid !doc option {name} in object {fullname}: {e}"
                ) from None
        else:
            raise sphinx.errors.DocumentError(
                f"unknown !doc option {name} in object {fullname}"
            )
    if (
        "exclude-members" not in autodoc_options
        or autodoc_options["exclude-members"] is True
    ):
        exclude_members = set()
    else:
        exclude_members = autodoc_options["exclude-members"].copy()

    submodules: dict[str, bool] = {}

    if depth > 0 and obj.kind == Kind.Module:
        for child_name, child in _iter_children(obj, objtree, None, autodoc_options):
            if child.kind != Kind.Module and not separate_members:
                continue
            if child.is_toplevel:
                child_fullname = child_name
                child_is_global = True
            else:
                child_fullname = f"{fullname}.{child_name}"
                child_is_global = False
            exclude_members.add(child_name)
            if not mod_filter(child_fullname):
                submodules[child_fullname] = child_is_global

    autodoc_options["exclude-members"] = exclude_members

    for option_name in autodoc_options:
        if autodoc_options[option_name] in (None, True):
            autodoc_options[option_name] = ""
        elif isinstance(autodoc_options[option_name], (set, list)):
            autodoc_options[option_name] = ", ".join(
                sorted(autodoc_options[option_name])
            )
    if is_global:
        autodoc_options["global"] = ""
        autodoc_options["module"] = ""
        lname = "Global"
    elif obj.kind:
        lname = LuaDomain.object_types[obj.kind.value].lname.title()
    else:
        lname = "Object"

    match format:
        case "rst":
            template = _TEMPLATE_RST
            title = f"{lname} ``{fullname}``"
        case "md":
            template = _TEMPLATE_MD
            title = f"{lname} `{fullname}`"
        case _:
            raise sphinx.errors.ConfigError(f"unknown apidoc format {format}")

    page = template.render(
        title=title,
        fullname=fullname,
        options=autodoc_options,
        submodules=submodules,
        parent_modname=parent_modname or "None",
    )

    if is_toplevel:
        filepath = dir / f"index.{format}"
    else:
        filepath = dir / f"{_mangle_filename(fullname)}.{format}"
    if not filepath.exists() or filepath.read_text() != page:
        filepath.write_text(page)
    files.add(str(filepath))

    for child_fullname, child_is_global in submodules.items():
        _generate(
            domain=domain,
            dir=dir,
            fullname=child_fullname,
            objtree=objtree,
            depth=depth - 1,
            options=options,
            mod_filter=mod_filter,
            files=files,
            format=format,
            separate_members=separate_members,
            is_toplevel=False,
            is_global=child_is_global,
            parent_modname=fullname if child_is_global else parent_modname,
        )


def _make_case_sensitive(dir: pathlib.Path) -> bool:
    dir.mkdir(parents=True, exist_ok=True)

    if not _fs_is_case_insensitive(dir):
        return True

    if sys.platform == "win32":
        _logger.info(
            "trying to switch directory to case-insensitive mode: %s",
            dir,
            type="lua-ls",
        )

        retcode = subprocess.call(
            ["fsutil.exe", "file", "setCaseSensitiveInfo", dir, "enable"]
        )

        if retcode != 0:
            return False
        else:
            return not _fs_is_case_insensitive(dir)

    return False


def _fs_is_case_insensitive(dir: pathlib.Path) -> bool:
    f1 = dir / "__sphinx_lua_ls_CASE_SENSITIVITY_TEST"
    f2 = dir / "__sphinx_lua_ls_case_sensitivity_test"

    if f1.exists():
        os.remove(f1)
    if f2.exists():
        os.remove(f2)

    try:
        f1.touch()
        return f2.exists()
    finally:
        if f1.exists():
            os.remove(f1)
        if f2.exists():
            os.remove(f2)


def _mangle_filename(name: str) -> str:
    # We don't want to urlencode the file name because we'll end up with double
    # encoding in all references. So, we use `!` instead of `%`.
    return urllib.parse.quote(normalize_name(name), safe="()[]").replace("%", "!")
