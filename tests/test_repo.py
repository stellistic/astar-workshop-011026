"""Repository-level checks: notebooks are built from source, are valid, and every lab guide's links resolve."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tools.notebooks import build as nb_build

ROOT = Path(__file__).resolve().parents[1]
LAB_DIRS = sorted(p for p in ROOT.glob("lab0*") if p.is_dir())


def test_notebooks_are_up_to_date_with_their_sources() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tools.notebooks.build", "--check"], cwd=ROOT, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("target", sorted(nb_build.TARGETS.values()))
def test_notebook_is_valid_fabric_ipynb(target: str) -> None:
    nb = json.loads((ROOT / target).read_text(encoding="utf-8"))
    assert nb["nbformat"] == 4
    assert nb["metadata"]["kernelspec"]["name"] == "synapse_pyspark"
    kinds = [c["cell_type"] for c in nb["cells"]]
    assert kinds[0] == "markdown", "every notebook opens with an explanation"
    assert kinds.count("code") >= 3
    for cell in nb["cells"]:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == [] and cell["execution_count"] is None, "ship notebooks without outputs"


@pytest.mark.parametrize("target", sorted(nb_build.TARGETS.values()))
def test_notebook_code_cells_are_valid_python(target: str) -> None:
    nb = json.loads((ROOT / target).read_text(encoding="utf-8"))
    for i, cell in enumerate(nb["cells"]):
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        lines = [ln for ln in source.splitlines() if not ln.lstrip().startswith(("%", "!"))]
        if source.lstrip().startswith("%%sql"):
            continue
        compile("\n".join(lines), f"{target}#cell{i}", "exec")


def test_parse_cells_splits_markdown_and_code() -> None:
    cells = nb_build.parse_cells("# %% [markdown]\n# # Title\n# text\n\n# %%\nx = 1\n\n# %%\n%%sql\nSELECT 1\n")
    assert [c["cell_type"] for c in cells] == ["markdown", "code", "code"]
    assert "".join(cells[0]["source"]) == "# Title\ntext"
    assert "".join(cells[2]["source"]) == "%%sql\nSELECT 1"


def _markdown_files() -> list[Path]:
    return [ROOT / "README.md", *sorted(ROOT.glob("lab0*/README.md")), *sorted((ROOT / "docs").rglob("*.md"))]


@pytest.mark.parametrize("md", _markdown_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_relative_links_and_images_resolve(md: Path) -> None:
    text = md.read_text(encoding="utf-8")
    broken = []
    for target in re.findall(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", text):
        if re.match(r"^(https?:|mailto:|#)", target):
            continue
        path = (md.parent / target.split("#", 1)[0]).resolve()
        if not path.exists():
            broken.append(target)
    assert not broken, f"{md.relative_to(ROOT)} has broken links: {broken}"


def test_every_lab_has_a_guide() -> None:
    assert LAB_DIRS, "no lab folders found"
    for lab in LAB_DIRS:
        assert (lab / "README.md").exists(), f"{lab.name} has no README.md"


def test_expected_results_doc_is_up_to_date() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tools.kit.expected_doc", "--check"], cwd=ROOT, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
