# SPDX-License-Identifier: MIT
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup

from .config import Metadata as MetaConfig

_DATE_RE = (
    r"(?:"
    r"\d{1,2}\s+\S+\s+\d{4}\s+\d{2}:\d{2}(?::\d{2})?"
    r"|"
    r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?::\d{2})?(?:\s+[A-Z]{2,5})?"
    r")"
)
_NEXT_META_RE = r"(?=\s+(?:Created|Updated|Revision)\b|$)"
_NAME_RE = r"(?:(?!\s+(?:Created|Updated|Revision)\b).)+?"


@dataclass
class Info:
    title: str = "Untitled"
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    updated_at: Optional[str] = None
    version: Optional[str] = None
    tags: list[dict[str, str]] = field(default_factory=list)
    body_html: str = ""

    @property
    def has_metadata(self) -> bool:
        return any([self.created_by, self.updated_by, self.updated_at, self.version])


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _format_date(raw_date: Optional[str], cfg: MetaConfig) -> Optional[str]:
    if not raw_date:
        return None
    raw_date = _clean_text(raw_date)
    for input_format in [cfg.date_input_format, "%Y-%m-%d %H:%M:%S %Z", "%Y-%m-%d %H:%M:%S"]:
        try:
            dt = datetime.strptime(raw_date, input_format)
            return dt.strftime(cfg.date_output_format)
        except ValueError:
            continue
    return raw_date


def _created_from_text(text: str) -> Optional[str]:
    patterns = [
        rf"\bCreated\s+{_DATE_RE}\s+by\s+(?P<name>{_NAME_RE}){_NEXT_META_RE}",
        rf"\bCreated\s+by\s+(?P<name>{_NAME_RE})\s+(?:on|at)\s+{_DATE_RE}{_NEXT_META_RE}",
        rf"\bCreated\s+by\s+(?P<name>{_NAME_RE})\s+{_DATE_RE}{_NEXT_META_RE}",
        rf"\bCreated\s+by\s+(?P<name>{_NAME_RE}){_NEXT_META_RE}",
    ]
    for pattern in patterns:
        if m := re.search(pattern, text, re.IGNORECASE):
            return m.group("name").strip(" :-")
    return None


def _updated_from_text(text: str, cfg: MetaConfig) -> tuple[Optional[str], Optional[str]]:
    patterns = [
        rf"\bUpdated\s+(?P<date>{_DATE_RE})\s+by\s+(?P<name>{_NAME_RE}){_NEXT_META_RE}",
        rf"\bUpdated\s+by\s+(?P<name>{_NAME_RE})\s+(?:on|at)\s+(?P<date>{_DATE_RE}){_NEXT_META_RE}",
        rf"\bUpdated\s+by\s+(?P<name>{_NAME_RE})\s+(?P<date>{_DATE_RE}){_NEXT_META_RE}",
        rf"\bUpdated\s+by\s+(?P<name>{_NAME_RE}){_NEXT_META_RE}",
    ]
    for pattern in patterns:
        if m := re.search(pattern, text, re.IGNORECASE):
            return m.group("name").strip(" :-"), _format_date(m.groupdict().get("date"), cfg)
    return None, None


def _has_usable_match_remainder(text: str, end: int) -> bool:
    remainder = text[end:].strip()
    return not remainder or re.match(r"^(?:Created|Updated|Revision)\b", remainder, re.IGNORECASE) is not None


def _extract_tags(soup: BeautifulSoup) -> list[dict[str, str]]:
    tags: list[dict[str, str]] = []
    for tag_item in soup.select(".tag-section-page .tag-item"):
        name = _clean_text(tag_item.get("data-name", ""))
        value = _clean_text(tag_item.get("data-value", ""))

        if not name:
            name_el = tag_item.select_one(".tag-name")
            name = _clean_text(name_el.get_text(" ", strip=True)) if name_el else ""
        if not value:
            value_el = tag_item.select_one(".tag-value")
            value = _clean_text(value_el.get_text(" ", strip=True)) if value_el else ""

        if name or value:
            tags.append({"name": name, "value": value})
    return tags


def extract(soup: BeautifulSoup, cfg: MetaConfig, *, unknown: Optional[str] = None) -> Info:
    """Extract metadata from a BookStack-rendered HTML soup.

    If `unknown` is given, fields that aren't found in the document fall back
    to that value (useful when the cover/footer should always show a label,
    e.g. "Versionsdatum: n/a"). If `unknown` is None, fields stay as None and
    callers can decide whether to render them at all.
    """
    info = Info(
        created_by=unknown,
        updated_by=unknown,
        updated_at=unknown,
        version=unknown,
    )

    if soup.title and soup.title.string:
        info.title = soup.title.string.strip()
    elif h1 := soup.find("h1"):
        info.title = h1.get_text(strip=True)

    info.tags = _extract_tags(soup)

    created_re = re.compile(cfg.created_pattern, re.IGNORECASE)
    updated_re = re.compile(cfg.updated_pattern, re.IGNORECASE)
    version_re = re.compile(cfg.version_pattern, re.IGNORECASE)

    found_created = False
    found_updated = False
    found_version = False

    chunks = [_clean_text(chunk) for chunk in soup.stripped_strings]
    # Some BookStack themes/layouts split labels, names, and dates across
    # sibling elements. Include a full-text pass so fallback parsing still sees
    # the surrounding metadata in order.
    chunks.append(_clean_text(" ".join(chunks)))

    for chunk in chunks:
        if not found_created and (m := created_re.search(chunk)) and _has_usable_match_remainder(chunk, m.end()):
            info.created_by = m.group(1).strip()
            found_created = True
        if not found_updated and (m := updated_re.search(chunk)) and _has_usable_match_remainder(chunk, m.end()):
            raw_date = m.group(1)
            info.updated_by = m.group(2).strip()
            info.updated_at = _format_date(raw_date, cfg)
            found_updated = True
        if not found_version and (m := version_re.search(chunk)):
            info.version = m.group(1).strip()
            found_version = True
        if not found_created and (created_by := _created_from_text(chunk)):
            info.created_by = created_by
            found_created = True
        if not found_updated:
            updated_by, updated_at = _updated_from_text(chunk, cfg)
            if updated_by:
                info.updated_by = updated_by
                if updated_at:
                    info.updated_at = updated_at
                found_updated = True

    body = soup.body or soup
    info.body_html = body.decode_contents() if hasattr(body, "decode_contents") else str(body)
    return info
