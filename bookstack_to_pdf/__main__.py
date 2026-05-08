# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

from . import config as config_module
from .render import render


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="bookstack-to-pdf",
        description="Render a BookStack-exported HTML file into a branded PDF using WeasyPrint.",
    )
    p.add_argument("input_html", type=Path, help="Path to the input HTML (provided by BookStack)")
    p.add_argument("output_pdf", type=Path, help="Path where the rendered PDF should be written")
    p.add_argument("--config", "-c", help="Path to config.yaml (overrides discovery)")
    p.add_argument(
        "--dump-input",
        type=Path,
        help="Copy the raw BookStack HTML input to this path before rendering, for diagnostics.",
    )
    p.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    return p.parse_args(argv)


def _dump_input(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    logging.getLogger(__name__).info("Copied raw input HTML to %s", target)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if args.verbose:
        logging.getLogger("PIL").setLevel(logging.INFO)
        logging.getLogger("fontTools").setLevel(logging.INFO)

    if not args.input_html.is_file():
        print(f"Input HTML not found: {args.input_html}", file=sys.stderr)
        return 2

    cfg = config_module.load(args.config)

    try:
        if args.dump_input:
            _dump_input(args.input_html, args.dump_input)
        render(args.input_html, args.output_pdf, cfg)
    except Exception as exc:
        logging.getLogger(__name__).exception("PDF rendering failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
