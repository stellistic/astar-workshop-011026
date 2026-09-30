"""Renders docs/facilitator/expected-results.md from tools/expected_counts.json so the two can never drift.

Usage:
    python -m tools.kit.expected_doc           # write the document
    python -m tools.kit.expected_doc --check   # exit 1 if it is out of date (used by tests)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COUNTS = ROOT / "tools" / "expected_counts.json"
TARGET = ROOT / "docs" / "facilitator" / "expected-results.md"

ISSUE_TEXT = {
    "exact_duplicates": "exact duplicate rows",
    "negative_scrap": "negative `ScrapUnits`",
    "invalid_datekey": "impossible `DateKey` (e.g. 20250230)",
    "missing_actual_units": "blank `ActualUnits`",
    "operator_team_variants": "`OperatorTeam` spelling variants",
    "defects_exceed_inspected": "`DefectCount` > `InspectedUnits`",
    "missing_defect_type": "blank `DefectTypeKey`",
    "severity_variants": "`Severity` case/padding variants",
    "blank_root_cause": "blank `RootCause`",
    "preventive_flag_variants": "`PreventiveFlag` as Y/N/yes/TRUE…",
    "dmy_required_ship_date": "dates written dd/MM/yyyy",
    "open_orders": "blank `ActualShipDate` (open orders)",
    "orphan_customer": "`CustomerKey = 999` (no such customer)",
    "revenue_with_thousands_separator": '`Revenue` like `"198,801"`',
    "duplicate_keys": "duplicate key row",
    "untrimmed_names": "untrimmed `ProductName`",
    "currency_formatted_price": '`UnitPrice` like `"$1,199.00"`',
    "lowercase_category": "lower-case `Category`",
    "country_variants": "`Country` as SG/MY/IN/AU or odd casing",
    "messy_plant_code": "`PlantCode` lower-case or padded",
}

SILVER_HANDLING = {
    "exact_duplicates": "removed",
    "negative_scrap": "quarantined",
    "invalid_datekey": "quarantined",
    "missing_actual_units": "quarantined",
    "defects_exceed_inspected": "quarantined",
    "missing_defect_type": "→ `-1` *Not recorded*",
    "orphan_customer": "kept; Gold → `-1` *Unknown customer*",
    "open_orders": "kept, `OrderStatus = Open`",
    "duplicate_keys": "removed (Lab 4)",
}


def snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def pct(v: float) -> str:
    return f"{v * 100:.2f}%"


def render(c: dict) -> str:
    k = c["kpis"]
    lines = [
        "[← Workshop home](../../README.md)",
        "",
        "# Expected results",
        "",
        "> Generated from [`tools/expected_counts.json`](../../tools/expected_counts.json) by",
        "> `python -m tools.kit.expected_doc`. Don't edit by hand.",
        "",
        "The workshop data is fixed and seeded deterministically, so **every participant gets exactly these numbers**.",
        "Each notebook's final *verify* cell checks them automatically.",
        "",
        "## Lab 1 · Files",
        "",
        "| Lakehouse folder | Files |",
        "|---|---:|",
        f"| `Files/landing/plant` | {len(c['bronze'])} |",
        f"| `Files/landing/utility_bills` | {c['utility_bills']['documents']} "
        f"({c['utility_bills']['digital']} digital, {c['utility_bills']['scanned']} scanned) |",
        "| `Files/landing/reference` | 2 |",
        "",
        "## Lab 2 · Bronze",
        "",
        "| Table | Rows |",
        "|---|---:|",
    ]
    lines += [f"| `bronze.{snake(n)}` | {v:,} |" for n, v in sorted(c["bronze"].items(), key=lambda x: snake(x[0]))]
    lines += [f"| **Total** | **{sum(c['bronze'].values()):,}** |", "", "## Labs 3–4 · Silver", ""]
    lines += ["| Table | Rows | Built in |", "|---|---:|---|"]
    lab4 = {"dim_product", "dim_customer", "dim_plant"}
    lines += [
        f"| `silver.{t}` | {v:,} | {'Lab 4 (Dataflow Gen2)' if t in lab4 else 'Lab 3 (notebook)'} |"
        for t, v in c["silver"].items()
    ]
    lines += ["", "## Lab 5 · Gold", "", "| Table | Rows |", "|---|---:|"]
    lines += [f"| `gold.{t}` | {v:,} |" for t, v in c["gold"].items()]
    lines += [
        "| `gold.fact_utility_bill` (Lab 6) | 48 |",
        "",
        "## Lab 7 · Semantic model measures",
        "",
        "| Measure | Expected value |",
        "|---|---:|",
        f"| Actual Units | {k['actual_units']:,} |",
        f"| Planned Units | {k['planned_units']:,} |",
        f"| Scrap Units | {k['scrap_units']:,} |",
        f"| Scrap Rate % | {pct(k['scrap_rate_pct'])} |",
        f"| Production Attainment % | {pct(k['production_attainment_pct'])} |",
        f"| Inspected Units | {k['inspected_units']:,} |",
        f"| Defect Count | {k['defect_count']:,} |",
        f"| Defect Rate % | {pct(k['defect_rate_pct'])} |",
        f"| Orders | {k['orders']:,} |",
        f"| Late Order % | {k['late_orders'] / k['orders'] * 100:.1f}% ({k['late_orders']} late) |",
        f"| Total Revenue | {k['total_revenue']:,.0f} |",
        f"| Maintenance Events | {k['maintenance_events']:,} |",
        f"| Preventive Maintenance % | {k['preventive_maintenance_pct'] * 100:.1f}% |",
        "| Electricity kWh (Lab 6, from the PDFs) | 3,355,595 |",
        "| Energy per Unit kWh (Lab 6 × MES) | 16.65 (SG-01 22.05 · MY-01 18.28 · AU-01 15.68 · IN-01 11.84) |",
        "",
        "## What was seeded",
        "",
        f"Seed `{c['seed']}`. Only the tables below were changed; every other file is byte-identical to the",
        "K-Corp-Plant source.",
        "",
        "| File | Issue | Rows | Silver handling |",
        "|---|---|---:|---|",
    ]
    for table, issues in c["seeded_issues"].items():
        for key, n in issues.items():
            handling = SILVER_HANDLING.get(key, "conformed")
            lines.append(f"| `{table}.csv` | {ISSUE_TEXT.get(key, key)} | {n} | {handling} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = render(json.loads(COUNTS.read_text(encoding="utf-8")))
    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != text:
            print("expected-results.md is stale: run python -m tools.kit.expected_doc")
            return 1
        return 0
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(text, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
