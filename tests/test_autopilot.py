"""Autopilot status contract and the status-page renderer."""

import importlib.util
import json
import shutil

import jsonschema
import pytest

from conftest import REPO_ROOT, SKILL_DIR


EXAMPLE = REPO_ROOT / "examples" / "synthetic-crm"
SCHEMA = json.loads((SKILL_DIR / "templates" / "autopilot-run.schema.json").read_text())


def load_renderer():
    spec = importlib.util.spec_from_file_location("render_status", SKILL_DIR / "tools" / "render_status.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def run_dir(tmp_path):
    for name in ("teardown.json", "autopilot.json", "feature-inventory.json", "preservation-manifest.json"):
        shutil.copy(EXAMPLE / name, tmp_path / name)
    return tmp_path


def edit(path, **changes):
    data = json.loads(path.read_text())
    data.update(changes)
    path.write_text(json.dumps(data))


def test_example_autopilot_file_matches_schema():
    jsonschema.Draft202012Validator(SCHEMA).validate(json.loads((EXAMPLE / "autopilot.json").read_text()))


def test_schema_rejects_unknown_step_status():
    data = json.loads((EXAMPLE / "autopilot.json").read_text())
    data["steps"][0]["status"] = "probably-fine"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(SCHEMA).validate(data)


def test_unknown_usage_is_never_counted_as_unused():
    counts = load_renderer().summarize(json.loads((EXAMPLE / "feature-inventory.json").read_text()))
    assert counts == {
        "total": 4,
        "used": 2,
        "never": 1,
        "unknown": 1,
        "verdicts": {"KEEP": 1, "SIMPLIFY": 1, "DROP": 1, "DEFER": 1},
    }


def test_finished_first_pass_renders_headline_and_stops_refreshing(run_dir):
    edit(run_dir / "teardown.json", status="in-progress", phase=3)
    page = load_renderer().write_status(run_dir).read_text()
    assert "2 <small>of 4 features" in page
    assert "1 never used · 1 not yet known" in page
    assert "http-equiv=refresh" not in page
    assert "First pass done" in page
    assert "does not have admin access" in page
    assert not list(run_dir.glob(".status-*")), "temporary file left behind"


def test_running_page_refreshes_and_shows_current_activity(run_dir):
    edit(run_dir / "teardown.json", status="in-progress")
    auto = json.loads((run_dir / "autopilot.json").read_text())
    auto["steps"][-1]["status"] = "running"
    (run_dir / "autopilot.json").write_text(json.dumps(auto))
    edit(run_dir / "autopilot.json", now="Reading the Workflows list")
    page = load_renderer().render(run_dir)
    assert "http-equiv=refresh" in page
    assert "Reading the Workflows list" in page


def test_renders_before_any_findings_exist(tmp_path):
    (tmp_path / "teardown.json").write_text(json.dumps({"app": {"name": "Example"}, "status": "in-progress"}))
    (tmp_path / "feature-inventory.json").write_text("[{")  # caught mid-write
    page = load_renderer().render(tmp_path)
    assert "Mapping the app" in page


def test_tenant_text_is_escaped(run_dir):
    features = json.loads((run_dir / "feature-inventory.json").read_text())
    features[0]["name"] = "<script>alert(1)</script>"
    (run_dir / "feature-inventory.json").write_text(json.dumps(features))
    edit(run_dir / "autopilot.json", now="<img src=x onerror=1>")
    page = load_renderer().render(run_dir)
    assert "<script>alert(1)</script>" not in page
    assert "<img src=x" not in page
    assert "&lt;script&gt;" in page


def test_skill_points_at_autopilot_files(skill_md_text):
    for name in ("references/autopilot.md", "references/autopilot-hubspot.md",
                 "templates/autopilot-run.schema.json", "tools/render_status.py"):
        assert name in skill_md_text
        assert (SKILL_DIR / name).is_file()
