# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?= -j 12 -n
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = source
BUILDDIR      = build
DOCTREEDIR    = build/doctrees

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" -d "$(DOCTREEDIR)" $(SPHINXOPTS) $(O)

.PHONY: help watch Makefile

watch:
	sphinx-autobuild "$(SOURCEDIR)" "$(BUILDDIR)"/html -d "$(DOCTREEDIR)" --watch ../sphinx_lua_ls $(SPHINXOPTS) $(O)

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" -d "$(DOCTREEDIR)" $(SPHINXOPTS) $(O)
