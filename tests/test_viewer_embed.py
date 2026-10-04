import importlib.util
import json
import re
from pathlib import Path

import pytest

VIEWER = Path(__file__).resolve().parents[1] / "viewer"
_spec = importlib.util.spec_from_file_location("viewer_embed", VIEWER / "embed.py")
embed_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(embed_mod)

TEMPLATE = (
    "<html><body><main></main>"
    '<script id="report-data" type="application/json">null</script>'
    "<script>const viewer = 1;</script></body></html>"
)
DATA = re.compile(r'<script id="report-data" type="application/json">(.*?)</script>', re.S)


def extract(html: str):
    """What a browser would hand to JSON.parse: the text of the first <script> element."""
    return json.loads(DATA.search(html).group(1))


def test_round_trip_keeps_report_exact_and_template_untouched():
    report = {"meta": {"title": "Grzegorz “Brżęczyszczykiewicz” \U0001F3EE"},
              "claims": [{"id": "Q1-1", "evidence": [{"quote": "a < b && c > d", "span": [3, 9]}]}], "cascades": []}
    html = embed_mod.embed(TEMPLATE, report)
    assert extract(html) == report
    assert html == TEMPLATE.replace(">null<", ">" + embed_mod.json_for_script(report) + "<")   # only the placeholder changed


def test_hostile_quote_cannot_break_out_of_the_script_element():
    evil = '</script><img src=x onerror=alert(1)><!--<script>alert(2)</script>'
    report = {"claims": [{"evidence": [{"quote": evil, "context": evil + "  "}]}]}
    html = embed_mod.embed(TEMPLATE, report)
    assert html.count("</script>") == TEMPLATE.count("</script>")          # no extra closing tag
    assert "<!--" not in html and "<script>alert" not in html               # no comment opener / nested script start (<img is inert text in a JSON block)
    data_block = DATA.search(html).group(1)
    assert " " not in data_block and " " not in data_block
    assert extract(html) == report                                          # yet it decodes to the exact original text


def test_missing_or_already_filled_placeholder_is_an_error():
    with pytest.raises(ValueError, match="placeholder"):
        embed_mod.embed("<html><body>no data block</body></html>", {"a": 1})
    filled = embed_mod.embed(TEMPLATE, {"a": 1})
    with pytest.raises(ValueError, match="placeholder"):
        embed_mod.embed(filled, {"a": 2})                                   # never silently overwrite an embedded report


def test_cli_writes_output_and_reports_errors(tmp_path, capsys):
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"meta": {"title": "t"}, "claims": []}), encoding="utf-8")
    tpl = tmp_path / "tpl.html"
    tpl.write_text(TEMPLATE, encoding="utf-8")
    out = tmp_path / "out.html"
    assert embed_mod.main(["--report", str(report), "--out", str(out), "--template", str(tpl)]) == 0
    assert extract(out.read_text(encoding="utf-8")) == {"meta": {"title": "t"}, "claims": []}

    tpl.write_text("<html></html>", encoding="utf-8")
    assert embed_mod.main(["--report", str(report), "--out", str(tmp_path / "o2.html"), "--template", str(tpl)]) == 2
    assert "placeholder" in capsys.readouterr().err
    report.write_text("{not json", encoding="utf-8")
    assert embed_mod.main(["--report", str(report), "--out", str(tmp_path / "o3.html"), "--template", str(tpl)]) == 2
    assert not (tmp_path / "o3.html").exists()


def test_real_viewer_template_has_exactly_one_placeholder_and_no_data_flows_into_innerhtml():
    html = (VIEWER / "index.html").read_text(encoding="utf-8")
    assert len(embed_mod.PLACEHOLDER.findall(html)) == 1
    out = embed_mod.embed(html, {"claims": [{"evidence": [{"quote": "</script><b>x</b>"}]}]})
    assert out.count("</script>") == html.count("</script>")
    for banned in ("innerHTML", "insertAdjacentHTML", "outerHTML", "document.write"):
        assert banned not in html                                            # report text is only ever set via textContent
