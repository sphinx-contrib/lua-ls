import typing as _t
from collections import defaultdict

import docutils.nodes
import sphinx.addnodes
from sphinx.transforms import SphinxTransform
from sphinx.util.docutils import SphinxDirective

import sphinx_lua_ls.domain
from sphinx_lua_ls import utils


class InheritedMethodsNode(docutils.nodes.Element):
    pass


class InheritedMembersDirective(SphinxDirective):
    has_content = False
    required_arguments = 0
    optional_arguments = 1
    final_argument_whitespace = True

    def run(self) -> list[docutils.nodes.Node]:
        if self.arguments:
            target = self.arguments[0]
        else:
            modname = self.env.ref_context.get("lua:module", "")
            classname = self.env.ref_context.get("lua:class", "")
            target = ".".join(filter(None, [modname, classname]))
        if not target:
            raise self.error("class name is required")
        return [InheritedMethodsNode("", target=utils.normalize_name(target))]


def _get_name(fullname: str) -> str:
    if "[" in fullname:
        return utils.separate_sig(fullname, ".")[-1]
    else:
        return fullname.rsplit(".", maxsplit=1)[-1]


class InheritedMembersTransform(SphinxTransform):
    default_priority = 750

    @property
    def domain(self) -> sphinx_lua_ls.domain.LuaDomain:
        return _t.cast(sphinx_lua_ls.domain.LuaDomain, self.env.get_domain("lua"))

    def apply(self, **kwargs):
        node: InheritedMethodsNode
        for node in list(self.document.findall(InheritedMethodsNode)):
            target: str = node["target"]

            methods: dict[str, tuple[str, str]] = {}

            if data := self.domain.members.get(target, None):
                seen_methods = set(_get_name(e.fullname) for e in data.entries)
                seen_bases = set()

                bases = [(base, data) for base in data.bases]
                while bases:
                    (base, data) = bases.pop()

                    resolved_base = self.domain._find_obj(
                        data.base_lookup_modname or "",
                        data.base_lookup_classname or "",
                        base,
                        None,
                        data.base_lookup_using,
                    )

                    if not resolved_base:
                        continue

                    base_fullname = resolved_base[0]

                    if base_fullname in seen_bases:
                        continue
                    seen_bases.add(base_fullname)

                    base_data = self.domain.members.get(base_fullname, None)
                    if not base_data:
                        continue

                    for entry in base_data.entries:
                        name = _get_name(entry.fullname)

                        if name not in seen_methods and name not in methods:
                            methods[name] = (base_fullname, entry.fullname)

                    bases.extend((base, base_data) for base in base_data.bases)

            methods_per_base: dict[str, dict[str, str]] = defaultdict(dict)
            for name, (basename, fullname) in methods.items():
                methods_per_base[basename][name] = fullname

            node.replace_self(
                docutils.nodes.container(
                    "",
                    *self.render_bases(methods_per_base),
                    classes=["lua-inherited-members"],
                )
            )

    def render_bases(
        self, objects: dict[str, dict[str, str]]
    ) -> list[docutils.nodes.Node]:
        if not objects:
            return []

        nodes: list[docutils.nodes.Node] = []

        nodes.append(
            docutils.nodes.paragraph(
                "", "", docutils.nodes.strong("", "Other members:")
            )
        )
        a = docutils.nodes.admonition()
        nodes.append(a)

        for fullname, members in sorted(objects.items()):
            p = docutils.nodes.paragraph()
            a += p

            p += docutils.nodes.Text("Inherited from ")
            p += self.make_ref(fullname, fullname)
            p += docutils.nodes.Text(": ")

            sep = ""
            for name, fullname in sorted(members.items()):
                if sep:
                    p += docutils.nodes.Text(sep)
                p += self.make_ref(fullname, name)
                sep = ", "

        return nodes

    def make_ref(self, fullname: str, name: str):
        contnode = docutils.nodes.literal("", name)
        return (
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
