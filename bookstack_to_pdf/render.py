# SPDX-License-Identifier: MIT
from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import unquote

from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import CSS, HTML, URLFetcher
from weasyprint.text.fonts import FontConfiguration

from . import metadata
from .config import Config

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _build_toc(soup: BeautifulSoup, max_depth: int) -> list[dict]:
    """Walk headings, ensure each has an id, and return a flat list for the TOC."""
    entries = []
    seen_ids: set[str] = set()
    selectors = ", ".join(f"h{i}" for i in range(1, max_depth + 1))
    for heading in soup.select(selectors):
        text = heading.get_text(" ", strip=True)
        if not text:
            continue
        anchor = heading.get("id") or _slugify(text)
        base = anchor
        n = 1
        while anchor in seen_ids:
            n += 1
            anchor = f"{base}-{n}"
        seen_ids.add(anchor)
        heading["id"] = anchor
        level = int(heading.name[1])
        entries.append({"text": text, "anchor": anchor, "level": level})
    return entries


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug or "section"


def _page_of_expr(template: str) -> str:
    """Convert 'Page {page} of {pages}' to a CSS counter expression."""
    parts: list[str] = []

    def push_text(s: str):
        if s:
            parts.append('"' + s.replace('"', '\\"') + '"')

    a, _, rest = template.partition("{page}")
    push_text(a)
    parts.append("counter(page)")
    b, _, c = rest.partition("{pages}")
    push_text(b)
    if "{pages}" in template:
        parts.append("counter(pages)")
        push_text(c)
    return " ".join(parts) if parts else '""'


def _remove_export_only_sections(soup: BeautifulSoup) -> None:
    for tag_section in soup.select(".tag-section-page"):
        tag_section.decompose()


def _remove_empty_spacer_blocks(soup: BeautifulSoup) -> None:
    for el in soup.find_all(["div", "p"]):
        text = el.get_text("", strip=True).replace("\xa0", "")
        if text:
            continue
        if all(getattr(child, "name", None) == "br" for child in el.contents):
            el.decompose()


def _remove_trailing_export_separator(soup: BeautifulSoup) -> None:
    for meta in soup.select(".entity-meta, .activity-list, .audit-log, .page-meta"):
        wrapper = meta.parent
        previous = wrapper.find_previous_sibling() if wrapper else meta.find_previous_sibling()
        if previous and getattr(previous, "name", None) == "hr":
            previous.decompose()


def _normalize_internal_links(soup: BeautifulSoup) -> None:
    ids = {
        tag.get("id")
        for tag in soup.find_all(attrs={"id": True})
        if isinstance(tag.get("id"), str) and tag.get("id")
    }
    decoded_ids = {unquote(value): value for value in ids}

    for link in soup.find_all("a", href=True):
        href = link.get("href")
        if not isinstance(href, str) or not href.startswith("#"):
            continue

        fragment = href[1:]
        if fragment in ids:
            continue

        if target := decoded_ids.get(unquote(fragment)):
            link["href"] = f"#{target}"


def _decode_percent_encoded_ids(soup: BeautifulSoup) -> None:
    used: set[str] = set()

    for tag in soup.find_all(attrs={"id": True}):
        raw_id = tag.get("id")
        if not isinstance(raw_id, str) or not raw_id:
            continue

        decoded_id = unquote(raw_id)
        candidate = decoded_id
        n = 1
        while candidate in used:
            n += 1
            candidate = f"{decoded_id}-{n}"
        used.add(candidate)
        tag["id"] = candidate


def _make_url_fetcher(allow_remote: bool) -> URLFetcher:
    allowed_protocols = None if allow_remote else {"file", "data"}
    return URLFetcher(allowed_protocols=allowed_protocols)


def render(input_html: Path, output_pdf: Path, cfg: Config) -> None:
    raw = input_html.read_text(encoding="utf-8")
    soup = BeautifulSoup(raw, "html.parser")
    info = metadata.extract(soup, cfg.metadata, unknown=cfg.strings.unknown)
    logger.debug("Extracted %d BookStack tag(s)", len(info.tags))

    # Optionally swap the company block based on a configured tag (e.g. "Bereich").
    resolved_company = cfg.company.for_tags(info.tags)
    if resolved_company is not cfg.company:
        logger.info("Company resolved to %r via tag %r", resolved_company.name, cfg.company.by_tag.tag)
        cfg.company = resolved_company

    body_soup = BeautifulSoup(info.body_html, "html.parser")
    _remove_export_only_sections(body_soup)
    _remove_empty_spacer_blocks(body_soup)
    _remove_trailing_export_separator(body_soup)
    _decode_percent_encoded_ids(body_soup)
    _normalize_internal_links(body_soup)
    toc_entries = _build_toc(body_soup, cfg.toc.max_depth) if cfg.toc.enabled else []
    info.body_html = str(body_soup)

    env = Environment(
        loader=FileSystemLoader(_TEMPLATES_DIR),
        autoescape=select_autoescape(["html", "xml"]),
        keep_trailing_newline=True,
    )

    html_template = env.get_template("document.html.j2")
    css_template = env.get_template("styles.css.j2")

    context = {
        "cfg": cfg,
        "info": info,
        "toc_entries": toc_entries,
        "logo_url": cfg.resolve_asset(cfg.branding.logo),
        "cover_background_url": cfg.resolve_asset(cfg.branding.cover_background),
        "page_of_expr": _page_of_expr(cfg.strings.page_of),
        "resolve": cfg.resolve_asset,
    }

    html_str = html_template.render(**context)
    css_str = css_template.render(**context)

    fetcher = _make_url_fetcher(cfg.branding.allow_remote_assets)
    base_url = cfg.base_dir.resolve().as_uri() + "/"
    font_config = FontConfiguration()

    HTML(string=html_str, base_url=base_url, url_fetcher=fetcher).write_pdf(
        target=str(output_pdf),
        stylesheets=[
            CSS(
                string=css_str,
                base_url=base_url,
                url_fetcher=fetcher,
                font_config=font_config,
            )
        ],
        font_config=font_config,
    )
    logger.info("Wrote %s", output_pdf)
