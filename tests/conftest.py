# SPDX-License-Identifier: Apache-2.0
# Skip render tests when WeasyPrint system libraries (pango/gobject) are not installed.
collect_ignore = []

try:
    import weasyprint  # noqa: F401
except OSError:
    collect_ignore.append("tests/test_render.py")
