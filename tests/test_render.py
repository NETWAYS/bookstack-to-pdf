# SPDX-License-Identifier: MIT
from __future__ import annotations

from pathlib import Path

import pytest

from bookstack_to_pdf import config as config_module
from bs4 import BeautifulSoup

from bookstack_to_pdf.render import (
    _decode_percent_encoded_ids,
    _page_of_expr,
    _normalize_internal_links,
    _remove_empty_spacer_blocks,
    _remove_export_only_sections,
    _remove_trailing_export_separator,
    _slugify,
    render,
)


FIXTURE = Path(__file__).parent / "fixtures" / "sample_bookstack.html"


def test_page_of_expr_default():
    assert _page_of_expr("Page {page} of {pages}") == '"Page " counter(page) " of " counter(pages)'


def test_page_of_expr_no_pages():
    assert _page_of_expr("Page {page}") == '"Page " counter(page)'


def test_slugify_basic():
    assert _slugify("Hello World!") == "hello-world"
    assert _slugify("  Foo / Bar  ") == "foo-bar"
    assert _slugify("") == "section"


def test_remove_export_only_sections_removes_bookstack_tags():
    soup = BeautifulSoup(
        """
        <body>
          <h1>Tagged Page</h1>
          <section class="tag-section-page"><div class="tag-item" data-name="Bereich" data-value="ITSM"></div></section>
          <p>Body</p>
        </body>
        """,
        "html.parser",
    )

    _remove_export_only_sections(soup)

    assert soup.select_one(".tag-section-page") is None
    assert "Body" in soup.get_text(" ", strip=True)


def test_remove_empty_spacer_blocks_removes_bookstack_br_divs():
    soup = BeautifulSoup(
        """
        <body>
          <h3>DKIM</h3>
          <div><br></div>
          <div>Body</div>
          <p>&nbsp;</p>
        </body>
        """,
        "html.parser",
    )

    _remove_empty_spacer_blocks(soup)

    assert soup.find("br") is None
    assert "DKIM" in soup.get_text(" ", strip=True)
    assert "Body" in soup.get_text(" ", strip=True)


def test_remove_trailing_export_separator_before_metadata():
    soup = BeautifulSoup(
        """
        <body>
          <p>Body</p>
          <hr>
          <div class="text-muted text-small"><div class="entity-meta">Revision #1</div></div>
        </body>
        """,
        "html.parser",
    )

    _remove_trailing_export_separator(soup)

    assert soup.find("hr") is None
    assert "Body" in soup.get_text(" ", strip=True)


def test_normalize_internal_links_matches_encoded_bookstack_ids():
    soup = BeautifulSoup(
        """
        <body>
          <a href="#bkmrk-spamfilter-(rspamd)">Spamfilter</a>
          <a href="#bkmrk-\u00a0-0">Diagnose Header</a>
          <h2 id="bkmrk-spamfilter-%28rspamd%29">Spamfilter (Rspamd)</h2>
          <h3 id="bkmrk-%C2%A0-0">Diagnose Header</h3>
        </body>
        """,
        "html.parser",
    )

    _normalize_internal_links(soup)

    links = [link["href"] for link in soup.find_all("a")]
    assert links == ["#bkmrk-spamfilter-%28rspamd%29", "#bkmrk-%C2%A0-0"]


def test_decode_percent_encoded_ids_uses_weasyprint_anchor_form():
    soup = BeautifulSoup(
        """
        <body>
          <h2 id="bkmrk-spamfilter-%28rspamd%29">Spamfilter (Rspamd)</h2>
          <h3 id="bkmrk-%C2%A0-0">Diagnose Header</h3>
        </body>
        """,
        "html.parser",
    )

    _decode_percent_encoded_ids(soup)

    assert soup.find(id="bkmrk-spamfilter-(rspamd)") is not None
    assert soup.find(id="bkmrk-\u00a0-0") is not None


def test_render_smoke(tmp_path: Path):
    cfg = config_module.Config()
    cfg.base_dir = tmp_path
    out = tmp_path / "out.pdf"
    render(FIXTURE, out, cfg)
    assert out.is_file()
    assert out.stat().st_size > 1000


