# SPDX-License-Identifier: MIT
from __future__ import annotations

from pathlib import Path

from bookstack_to_pdf.__main__ import _dump_input


def test_dump_input_copies_raw_html(tmp_path: Path):
    source = tmp_path / "input.html"
    target = tmp_path / "debug" / "input.html"
    source.write_text("<html><body>raw export</body></html>", encoding="utf-8")

    _dump_input(source, target)

    assert target.read_text(encoding="utf-8") == "<html><body>raw export</body></html>"
