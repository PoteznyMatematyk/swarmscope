"""`swarmscope viewer` embeds a report into the offline viewer; hostile text must not be able to break out of the <script>."""

import json

import pytest

from swarmscope.cli import main


def test_viewer_command_embeds_report(tmp_path):
    report = {"meta": {"title": "t"}, "findings": [{"id": "F1", "title": "x</script><img src=x onerror=alert(1)>", "thesis": "y"}]}
    src, out = tmp_path / "report.json", tmp_path / "report.html"
    src.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        main(["viewer", "--report", str(src), "--out", str(out)])
    assert exc.value.code == 0
    html = out.read_text(encoding="utf-8")
    assert '"F1"' in html and "</script><img" not in html  # payload cannot close the data script element
    assert html.count('<script id="report-data"') == 1


def test_viewer_command_rejects_missing_report(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main(["viewer", "--report", str(tmp_path / "nope.json"), "--out", str(tmp_path / "o.html")])
    assert exc.value.code == 2
