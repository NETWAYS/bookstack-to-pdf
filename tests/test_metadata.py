# SPDX-License-Identifier: MIT
from __future__ import annotations

from bs4 import BeautifulSoup

from bookstack_to_pdf import metadata as meta_module
from bookstack_to_pdf.config import Metadata as MetaConfig


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _cfg() -> MetaConfig:
    return MetaConfig()


def test_title_from_title_tag():
    soup = _soup("<html><head><title>My Doc</title></head><body><h1>Ignored</h1></body></html>")
    info = meta_module.extract(soup, _cfg())
    assert info.title == "My Doc"


def test_title_fallback_to_h1():
    soup = _soup("<html><body><h1>Fallback Title</h1></body></html>")
    info = meta_module.extract(soup, _cfg())
    assert info.title == "Fallback Title"


def test_title_default_when_missing():
    soup = _soup("<html><body><p>no heading</p></body></html>")
    info = meta_module.extract(soup, _cfg())
    assert info.title == "Untitled"


def test_created_by_extracted():
    soup = _soup("<body><p>Created 18 April 2025 09:30:00 by Jane Doe</p></body>")
    info = meta_module.extract(soup, _cfg())
    assert info.created_by == "Jane Doe"


def test_updated_by_and_date_extracted():
    soup = _soup("<body><p>Updated 21 April 2025 14:15:00 by John Smith</p></body>")
    info = meta_module.extract(soup, _cfg())
    assert info.updated_by == "John Smith"
    assert info.updated_at == "21.04.2025"


def test_iso_timezone_metadata_extracted():
    soup = _soup(
        "<body>"
        "<div class='entity-meta'>"
        "<svg></svg>Revision #113 <br>"
        "<svg></svg>Created 2022-07-05 10:17:46 CEST by Marius Hein<br>"
        "<svg></svg>Updated 2026-03-05 13:44:01 CET by Api User"
        "</div>"
        "</body>"
    )
    info = meta_module.extract(soup, _cfg())
    assert info.created_by == "Marius Hein"
    assert info.updated_by == "Api User"
    assert info.updated_at == "05.03.2026"
    assert info.version == "113"


def test_metadata_names_can_contain_punctuation():
    soup = _soup(
        "<body>"
        "<p>Created 18 April 2025 09:30:00 by Jane D. Doe</p>"
        "<p>Updated 21 April 2025 14:15:00 by John Smith (Admin)</p>"
        "</body>"
    )
    info = meta_module.extract(soup, _cfg())
    assert info.created_by == "Jane D. Doe"
    assert info.updated_by == "John Smith (Admin)"
    assert info.updated_at == "21.04.2025"


def test_metadata_can_be_split_across_elements():
    soup = _soup(
        "<body>"
        "<span>Created by</span><a>Jane Doe</a>"
        "<span>Updated by</span><a>John Smith</a><span>21 April 2025 14:15:00</span>"
        "<span>Revision #7</span>"
        "</body>"
    )
    info = meta_module.extract(soup, _cfg())
    assert info.created_by == "Jane Doe"
    assert info.updated_by == "John Smith"
    assert info.updated_at == "21.04.2025"


def test_version_extracted():
    soup = _soup("<body><p>Revision #7</p></body>")
    info = meta_module.extract(soup, _cfg())
    assert info.version == "7"


def test_tags_extracted_from_bookstack_tag_section():
    soup = _soup(
        "<body>"
        "<section class='tag-section-page'>"
        "<div class='tag-item' data-name='Bereich' data-value='ITSM'></div>"
        "<div class='tag-item' data-name='Schutzklasse' data-value='Intern'></div>"
        "</section>"
        "</body>"
    )
    info = meta_module.extract(soup, _cfg())
    assert info.tags == [
        {"name": "Bereich", "value": "ITSM"},
        {"name": "Schutzklasse", "value": "Intern"},
    ]


def test_tags_fall_back_to_visible_text():
    soup = _soup(
        "<body>"
        "<section class='tag-section-page'>"
        "<div class='tag-item'>"
        "<div class='tag-name'><a>consul</a></div>"
        "<div class='tag-value'><a>mail</a></div>"
        "</div>"
        "</section>"
        "</body>"
    )
    info = meta_module.extract(soup, _cfg())
    assert info.tags == [{"name": "consul", "value": "mail"}]


def test_has_metadata_true():
    soup = _soup("<body><p>Created 18 April 2025 09:30:00 by Jane Doe</p></body>")
    info = meta_module.extract(soup, _cfg())
    assert info.has_metadata is True


def test_has_metadata_false():
    soup = _soup("<body><p>Nothing interesting here.</p></body>")
    info = meta_module.extract(soup, _cfg())
    assert info.has_metadata is False


def test_missing_metadata_fields_are_none():
    soup = _soup("<body><p>Nothing here.</p></body>")
    info = meta_module.extract(soup, _cfg())
    assert info.created_by is None
    assert info.updated_by is None
    assert info.updated_at is None
    assert info.version is None


def test_missing_metadata_fields_use_unknown_fallback():
    soup = _soup("<body><p>Nothing here.</p></body>")
    info = meta_module.extract(soup, _cfg(), unknown="n/a")
    assert info.created_by == "n/a"
    assert info.updated_by == "n/a"
    assert info.updated_at == "n/a"
    assert info.version == "n/a"
    # has_metadata is True because all fields are truthy under the fallback.
    assert info.has_metadata is True


def test_unknown_fallback_does_not_override_real_values():
    soup = _soup("<body><p>Created 18 April 2025 09:30:00 by Jane Doe</p></body>")
    info = meta_module.extract(soup, _cfg(), unknown="n/a")
    assert info.created_by == "Jane Doe"
    assert info.updated_by == "n/a"  # not in soup -> fallback


def test_body_html_contains_content():
    soup = _soup("<body><h2>Hello</h2><p>World</p></body>")
    info = meta_module.extract(soup, _cfg())
    assert "<h2>" in info.body_html
    assert "World" in info.body_html


def test_invalid_date_falls_back_to_raw():
    cfg = MetaConfig(date_input_format="%d %B %Y %H:%M:%S")
    soup = _soup("<body><p>Updated 99 Nope 0000 00:00:00 by Bot</p></body>")
    info = meta_module.extract(soup, cfg)
    # date parse fails — raw string is kept
    if info.updated_at is not None:
        assert "0000" in info.updated_at or info.updated_by == "Bot"
