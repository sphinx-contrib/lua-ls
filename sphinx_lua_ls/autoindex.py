from collections import defaultdict

import docutils.nodes
import sphinx.addnodes
from sphinx.transforms import SphinxTransform
from sphinx.util.docutils import SphinxDirective

import sphinx_lua_ls.domain
from sphinx_lua_ls import utils
from sphinx_lua_ls.objtree import Kind


class AutoIndexNode(docutils.nodes.Element):
    pass


class AutoIndexDirective(SphinxDirective):
    has_content = False
    required_arguments = 0
    optional_arguments = 1
    final_argument_whitespace = True

    def run(self) -> list[docutils.nodes.Node]:
        module = (
            self.arguments[0]
            if self.arguments
            else self.env.ref_context.get("lua:module", "")
        )
        if not module:
            raise self.error("module name is required")
        return [AutoIndexNode("", target=utils.normalize_name(module))]


class AutoIndexTransform(SphinxTransform):
    default_priority = 750

    _CANON_OBJTYPE = {
        "function": "function",
        "data": "data",
        "const": "data",
        "class": "class",
        "alias": "alias",
        "enum": "enum",
        "method": "function",
        "classmethod": "function",
        "staticmethod": "function",
        "attribute": "data",
        "table": "data",
        "module": "module",
    }

    @property
    def domain(self) -> sphinx_lua_ls.domain.LuaDomain:
        return self.env.get_domain("lua")  # type: ignore

    def apply(self, **kwargs):
        node: AutoIndexNode
        for node in list(self.document.findall(AutoIndexNode)):
            target: str = node["target"]
            objects: dict[str, list[tuple[str, str, str, str]]] = defaultdict(list)

            if globals := self.domain.globals.get(target, None):
                for data in globals.entries:
                    fullname = data.fullname
                    if data := self.domain.objects.get(fullname, None):
                        objects["global"].append(
                            (fullname, fullname, data.docname, data.synopsis or "")
                        )

            prefix = target + "."
            if members := self.domain.members.get(target, None):
                for data in members.entries:
                    fullname = data.fullname
                    if data := self.domain.objects.get(fullname, None):
                        name = fullname[len(prefix) :]
                        objects[
                            self._CANON_OBJTYPE.get(data.objtype, data.objtype)
                        ].append((name, fullname, data.docname, data.synopsis or ""))

            node.replace_self(
                docutils.nodes.container(
                    "", *self.render_index(objects), classes=["lua-index"]
                )
            )

    def render_index(
        self, objects: dict[str, list[tuple[str, str, str, str]]]
    ) -> list[docutils.nodes.Node]:
        nodes: list[docutils.nodes.Node] = []

        if "global" in objects:
            nodes.extend(self.render_type("global", objects.pop("global")))
        for kind in Kind:
            objtype = kind.value
            if objtype in objects:
                nodes.extend(self.render_type(objtype, objects.pop(objtype)))
        for objtype in sorted(objects):
            nodes.extend(self.render_type(objtype, objects[objtype]))

        return nodes

    def render_type(
        self, objtype: str, objects: list[tuple[str, str, str, str]]
    ) -> list[docutils.nodes.Node]:
        if objtype in self.domain.object_types:
            lname = self.domain.object_types[objtype].lname
        else:
            lname = objtype

        tbody = docutils.nodes.tbody()
        nodes: list[docutils.nodes.Node] = [
            docutils.nodes.paragraph("", "", docutils.nodes.strong("", lname.title())),
            docutils.nodes.table(
                "",
                docutils.nodes.tgroup(
                    "",
                    docutils.nodes.colspec(colwidth=33),
                    docutils.nodes.colspec(colwidth=66),
                    tbody,
                    cols=2,
                ),
                classes=["table", "lua-index-table", "colwidths-given"],
            ),
        ]

        for name, fullname, _, synopsis in sorted(
            objects, key=lambda x: x[0].casefold()
        ):
            row = docutils.nodes.row()
            tbody += row

            contnode = docutils.nodes.literal("", name)
            ref = (
                self.domain.resolve_xref(
                    self.env,
                    self.env.docname,
                    self.app.builder,
                    "obj",
                    fullname,
                    sphinx.addnodes.pending_xref(""),
                    contnode,
                )
                or contnode
            )

            row += docutils.nodes.entry("", docutils.nodes.paragraph("", "", ref))

            if synopsis:
                row += docutils.nodes.entry("", docutils.nodes.paragraph("", synopsis))
            else:
                row += docutils.nodes.entry()

        return nodes
