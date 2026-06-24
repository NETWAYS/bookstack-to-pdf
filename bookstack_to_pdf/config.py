# SPDX-License-Identifier: MIT
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class CompanyOverride(BaseModel):
    """Company fields that may be swapped in for a matching tag value.

    Every field is optional; whatever is left unset inherits from the base
    `company` block, so a mapping can override just the name or the full set."""

    name: Optional[str] = None
    address_lines: Optional[list[str]] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None


class CompanyByTag(BaseModel):
    """Optional: choose company details from a BookStack tag.

    When a document carries a tag whose name equals `tag` and whose value is a
    key in `map`, the matching `CompanyOverride` is applied on top of the base
    company. Disabled by default — leaving `company.by_tag` unset (or `tag`
    empty) keeps the static company block."""

    tag: str = ""
    case_sensitive: bool = False
    map: dict[str, CompanyOverride] = Field(default_factory=dict)


class Company(BaseModel):
    name: str = "Your Company"
    address_lines: list[str] = Field(default_factory=list)
    email: str = ""
    phone: str = ""
    website: str = ""
    by_tag: Optional[CompanyByTag] = None

    def for_tags(self, tags: list[dict[str, str]]) -> "Company":
        """Return the effective company for a document's tags.

        Applies the first matching `by_tag` override; returns self unchanged
        when the feature is unconfigured or no tag matches. Safe to call
        unconditionally."""
        rule = self.by_tag
        if not rule or not rule.tag.strip() or not rule.map:
            return self

        def norm(value: str) -> str:
            value = value.strip()
            return value if rule.case_sensitive else value.casefold()

        wanted_name = norm(rule.tag)
        value_to_override = {norm(key): override for key, override in rule.map.items()}

        for tag in tags:
            if norm(tag.get("name") or "") != wanted_name:
                continue
            override = value_to_override.get(norm(tag.get("value") or ""))
            if override is None:
                continue
            data = self.model_dump()
            data.update(override.model_dump(exclude_none=True))
            return Company(**data)
        return self


class FontFile(BaseModel):
    src: str
    weight: int | str = 400
    style: str = "normal"

    @property
    def css_weights(self) -> list[int | str]:
        if isinstance(self.weight, int):
            return [self.weight]

        if self.weight.lower() == "variable":
            return list(range(100, 1000, 100))

        parts = self.weight.split()
        if len(parts) == 2 and all(part.isdigit() for part in parts):
            start, end = sorted(int(part) for part in parts)
            first = ((start + 99) // 100) * 100
            last = (end // 100) * 100
            if first <= last:
                return list(range(first, last + 1, 100))

        return [self.weight]


class Font(BaseModel):
    family: str
    files: list[FontFile] = Field(default_factory=list)


class Branding(BaseModel):
    logo: Optional[str] = None
    logo_height_mm: float = 12
    cover_logo_height_mm: float = 20
    primary_color: str = "#1a3a5c"
    text_color: str = "rgb(68,68,68)"
    border_color: str = "#cccccc"
    # Optional full-bleed background image for the cover page (SVG or PNG).
    # Stretched to fill the A4 page exactly.
    cover_background: Optional[str] = None
    allow_remote_assets: bool = False
    fonts: list[Font] = Field(default_factory=list)
    font_family: str = "Arial, Helvetica, sans-serif"
    body_font_size: str = "11pt"
    footer_font_size: str = "8pt"
    cover_title_font_size: str = "28pt"
    cover_metadata_font_size: str = "10pt"
    cover_tag_font_size: str = "7.2pt"
    toc_font_size: str = "10.5pt"
    code_font_size: str = "9.5pt"


class Page(BaseModel):
    size: str = "A4"
    margin_top_mm: float = 30
    margin_bottom_mm: float = 30
    margin_left_mm: float = 25
    margin_right_mm: float = 20


class Cover(BaseModel):
    enabled: bool = True
    show_metadata: bool = True
    show_tags: bool = True


class Toc(BaseModel):
    enabled: bool = True
    max_depth: int = 3


class Strings(BaseModel):
    toc_title: str = "Table of Contents"
    page_of: str = "Page {page} of {pages}"
    created_by: str = "Created by"
    updated_by: str = "Updated by"
    updated_at: str = "Updated"
    version: str = "Version"
    subject: str = "Subject"
    unknown: str = "n/a"
    # Footer contact labels.
    web_label: str = "Web"
    email_label: str = "E-Mail"
    phone_label: str = "Tel"


class Metadata(BaseModel):
    created_pattern: str = r"Created \d{1,2} [A-Za-z]+ \d{4} \d{2}:\d{2}:\d{2} by ([\w\- ]+)"
    updated_pattern: str = r"Updated (\d{1,2} [A-Za-z]+ \d{4} \d{2}:\d{2}:\d{2}) by ([\w\- ]+)"
    version_pattern: str = r"Revision #(\d+)"
    date_input_format: str = "%d %B %Y %H:%M:%S"
    date_output_format: str = "%d.%m.%Y"


class Config(BaseModel):
    company: Company = Field(default_factory=Company)
    branding: Branding = Field(default_factory=Branding)
    page: Page = Field(default_factory=Page)
    cover: Cover = Field(default_factory=Cover)
    toc: Toc = Field(default_factory=Toc)
    strings: Strings = Field(default_factory=Strings)
    metadata: Metadata = Field(default_factory=Metadata)

    base_dir: Path = Field(default_factory=Path.cwd, exclude=True)

    def resolve_asset(self, value: Optional[str]) -> Optional[str]:
        """Turn a config-relative path into an absolute file:// URL.

        Leaves http(s) URLs untouched (the url_fetcher gates them at render time).
        Returns None for local paths that don't exist so the template can skip
        them. A missing layer in a comma-list background-image otherwise causes
        WeasyPrint to drop neighbouring layers as well."""
        if not value:
            return None
        if value.startswith(("http://", "https://", "file://", "data:")):
            return value
        path = Path(value)
        if not path.is_absolute():
            path = (self.base_dir / path).resolve()
        if not path.exists():
            return None
        return path.as_uri()


_CANDIDATE_PATHS = [
    "./config.yaml",
    "~/.config/bookstack-to-pdf/config.yaml",
    "/etc/bookstack-to-pdf/config.yaml",
]


def _find_config(explicit: Optional[str]) -> Optional[Path]:
    if explicit:
        return Path(explicit).expanduser().resolve()
    if env := os.environ.get("BOOKSTACK_TO_PDF_CONFIG"):
        return Path(env).expanduser().resolve()
    for candidate in _CANDIDATE_PATHS:
        p = Path(candidate).expanduser()
        if p.is_file():
            return p.resolve()
    return None


def load(path: Optional[str] = None) -> Config:
    """Load config from disk, falling back to defaults if no file is found."""
    resolved = _find_config(path)
    if resolved is None:
        return Config()
    with resolved.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    cfg = Config.model_validate(data)
    cfg.base_dir = resolved.parent
    return cfg
