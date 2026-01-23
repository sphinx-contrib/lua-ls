from sphinx import addnodes
from docutils import nodes
from typing import Any


class SigIndentNode(addnodes.desc_sig_space):
    def __init__(
        self,
        rawsource: str = '',
        text: str = '    ',
        *children: nodes.Element,
        **attributes: Any
    ):
        super().__init__(rawsource, text, *children, **attributes)


def visit_sig_indent_latex(self, node):
    self.body.append("~~~~")

def depart_sig_indent_latex(self, node):
    pass
