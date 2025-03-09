import sys

from sybil import Sybil
from sybil.parsers.codeblock import PythonCodeBlockParser
from sybil.parsers.doctest import DocTestParser
from sybil.parsers.rest import SkipParser

if sys.version_info >= (3, 10):
    # Examples use the new typing syntax.
    pytest_collect_file = Sybil(
        parsers=[
            DocTestParser(),
            PythonCodeBlockParser(),
            SkipParser(),
        ],
        patterns=["*.rst", "*.py"],
    ).pytest()
