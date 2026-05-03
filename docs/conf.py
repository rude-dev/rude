"""Sphinx configuration for Rude documentation."""

import warnings
from datetime import date
import importlib.metadata

# Suppress sphinx-autodoc-typehints deprecation warning (fixed in 3.6.2, but requires Python>=3.12)
# See: https://github.com/tox-dev/sphinx-autodoc-typehints/issues/588
warnings.filterwarnings("ignore", message=r".*set_application.*is deprecated.*")

# -- Project information ---------------------------------------------------

project = "Rude"
author = "Geoffrey Guéret"
copyright = f"{date.today().year}, {author}"
release = importlib.metadata.version("rude")
version = ".".join(release.split(".")[:2])

# -- General configuration -------------------------------------------------

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
    "sphinx_autodoc_typehints",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

exclude_patterns = ["_build", "plans", "superpowers"]

nitpicky = True
nitpick_ignore_regex = [
    (r"py:class", r"tree_sitter\..*"),
    (r"py:class", r"TS(Tree|Node|Cursor)"),
    (r"py:class", r"rude\.core\.rule\.(Rule|_Rule)Base"),
    (r"py:class", r"rude\.core\.node\._NodeTypeMixin"),
    (r"py:class", r"LineInfo"),
    (r"py:class", r"NodeEntry"),
    (r"py:class", r"rude\.rules\.pyflakes\.literals\._PrefixStringMissingPlaceholders"),
    (r"py:class", r"Simple function name"),
    (r"py:class", r"Full dotted name"),
    (r"py:class", r"SemanticModel"),
    (r"py:meth", r"SemanticModel\..*"),
]

# Suppress ambiguous 'type' reference warning (Scope.type vs Token.type)
suppress_warnings = ["ref.python"]

# -- MyST configuration ---------------------------------------------------

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
]

# -- Autodoc configuration ------------------------------------------------

autodoc_member_order = "bysource"
autodoc_typehints = "description"
autodoc_class_signature = "separated"
always_document_param_types = True

import os
import sys
sys.path.insert(0, os.path.abspath("../python"))

# -- Napoleon configuration ------------------------------------------------

napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_attr_annotations = True

# -- Intersphinx configuration ---------------------------------------------

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# -- HTML output -----------------------------------------------------------

html_theme = "furo"
html_title = f"Rude <small>{version}</small>"
html_logo = "_static/logo-mask.svg"
templates_path = ["_templates"]

html_theme_options = {
    "source_repository": "https://github.com/rude-dev/rude",
    "source_branch": "main",
    "source_directory": "docs/",
    "top_of_page_buttons": [],
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/rude-dev/rude",
            "html": '<svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 16 16"><path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path></svg>',
            "class": "",
        },
        {
            "name": "PyPI",
            "url": "https://pypi.org/project/rude/",
            "html": '<svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 17 20"><path d="M12.5 0l-4 2.1v11.4l4-2V0zM8.5 4.3l-4 2v11.4l4-2V4.3zM16.5 2.1l-4 2.1v11.4l4-2V2.1zM4.5 6.4l-4 2v11.4l4-2V6.4z"></path></svg>',
            "class": "",
        },
    ],
}

html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_js_files = ["tagline.js"]
