"""Converts percent-format notebook sources (tools/notebooks/src/*.py) into Fabric-importable .ipynb files.

Authoring notebooks as plain Python keeps them reviewable and diffable. Cell markers:

    # %% [markdown]      starts a markdown cell; every line is written as "# text" and the "# " is stripped
    # %%                 starts a code cell

Usage:
    python -m tools.notebooks.build            # write every notebook listed in TARGETS
    python -m tools.notebooks.build --check    # exit 1 if any .ipynb is out of date (used by tests)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "tools" / "notebooks" / "src"

TARGETS: dict[str, str] = {
    "02_bronze_ingest.py": "lab02-bronze/notebooks/02_bronze_ingest.ipynb",
    "03_silver_transform.py": "lab03-silver-notebook/notebooks/03_silver_transform.ipynb",
    "04_silver_dims_catchup.py": "lab04-silver-dataflow/notebooks/04_silver_dims_catchup.ipynb",
    "05_gold_star_schema.py": "lab05-gold/notebooks/05_gold_star_schema.ipynb",
    "06_utility_bills_ai.py": "lab06-unstructured-ai/notebooks/06_utility_bills_ai.ipynb",
    "07_semantic_model_catchup.py": "lab07-semantic-model/notebooks/07_semantic_model_catchup.ipynb",
}

METADATA = {
    "language_info": {"name": "python"},
    "kernelspec": {"name": "synapse_pyspark", "display_name": "Synapse PySpark"},
    "microsoft": {"language": "python", "language_group": "synapse_pyspark"},
    "kernel_info": {"name": "synapse_pyspark"},
}


def parse_cells(text: str) -> list[dict]:
    cells: list[dict] = []
    kind: str | None = None
    buf: list[str] = []

    def flush() -> None:
        if kind is None:
            return
        lines = buf[:]
        while lines and not lines[-1].strip():
            lines.pop()
        while lines and not lines[0].strip():
            lines.pop(0)
        if kind == "markdown":
            lines = [ln[2:] if ln.startswith("# ") else ln.lstrip("#") for ln in lines]
        if not lines:
            return
        source = [ln + "\n" for ln in lines]
        source[-1] = source[-1].rstrip("\n")
        cell: dict = {"cell_type": kind, "metadata": {}, "source": source}
        if kind == "code":
            cell.update({"execution_count": None, "outputs": []})
        cells.append(cell)

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# %% [markdown]"):
            flush()
            kind, buf = "markdown", []
        elif stripped == "# %%" or stripped.startswith("# %% "):
            flush()
            kind, buf = "code", []
        elif kind is not None:
            buf.append(line)
    flush()
    return cells


def render(src: Path, lakehouse: dict | None = None) -> str:
    metadata = dict(METADATA)
    if lakehouse is not None:
        metadata["dependencies"] = {"lakehouse": lakehouse}
    nb = {
        "cells": parse_cells(src.read_text(encoding="utf-8")),
        "metadata": metadata,
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    return json.dumps(nb, indent=1, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale: list[str] = []
    for src_name, target in TARGETS.items():
        src = SRC / src_name
        if not src.exists():
            continue
        out = ROOT / target
        rendered = render(src)
        if args.check:
            if not out.exists() or out.read_text(encoding="utf-8") != rendered:
                stale.append(target)
        else:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(rendered, encoding="utf-8")
            print(f"wrote {target}")
    if stale:
        print("stale notebooks (run python -m tools.notebooks.build):\n  " + "\n  ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
