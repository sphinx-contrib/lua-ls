import os
import pathlib
from typing import Any, Callable

import jinja2
import sphinx.errors

from sphinx_lua_ls.autodoc import AutoObjectDirective, _iter_children
from sphinx_lua_ls.objtree import Kind, Object

_ENV = jinja2.Environment()
_ENV.filters["h1"] = lambda title: f"{title}\n{'=' * len(title)}"  # type: ignore
_ENV.filters["h2"] = lambda title: f"{title}\n{'-' * len(title)}"  # type: ignore
_ENV.filters["h3"] = lambda title: f"{title}\n{'~' * len(title)}"  # type: ignore


_TEMPLATE = _ENV.from_string(
    """{{ title | h1 }}

{% if submodules %}
.. toctree::
   :hidden:

   {% for _, child_filename in submodules.items() %}
   {{ child_filename }}.rst
   {% endfor %}
{% endif %}

.. lua:autoobject:: {{ fullname }}
   {% for option, value in options.items() %}:{{ option }}: {{ value }}
   {% endfor %}
""".lstrip()
)


def generate(
    dir: pathlib.Path,
    fullname: str,
    objtree: Object,
    options: dict[str, Any],
    depth: int,
    mod_filter: Callable[[str], Any],
):
    dir.mkdir(parents=True, exist_ok=True)

    options.setdefault("members", True)
    options.setdefault("recursive", True)
    options.setdefault("index-table", True)

    files: set[pathlib.Path] = set()
    _generate(
        dir,
        fullname,
        objtree,
        "",
        depth,
        options,
        mod_filter,
        files,
    )

    removed: set[pathlib.Path] = set(dir.glob("*.rst"))
    removed -= files

    for file in removed:
        os.remove(file)


def _generate(
    dir: pathlib.Path,
    fullname: str,
    objtree: Object,
    filename: str,
    depth: int,
    options: dict[str, Any],
    mod_filter: Callable[[str], Any],
    files: set[pathlib.Path],
):
    obj = objtree.find(fullname)
    if not obj:
        raise sphinx.errors.ConfigError(f"can't find module {fullname}")

    if obj.kind != Kind.Module:
        raise sphinx.errors.ConfigError(
            f"lua apidoc can only work with modules, "
            f"instead it got {obj.kind} {fullname}"
        )

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
        autodoc_options["exclude-members"] = set()
    else:
        autodoc_options["exclude-members"] = autodoc_options["exclude-members"].copy()

    submodules: dict[str, str] = {}

    if depth > 0:
        for child_name, child in _iter_children(obj, objtree, None, autodoc_options):
            if child.kind == Kind.Module:
                child_fullname = f"{fullname}.{child_name}"
                child_filename = f"{filename}.{child_name}" if filename else child_name
                autodoc_options["exclude-members"].add(child_name)
                if not mod_filter(child_fullname):
                    submodules[child_fullname] = child_filename

    for option_name in autodoc_options:
        if autodoc_options[option_name] in (None, True):
            autodoc_options[option_name] = ""
        elif isinstance(autodoc_options[option_name], (set, list)):
            autodoc_options[option_name] = ", ".join(
                sorted(autodoc_options[option_name])
            )

    page = _TEMPLATE.render(
        title=f"Module ``{fullname}``",
        fullname=fullname,
        options=autodoc_options,
        submodules=submodules,
    )

    filepath = dir / f"{filename or 'index'}.rst"
    if not filepath.exists() or filepath.read_text() != page:
        filepath.write_text(page)
    files.add(filepath)

    for child_fullname, child_filename in submodules.items():
        _generate(
            dir,
            child_fullname,
            objtree,
            child_filename,
            depth - 1,
            options,
            mod_filter,
            files,
        )
