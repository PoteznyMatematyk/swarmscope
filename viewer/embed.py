"""Embed a ``report.json`` into the SwarmScope Evidence Viewer, producing one self-contained HTML file.

    python viewer/embed.py --report report.json --out report.html

The viewer contains ``<script id="report-data" type="application/json">null</script>``. This script replaces the
``null`` with the report. Transcript text is untrusted (written by AI agents and unknown humans), so the JSON is
made safe to sit inside a <script> element: every ``<`` that could open a tag or a comment is escaped, and the
JavaScript line separators U+2028/U+2029 are written as escapes. The result is still valid JSON that decodes to
exactly the original report.

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_TEMPLATE = Path(__file__).with_name("index.html")
# The placeholder must be exactly ``null``: a template that already carries a report is refused, never overwritten.
PLACEHOLDER = re.compile(r'(<script id="report-data" type="application/json">)\s*null\s*(</script>)')
_LT = re.compile(r"<(?=!--|script)", re.IGNORECASE)


def json_for_script(report: object) -> str:
    """Serialise ``report`` so that it cannot terminate or confuse the surrounding <script> element."""
    text = json.dumps(report, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    text = _LT.sub("\\\\u003c", text)            # "<!--" and "<script" -> <... (a comment opener can swallow </script>)
    text = text.replace("</", "<\\/")            # "</"  -> "<\/"  (a valid JSON escape of "/"): no closing tag can appear
    return text.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def embed(template: str, report: object) -> str:
    """Return ``template`` with the report inserted. Raises ``ValueError`` if the placeholder is not there."""
    if len(PLACEHOLDER.findall(template)) != 1:
        raise ValueError('placeholder <script id="report-data" type="application/json">null</script> not found exactly once '
                         "(is a report already embedded in this template?)")
    payload = json_for_script(report)
    return PLACEHOLDER.sub(lambda m: m.group(1) + payload + m.group(2), template, count=1)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Embed report.json into the SwarmScope Evidence Viewer.")
    ap.add_argument("--report", required=True, help="report.json produced by `swarmscope report`")
    ap.add_argument("--out", required=True, help="output HTML file")
    ap.add_argument("--template", default=str(DEFAULT_TEMPLATE), help="viewer template (default: index.html next to this script)")
    args = ap.parse_args(argv)
    try:
        report = json.loads(Path(args.report).read_text(encoding="utf-8"))
        html = embed(Path(args.template).read_text(encoding="utf-8"), report)
    except (OSError, ValueError) as exc:          # json.JSONDecodeError is a ValueError
        print(f"embed: {exc}", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.write_text(html, encoding="utf-8", newline="\n")
    print(f"embed: wrote {out} ({len(html.encode('utf-8')) / 1024:.0f} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
