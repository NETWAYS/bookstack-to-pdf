# BookStack To PDF

`bookstack-to-pdf` is a configurable PDF export command for [BookStack](https://www.bookstackapp.com/). BookStack hands it exported HTML; the command applies your branding, cover page, table of contents, running header/footer, metadata, local assets, and custom fonts, then renders the final PDF with [WeasyPrint](https://weasyprint.org/).

The goal is to keep BookStack as the place where documentation is written, while moving PDF-specific layout concerns into a small, versioned renderer. BookStack exposes page content, tags, and metadata once; `bookstack-to-pdf` decides how those pieces become a cover, table of contents, headers, footers, and branded pages.

This is intentionally not a full replacement for BookStack's HTML/CSS export system. It works best when the exported HTML is reasonably semantic and when PDF-only behavior is handled here instead of being scattered across BookStack custom CSS. Very complex browser layouts, interactive elements, remote assets, and heavily customized BookStack themes may need small export-template or CSS adjustments before WeasyPrint can render them cleanly.

## Production Install

Install the renderer on the host that runs BookStack:

```bash
sudo apt install libpango-1.0-0 libpangoft2-1.0-0

# Clone or copy this project to /opt/bookstack-to-pdf first.
cd /opt/bookstack-to-pdf
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install .

cp config.example.yaml config.yaml
$EDITOR config.yaml
```

Add the command to BookStack's `.env` file. Use absolute paths:

```env
EXPORT_PDF_COMMAND="/opt/bookstack-to-pdf/.venv/bin/bookstack-to-pdf --config /opt/bookstack-to-pdf/config.yaml {input_html_path} {output_pdf_path}"
EXPORT_PDF_COMMAND_TIMEOUT=60
```

Make the install readable by the BookStack process user, commonly `www-data`:

```bash
chmod o+x /opt/bookstack-to-pdf
chmod +x /opt/bookstack-to-pdf/.venv/bin/bookstack-to-pdf
chmod -R o+rX /opt/bookstack-to-pdf/.venv
chmod o+rX /opt/bookstack-to-pdf/assets
chmod -R o+rX /opt/bookstack-to-pdf/assets
```

Restart BookStack after changing `.env`.

## Deployment Checklist

- Use absolute paths in `EXPORT_PDF_COMMAND`.
- Keep `branding.allow_remote_assets: false` unless exported BookStack content is allowed to fetch remote images and fonts.
- Confirm the BookStack process user can traverse `/opt/bookstack-to-pdf` and read `.venv`, `assets`, and `config.yaml`.
- Run the smoke test below with the same config file BookStack will use.
- Keep generated files such as `build/`, `*.egg-info`, `__pycache__/`, `.pytest_cache/`, `.DS_Store`, and test PDFs out of the deployed source tree.

## Requirements

| Requirement | Notes |
| --- | --- |
| Python 3.10 or newer | Used by the `bookstack-to-pdf` command. |
| WeasyPrint 68.1 or newer | Installed from `pyproject.toml`; the renderer uses the current `URLFetcher` API. |
| WeasyPrint system libraries | On Debian/Ubuntu, install `libpango-1.0-0` and `libpangoft2-1.0-0`. On Fedora/RHEL, install `pango`. |
| BookStack external PDF command support | Configure BookStack with `EXPORT_PDF_COMMAND`. |

## Configuration

Copy `config.example.yaml` to `config.yaml` and edit it for your organization.

Config discovery order:

1. `--config /path/to/config.yaml`
2. `BOOKSTACK_TO_PDF_CONFIG`
3. `./config.yaml`
4. `~/.config/bookstack-to-pdf/config.yaml`
5. `/etc/bookstack-to-pdf/config.yaml`

For BookStack, prefer `--config` with an absolute path because BookStack does not run the export command from this project directory.

### Company Details

```yaml
company:
  name: "Your Company GmbH"
  address_lines:
    - "Your Street 1"
    - "12345 Your City"
  email: "info@example.com"
  phone: "+49 000 0000000"
  website: "https://example.com"
```

These values appear on the cover and in the running footer.

### Branding And Assets

```yaml
branding:
  logo: "./assets/demo-logo.png"
  logo_height_mm: 12
  cover_logo_height_mm: 12
  primary_color: "#1a3a5c"
  text_color: "rgb(68,68,68)"
  border_color: "#cccccc"
  cover_background: null
  allow_remote_assets: false
```

Relative asset paths are resolved from the directory that contains the config file. The example config uses the committed demo logo at `assets/demo-logo.png`; put your own local assets in `assets/` and update `config.yaml` after copying the example. Missing local assets are skipped, so a missing optional cover background does not break rendering.

Remote asset fetching is disabled by default. Keep `allow_remote_assets: false` for server deployments unless you explicitly trust external image and font URLs in exported BookStack content.

Font sizes are configurable as CSS lengths:

```yaml
branding:
  body_font_size: "9pt"
  footer_font_size: "8pt"
  cover_title_font_size: "28pt"
  cover_metadata_font_size: "10pt"
  cover_tag_font_size: "7.2pt"
  toc_font_size: "10.5pt"
  code_font_size: "9.5pt"
```

Use `pt` for predictable print sizing. Smaller footer and tag sizes usually work best because those areas have limited horizontal space.

### Custom Fonts

The example config uses system fonts by default so the repository does not need to commit local font files:

```yaml
branding:
  fonts: []
  font_family: "Arial, Helvetica, sans-serif"
```

To use a custom font, put the files in `assets/fonts/` and reference them from your copied `config.yaml`:

```text
assets/fonts/
  Montserrat-Regular.ttf
  Montserrat-Bold.ttf
  Montserrat-Italic-Regular.ttf
```

You do not need every file from a font family. You only need the files for the styles the PDF uses. For the default templates that means:

- regular body text: weight `400`, style `normal`
- bold headings/labels: weight `700`, style `normal`
- italic content if your BookStack pages use it: weight `400`, style `italic`

For example:

```yaml
branding:
  fonts:
    - family: "Montserrat"
      files:
        - { src: "./assets/fonts/Montserrat-Regular.ttf",        weight: 400, style: "normal" }
        - { src: "./assets/fonts/Montserrat-Bold.ttf",           weight: 700, style: "normal" }
        - { src: "./assets/fonts/Montserrat-Italic-Regular.ttf", weight: 400, style: "italic" }
  font_family: "Montserrat, Arial, Helvetica, sans-serif"
```

To use another font, put its files in `assets/fonts`, add one `files` entry for each style you need, then change `family` and `font_family` to your font's name. Example:

```yaml
branding:
  fonts:
    - family: "Your Font Name"
      files:
        - { src: "./assets/fonts/YourFont-Regular.ttf", weight: 400, style: "normal" }
        - { src: "./assets/fonts/YourFont-Bold.ttf",    weight: 700, style: "normal" }
        - { src: "./assets/fonts/YourFont-Italic.ttf",  weight: 400, style: "italic" }
  font_family: "Your Font Name, Arial, Helvetica, sans-serif"
```

The `family` value and the first name in `font_family` must match. If they do not, WeasyPrint will fall back to Arial.

### Cover, Table Of Contents, And Metadata

```yaml
cover:
  enabled: true
  show_metadata: true
  show_tags: true

toc:
  enabled: true
  max_depth: 3
```

`show_tags` controls whether BookStack page tags appear on the cover. The renderer extracts tags from BookStack's `.tag-section-page` markup, renders them as compact cover chips, then removes that tag section from the body so the tags do not repeat in the document content.

The renderer builds a table of contents from headings in the exported HTML and adds stable anchors when BookStack has not provided them.

### BookStack Page Export Template

For the most robust setup, expose BookStack page tags once in the exported HTML and let `bookstack-to-pdf` decide where they appear in the PDF. Put this in a BookStack theme override for the page export template, mirroring `resources/views/exports/page.blade.php` from BookStack:

```blade
@extends('layouts.export')

@section('title', $page->name)

@section('content')
    @include('pages.parts.page-display')

    @if($page->tags->count() > 0)
        <section class="tag-section-page">
            <div class="tag-list">
                @foreach($page->tags as $tag)
                    <div class="tag-item primary-background-light" data-name="{{ $tag->name }}" data-value="{{ $tag->value }}">
                        <div class="tag-name">{{ $tag->name }}</div>
                        @if($tag->value)
                            <div class="tag-value">{{ $tag->value }}</div>
                        @endif
                    </div>
                @endforeach
            </div>
        </section>
    @endif

    <hr>

    <div class="text-muted text-small">
        @include('exports.parts.meta', ['entity' => $page])
    </div>
@endsection
```

After applying your BookStack theme override, export a page as HTML and confirm it contains BookStack's tag markup:

```bash
grep -n '<section class="tag-section-page"' exported-page.html
```

If no `.tag-section-page` block is present in the HTML, the PDF command cannot print tags. Lines such as `.tag-item[data-name="Area"]` only prove that tag CSS exists; they do not contain tag values.

### BookStack Book Export Template

For book exports, page-level tags can get noisy because every page in the book may have different tags. A good default is to keep `page-item.blade.php` focused on the page title and body, without rendering the per-page tag list:

```blade
<div class="page-break"></div>

<h1 id="page-{{$page->id}}">{{ $page->name }}</h1>
{!! $page->html !!}
```

Put this in a BookStack theme override for the book page item template, mirroring `resources/views/exports/parts/page-item.blade.php` from BookStack. If your readers truly need page tags inside book exports, add them there deliberately, but do not expect those per-page tags to be good cover metadata for the whole book.

Metadata extraction is regex-based because BookStack renders localized text into the export HTML:

```yaml
metadata:
  created_pattern: 'Created \d{1,2} [A-Za-z]+ \d{4} \d{2}:\d{2}:\d{2} by ([\w\- ]+)'
  updated_pattern: 'Updated (\d{1,2} [A-Za-z]+ \d{4} \d{2}:\d{2}:\d{2}) by ([\w\- ]+)'
  version_pattern: 'Revision #(\d+)'
  date_input_format: "%d %B %Y %H:%M:%S"
  date_output_format: "%d.%m.%Y"
```

If your BookStack UI is not English, update the patterns to match your exported HTML.

### Localized Labels

All generated labels can be changed:

```yaml
strings:
  toc_title: "Table of Contents"
  page_of: "Page {page} of {pages}"
  created_by: "Created by"
  updated_by: "Updated by"
  updated_at: "Updated"
  version: "Version"
  web_label: "Web"
  email_label: "Email"
  phone_label: "Phone"
```

## Command Line Use

Render a BookStack-exported HTML file directly:

```bash
bookstack-to-pdf input.html output.pdf --config /etc/bookstack-to-pdf/config.yaml
bookstack-to-pdf input.html output.pdf --verbose
bookstack-to-pdf input.html output.pdf --dump-input /tmp/bookstack-to-pdf-input.html
```

From a development checkout:

```bash
uv sync --dev
uv run python -m bookstack_to_pdf tests/fixtures/sample_bookstack.html /tmp/bookstack-sample.pdf --config config.example.yaml
```

## Development And Validation

Run the test suite:

```bash
uv run python -m pytest
```

Run a PDF smoke test:

```bash
uv run python -m bookstack_to_pdf tests/fixtures/sample_bookstack.html /tmp/bookstack-sample.pdf --config config.example.yaml
ls -lh /tmp/bookstack-sample.pdf
```

The smoke render should produce a non-empty PDF and should not require remote asset fetching when the configured logo and fonts exist locally.

## Troubleshooting

**BookStack export fails immediately**

Check BookStack's Laravel log:

```bash
tail -f /var/www/bookstack/storage/logs/laravel.log
```

Look for `PDF Export via command failed`, the exit code, and stderr from `bookstack-to-pdf`.

**Config is ignored**

Use an absolute `--config` path in `EXPORT_PDF_COMMAND`. Relative paths are resolved from BookStack's working directory, not this project directory.

**Logo or fonts do not appear**

Confirm the files exist relative to `config.yaml`, then confirm the BookStack process user can traverse the project directory and read `assets`.

```bash
find /opt/bookstack-to-pdf/assets -maxdepth 2 -type f -ls
```

**Tags do not appear on the cover**

First confirm `cover.show_tags: true` in the config used by BookStack. Then temporarily dump the exact HTML that BookStack passes to the PDF command:

```env
EXPORT_PDF_COMMAND="/opt/bookstack-to-pdf/.venv/bin/bookstack-to-pdf --config /opt/bookstack-to-pdf/config.yaml --dump-input /tmp/bookstack-to-pdf-input.html --verbose {input_html_path} {output_pdf_path}"
```

Run one PDF export from BookStack, then check the dumped HTML on the server:

```bash
grep -n '<section class="tag-section-page"' /tmp/bookstack-to-pdf-input.html
```

If the grep returns nothing, BookStack did not include tags in the export HTML. Lines such as `.tag-item[data-name="Bereich"]` are only CSS rules. Fix the BookStack export/theme override first. If the grep finds the section, check BookStack's Laravel log for the verbose line `Extracted N BookStack tag(s)` and confirm the command uses the expected config file.

Remove `--dump-input` after debugging because the copied HTML can contain private page content.

**WeasyPrint or Pango errors**

Install the platform libraries listed in Requirements. On minimal servers, missing Pango libraries are the most common cause.

**Rendering times out**

Increase `EXPORT_PDF_COMMAND_TIMEOUT` only after checking for unusually large pages, very large images, or remote assets. A 60 second timeout is a sensible starting point.

## Security Notes

- Remote assets are blocked by default through a custom WeasyPrint URL fetcher.
- JavaScript does not execute during rendering.
- BookStack content can still create expensive layouts, so keep an export timeout configured.

## License

Apache-2.0. See [LICENSE](LICENSE).