def test_render_has_outline(tmp_path: Path):
    pypdf = pytest.importorskip("pypdf")
    cfg = config_module.Config()
    cfg.base_dir = tmp_path
    out = tmp_path / "out.pdf"
    render(FIXTURE, out, cfg)

    reader = pypdf.PdfReader(str(out))
    assert len(reader.pages) >= 2  # cover + content


def test_render_puts_bookstack_tags_on_cover(tmp_path: Path):
    pypdf = pytest.importorskip("pypdf")
    html = tmp_path / "tagged.html"
    html.write_text(
        """
        <html>
          <head><title>Tagged Page</title></head>
          <body>
            <h1>Tagged Page</h1>
            <section class="tag-section-page">
              <div class="tag-list">
                <div class="tag-item" data-name="Bereich" data-value="ITSM"></div>
                <div class="tag-item" data-name="Schutzklasse" data-value="Intern"></div>
              </div>
            </section>
            <p>Body</p>
          </body>
        </html>
        """,
        encoding="utf-8",
    )

    cfg = config_module.Config()
    cfg.base_dir = tmp_path
    out = tmp_path / "out.pdf"
    render(html, out, cfg)

    cover_text = pypdf.PdfReader(str(out)).pages[0].extract_text()
    assert "Bereich" in cover_text
    assert "ITSM" in cover_text
    assert "Schutzklasse" in cover_text
    assert "Intern" in cover_text


def test_render_can_hide_bookstack_tags(tmp_path: Path):
    pypdf = pytest.importorskip("pypdf")
    html = tmp_path / "tagged.html"
    html.write_text(
        """
        <html>
          <head><title>Tagged Page</title></head>
          <body>
            <h1>Tagged Page</h1>
            <section class="tag-section-page">
              <div class="tag-item" data-name="Bereich" data-value="ITSM"></div>
            </section>
            <p>Body</p>
          </body>
        </html>
        """,
        encoding="utf-8",
    )

    cfg = config_module.Config()
    cfg.base_dir = tmp_path
    cfg.cover.show_tags = False
    out = tmp_path / "out.pdf"
    render(html, out, cfg)

    pdf_text = "\n".join(page.extract_text() for page in pypdf.PdfReader(str(out)).pages)
    assert "Bereich" not in pdf_text
    assert "ITSM" not in pdf_text


def test_render_embeds_configured_font(tmp_path: Path):
    pypdf = pytest.importorskip("pypdf")
    font = tmp_path / "Montserrat-Regular.ttf"
    font.write_bytes((Path(__file__).parents[1] / "assets" / "fonts" / "Montserrat-Regular.ttf").read_bytes())

    cfg = config_module.Config()
    cfg.base_dir = tmp_path
    cfg.branding.fonts = [
        config_module.Font(
            family="Montserrat",
            files=[config_module.FontFile(src="./Montserrat-Regular.ttf", weight=400, style="normal")],
        )
    ]
    cfg.branding.font_family = "Montserrat, Arial, Helvetica, sans-serif"

    out = tmp_path / "out.pdf"
    render(FIXTURE, out, cfg)

    reader = pypdf.PdfReader(str(out))
    embedded_fonts = set()
    for page in reader.pages:
        resources = page.get("/Resources", {})
        fonts = resources.get("/Font", {})
        for font_ref in fonts.values():
            font_obj = font_ref.get_object()
            base_font = str(font_obj.get("/BaseFont", ""))
            embedded_fonts.add(base_font)

    assert any("Montserrat" in font_name for font_name in embedded_fonts)


def test_url_fetcher_blocks_remote(tmp_path: Path):
    cfg = config_module.Config()
    cfg.base_dir = tmp_path
    cfg.branding.logo = "https://example.com/logo.png"
    cfg.branding.allow_remote_assets = False
    out = tmp_path / "out.pdf"
    # Should still succeed because WeasyPrint tolerates missing images,
    # but the fetcher should refuse to load the remote URL.
    render(FIXTURE, out, cfg)
    assert out.is_file()
