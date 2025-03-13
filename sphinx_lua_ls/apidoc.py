import os
import pathlib
from typing import Any

import jinja2

from sphinx_lua_ls.objtree import Kind, Object, Visibility

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
    root: Object,
    options: dict[str, Any],
    depth: int = 4,
):
    dir.mkdir(parents=True, exist_ok=True)

    (dir / ".gitignore").write_text("*\n")

    options.setdefault("members", "")
    options.setdefault("recursive", "")
    options.setdefault("index-table", "")

    files: set[pathlib.Path] = set()
    _generate(
        dir,
        fullname,
        root,
        "",
        depth,
        options,
        files,
    )

    removed: set[pathlib.Path] = set(dir.glob("*.rst"))
    removed -= files

    for file in removed:
        os.remove(file)


def _generate(
    dir: pathlib.Path,
    fullname: str,
    root: Object,
    filename: str,
    depth: int,
    options: dict[str, Any],
    files: set[pathlib.Path],
):
    found = root.find_path(fullname)
    if not found:
        raise ValueError(f"can't find module {fullname}")
    obj, _, classname, _ = found

    if (
        obj.kind != Kind.Module
        or obj.parsed_doctype not in [None, "module"]
        or classname
    ):
        raise RuntimeError(
            "lua apidoc can only work with modules"
        )  # TODO: better error message

    autodoc_options = options.copy()
    if (
        "exclude-members" not in autodoc_options
        or autodoc_options["exclude-members"] is True
    ):
        autodoc_options["exclude-members"] = set()
    else:
        autodoc_options["exclude-members"] = autodoc_options["exclude-members"].copy()

    submodules: dict[str, str] = {}

    for child_name, child in obj.children.items():
        if child_name in autodoc_options["exclude-members"]:
            continue
        is_private = (
            child.visibility == Visibility.Private or "private" in child.parsed_options
        )
        if is_private and "private-members" not in options:
            continue
        is_protected = (
            child.visibility == Visibility.Protected
            or "protected" in child.parsed_options
        )
        if is_protected and "protected-members" not in options:
            continue
        is_package = (
            child.visibility == Visibility.Package or "package" in child.parsed_options
        )
        if is_package and "package-members" not in options:
            continue

        if (
            depth > 0
            and child.kind == Kind.Module
            and root.parsed_doctype in [None, "module"]
        ):
            child_fullname = f"{fullname}.{child_name}"
            child_filename = f"{filename}.{child_name}" if filename else child_name
            submodules[child_fullname] = child_filename
            autodoc_options["exclude-members"].add(child_name)

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
            root,
            child_filename,
            depth - 1,
            options,
            files,
        )
