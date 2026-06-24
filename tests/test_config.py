# SPDX-License-Identifier: MIT
from __future__ import annotations

import os
from pathlib import Path

import pytest

from bookstack_to_pdf import config as config_module
from bookstack_to_pdf.config import Company, Config


def test_default_config_loads_without_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)  # ensure no ./config.yaml is found
    cfg = config_module.load(path=None)
    assert isinstance(cfg, Config)
    assert cfg.company.name == "Your Company"


def test_load_from_explicit_path(tmp_path: Path):
    yaml = tmp_path / "config.yaml"
    yaml.write_text("company:\n  name: Test Corp\n", encoding="utf-8")
    cfg = config_module.load(path=str(yaml))
    assert cfg.company.name == "Test Corp"


def test_load_sets_base_dir(tmp_path: Path):
    yaml = tmp_path / "config.yaml"
    yaml.write_text("company:\n  name: X\n", encoding="utf-8")
    cfg = config_module.load(path=str(yaml))
    assert cfg.base_dir == tmp_path


def test_load_from_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    yaml = tmp_path / "config.yaml"
    yaml.write_text("company:\n  name: Env Corp\n", encoding="utf-8")
    monkeypatch.setenv("BOOKSTACK_TO_PDF_CONFIG", str(yaml))
    cfg = config_module.load(path=None)
    assert cfg.company.name == "Env Corp"


def test_resolve_asset_none_returns_none():
    cfg = Config()
    assert cfg.resolve_asset(None) is None


def test_resolve_asset_empty_returns_none():
    cfg = Config()
    assert cfg.resolve_asset("") is None


def test_resolve_asset_http_passthrough():
    cfg = Config()
    url = "https://example.com/logo.png"
    assert cfg.resolve_asset(url) == url


def test_resolve_asset_relative_path(tmp_path: Path):
    cfg = Config()
    cfg.base_dir = tmp_path
    asset = tmp_path / "assets" / "logo.png"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"")
    result = cfg.resolve_asset("assets/logo.png")
    assert result == asset.resolve().as_uri()


def test_resolve_asset_absolute_path(tmp_path: Path):
    cfg = Config()
    asset = tmp_path / "logo.png"
    asset.write_bytes(b"")
    result = cfg.resolve_asset(str(asset))
    assert result.startswith("file://")
    assert "logo.png" in result


def test_resolve_asset_missing_returns_none(tmp_path: Path):
    cfg = Config()
    cfg.base_dir = tmp_path
    assert cfg.resolve_asset("assets/missing.png") is None


def test_partial_config_uses_defaults(tmp_path: Path):
    yaml = tmp_path / "config.yaml"
    yaml.write_text("company:\n  name: Partial\n", encoding="utf-8")
    cfg = config_module.load(path=str(yaml))
    assert cfg.page.size == "A4"
    assert cfg.toc.enabled is True
    assert cfg.branding.allow_remote_assets is False


def test_font_weight_accepts_variable_range(tmp_path: Path):
    yaml = tmp_path / "config.yaml"
    yaml.write_text(
        """
branding:
  fonts:
    - family: Montserrat
      files:
        - { src: "./assets/fonts/Montserrat.ttf", weight: "100 900", style: "normal" }
""",
        encoding="utf-8",
    )
    cfg = config_module.load(path=str(yaml))
    assert cfg.branding.fonts[0].files[0].weight == "100 900"
    assert cfg.branding.fonts[0].files[0].css_weights == [100, 200, 300, 400, 500, 600, 700, 800, 900]


def test_company_for_tags_noop_without_by_tag():
    company = Company(name="NETWAYS GmbH")
    assert company.for_tags([{"name": "Bereich", "value": "Professional Services"}]) is company


def test_company_for_tags_overrides_on_match():
    company = Company(
        name="NETWAYS GmbH",
        email="info@netways.de",
        by_tag={
            "tag": "Bereich",
            "map": {
                "Professional Services": {
                    "name": "NETWAYS Professional Services GmbH",
                    "email": "ps@netways.de",
                }
            },
        },
    )
    resolved = company.for_tags([{"name": "Bereich", "value": "Professional Services"}])
    assert resolved.name == "NETWAYS Professional Services GmbH"
    assert resolved.email == "ps@netways.de"


def test_company_for_tags_inherits_unset_fields():
    company = Company(
        name="NETWAYS GmbH",
        email="info@netways.de",
        phone="+49 911 0000000",
        by_tag={"tag": "Bereich", "map": {"Web Services": {"name": "NETWAYS Web Services GmbH"}}},
    )
    resolved = company.for_tags([{"name": "Bereich", "value": "Web Services"}])
    assert resolved.name == "NETWAYS Web Services GmbH"
    assert resolved.email == "info@netways.de"  # inherited from base
    assert resolved.phone == "+49 911 0000000"


def test_company_for_tags_case_insensitive_by_default():
    company = Company(
        name="NETWAYS GmbH",
        by_tag={"tag": "bereich", "map": {"professional services": {"name": "PS GmbH"}}},
    )
    resolved = company.for_tags([{"name": "Bereich", "value": "Professional Services"}])
    assert resolved.name == "PS GmbH"


def test_company_for_tags_case_sensitive_no_match():
    company = Company(
        name="NETWAYS GmbH",
        by_tag={
            "tag": "Bereich",
            "case_sensitive": True,
            "map": {"Professional Services": {"name": "PS GmbH"}},
        },
    )
    resolved = company.for_tags([{"name": "Bereich", "value": "professional services"}])
    assert resolved.name == "NETWAYS GmbH"  # value casing differs, no match


def test_company_for_tags_no_matching_tag_returns_self():
    company = Company(
        name="NETWAYS GmbH",
        by_tag={"tag": "Bereich", "map": {"Professional Services": {"name": "PS GmbH"}}},
    )
    resolved = company.for_tags([{"name": "Region", "value": "Nürnberg"}])
    assert resolved.name == "NETWAYS GmbH"


def test_font_weight_accepts_variable_alias(tmp_path: Path):
    yaml = tmp_path / "config.yaml"
    yaml.write_text(
        """
branding:
  fonts:
    - family: Montserrat
      files:
        - { src: "./assets/fonts/Montserrat.ttf", weight: "variable", style: "normal" }
""",
        encoding="utf-8",
    )
    cfg = config_module.load(path=str(yaml))
    assert cfg.branding.fonts[0].files[0].css_weights == [100, 200, 300, 400, 500, 600, 700, 800, 900]
