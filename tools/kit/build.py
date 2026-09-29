"""Builds the participant data kit from the clean K-Corp-Plant extract.

The workshop needs data that is *realistically* dirty, so Silver has real work to do. This module takes the clean
source CSVs (tools/source/kcorp_plant) and seeds a fixed, documented set of data-quality issues with a fixed random
seed, so every build is byte-for-byte identical and the lab guides can quote exact row counts.

Usage:
    python -m tools.kit.build                       # rebuild CSVs, ground truth and expected counts
    python -m tools.kit.build --bills-src <pdf dir>  # also (re)curate the 48 utility-bill PDFs
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import random
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

SEED = 20261001
KIT_VERSION = "1.0.0"

PLANT_FILES = [
    "DimAsset",
    "DimCustomer",
    "DimDate",
    "DimDefectType",
    "DimLine",
    "DimPlant",
    "DimProduct",
    "DimShift",
    "FactAnomalyEvent",
    "FactCustomerOrder",
    "FactMaintenanceEvent",
    "FactProductionRun",
    "FactQualityInspection",
]
UNTOUCHED = {"DimAsset", "DimDate", "DimDefectType", "DimLine", "DimShift", "FactAnomalyEvent"}
BILL_PERIODS = [f"2026{m:02d}" for m in range(1, 7)]

Row = dict[str, str]


@dataclass
class Table:
    header: list[str]
    rows: list[Row]
    issues: dict[str, int] = field(default_factory=dict)


def read_table(path: Path) -> Table:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return Table(header=list(reader.fieldnames or []), rows=[dict(r) for r in reader])


def write_table(path: Path, table: Table) -> None:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=table.header, lineterminator="\n")
    writer.writeheader()
    writer.writerows(table.rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(buf.getvalue(), encoding="utf-8")


class Picker:
    """Hands out disjoint random row indices so seeded issues never overlap and counts stay exact."""

    def __init__(self, rng: random.Random, candidates: list[int]) -> None:
        self._rng = rng
        self._free = list(candidates)

    def take(self, n: int, where: Callable[[int], bool] | None = None) -> list[int]:
        pool = [i for i in self._free if where is None or where(i)]
        if len(pool) < n:
            raise ValueError(f"only {len(pool)} candidate rows left, need {n}")
        chosen = sorted(self._rng.sample(pool, n))
        taken = set(chosen)
        self._free = [i for i in self._free if i not in taken]
        return chosen


def _insert_duplicates(rng: random.Random, rows: list[Row], sources: list[int]) -> list[Row]:
    out = list(rows)
    for copy in [dict(rows[i]) for i in sources]:
        out.insert(rng.randint(0, len(out)), copy)
    return out


def _dmy(iso: str) -> str:
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")


def seed_production_runs(rng: random.Random, t: Table) -> Table:
    rows = [dict(r) for r in t.rows]
    pick = Picker(rng, list(range(len(rows))))
    for i in pick.take(8, lambda i: int(rows[i]["ScrapUnits"]) > 0):
        rows[i]["ScrapUnits"] = f"-{rows[i]['ScrapUnits']}"
    bad_dates = ["20250230", "20241331", "20240431", "20250931", "20240600"]
    for i, bad in zip(pick.take(5), bad_dates, strict=True):
        rows[i]["DateKey"] = bad
    for i in pick.take(6):
        rows[i]["ActualUnits"] = ""
    for i in pick.take(120):
        letter = rows[i]["OperatorTeam"][-1]
        variants = [f"team-{letter.lower()}", f" Team-{letter}", f"TEAM-{letter} ", f"Team {letter}", f"team_{letter}"]
        rows[i]["OperatorTeam"] = rng.choice(variants)
    rows = _insert_duplicates(rng, rows, pick.take(25))
    return Table(
        t.header,
        rows,
        {
            "exact_duplicates": 25,
            "negative_scrap": 8,
            "invalid_datekey": 5,
            "missing_actual_units": 6,
            "operator_team_variants": 120,
        },
    )


def seed_quality_inspections(rng: random.Random, t: Table) -> Table:
    rows = [dict(r) for r in t.rows]
    if any(int(r["DefectCount"]) > int(r["InspectedUnits"]) for r in rows):
        raise ValueError("source already has DefectCount > InspectedUnits; counts would be wrong")
    pick = Picker(rng, list(range(len(rows))))
    for i in pick.take(7):
        rows[i]["DefectCount"] = str(int(rows[i]["InspectedUnits"]) + rng.randint(5, 40))
    for i in pick.take(12):
        rows[i]["DefectTypeKey"] = ""
    variants = {"Low": ["low", "LOW", " Low", "Low "], "Medium": ["medium", "MEDIUM ", " Medium"], "High": ["high"]}
    for i in pick.take(150):
        rows[i]["Severity"] = rng.choice(variants[rows[i]["Severity"]])
    return Table(t.header, rows, {"defects_exceed_inspected": 7, "missing_defect_type": 12, "severity_variants": 150})


def seed_maintenance_events(rng: random.Random, t: Table) -> Table:
    rows = [dict(r) for r in t.rows]
    pick = Picker(rng, list(range(len(rows))))
    for i in pick.take(9):
        rows[i]["RootCause"] = ""
    truthy = ["Y", "YES", "TRUE", "true", "y"]
    falsy = ["N", "NO", "FALSE", "false", "n"]
    for i in pick.take(60):
        rows[i]["PreventiveFlag"] = rng.choice(truthy if rows[i]["PreventiveFlag"] == "1" else falsy)
    return Table(t.header, rows, {"blank_root_cause": 9, "preventive_flag_variants": 60})


def seed_customer_orders(rng: random.Random, t: Table) -> Table:
    rows = [dict(r) for r in t.rows]
    pick = Picker(rng, list(range(len(rows))))
    for i in pick.take(300):
        rows[i]["RequiredShipDate"] = _dmy(rows[i]["RequiredShipDate"])
        rows[i]["ActualShipDate"] = _dmy(rows[i]["ActualShipDate"])
    for i in pick.take(40):
        rows[i]["ActualShipDate"] = ""
        rows[i]["ShippedUnits"] = "0"
    for i in pick.take(6):
        rows[i]["CustomerKey"] = "999"
    for i in pick.take(50, lambda i: float(rows[i]["Revenue"]) >= 1000):
        rows[i]["Revenue"] = f"{int(float(rows[i]['Revenue'])):,}"
    return Table(
        t.header,
        rows,
        {
            "dmy_required_ship_date": 300,
            "open_orders": 40,
            "orphan_customer": 6,
            "revenue_with_thousands_separator": 50,
        },
    )


def seed_products(rng: random.Random, t: Table) -> Table:
    rows = [dict(r) for r in t.rows]
    pick = Picker(rng, list(range(len(rows))))
    for i in pick.take(4):
        name = rows[i]["ProductName"]
        rows[i]["ProductName"] = rng.choice([f" {name}", f"{name}  ", f"  {name} "])
    for i in pick.take(5):
        rows[i]["UnitPrice"] = f"${float(rows[i]['UnitPrice']):,.2f}"
    for i in pick.take(2):
        rows[i]["Category"] = rows[i]["Category"].lower()
    rows = _insert_duplicates(rng, rows, pick.take(1))
    return Table(
        t.header,
        rows,
        {"duplicate_keys": 1, "untrimmed_names": 4, "currency_formatted_price": 5, "lowercase_category": 2},
    )


def seed_customers(rng: random.Random, t: Table) -> Table:
    rows = [dict(r) for r in t.rows]
    pick = Picker(rng, list(range(len(rows))))
    variants = {
        "Singapore": ["SG", "singapore", "SINGAPORE"],
        "Malaysia": ["MY", "malaysia", "Malaysia "],
        "India": ["IN", "india"],
        "Australia": ["AU", " Australia"],
    }
    for i in pick.take(8):
        rows[i]["Country"] = rng.choice(variants[rows[i]["Country"]])
    rows = _insert_duplicates(rng, rows, pick.take(1))
    return Table(t.header, rows, {"duplicate_keys": 1, "country_variants": 8})


def seed_plants(_rng: random.Random, t: Table) -> Table:
    rows = [dict(r) for r in t.rows]
    for r in rows:
        if r["PlantCode"] == "SG-01":
            r["PlantCode"] = "sg-01"
        elif r["PlantCode"] == "IN-01":
            r["PlantCode"] = " IN-01 "
    return Table(t.header, rows, {"messy_plant_code": 2})


SEEDERS: dict[str, Callable[[random.Random, Table], Table]] = {
    "FactProductionRun": seed_production_runs,
    "FactQualityInspection": seed_quality_inspections,
    "FactMaintenanceEvent": seed_maintenance_events,
    "FactCustomerOrder": seed_customer_orders,
    "DimProduct": seed_products,
    "DimCustomer": seed_customers,
    "DimPlant": seed_plants,
}


def silver_kpis(seeded: dict[str, Table]) -> dict[str, float | int]:
    """Replays the Silver rules in plain Python to produce the numbers the notebooks and model must hit."""
    seen: set[tuple[str, ...]] = set()
    runs: list[Row] = []
    for r in seeded["FactProductionRun"].rows:
        key = tuple(r.values())
        if key in seen:
            continue
        seen.add(key)
        try:
            datetime.strptime(r["DateKey"], "%Y%m%d")
        except ValueError:
            continue
        if r["ActualUnits"].strip() == "" or int(r["ScrapUnits"]) < 0:
            continue
        runs.append(r)
    actual = sum(int(r["ActualUnits"]) for r in runs)
    scrap = sum(int(r["ScrapUnits"]) for r in runs)
    planned = sum(int(r["PlannedUnits"]) for r in runs)
    insp = [r for r in seeded["FactQualityInspection"].rows if int(r["DefectCount"]) <= int(r["InspectedUnits"])]
    inspected = sum(int(r["InspectedUnits"]) for r in insp)
    defects = sum(int(r["DefectCount"]) for r in insp)
    orders = seeded["FactCustomerOrder"].rows
    maint = seeded["FactMaintenanceEvent"].rows
    preventive = sum(1 for r in maint if r["PreventiveFlag"].strip().upper() in {"1", "Y", "YES", "TRUE"})
    return {
        "planned_units": planned,
        "actual_units": actual,
        "scrap_units": scrap,
        "production_attainment_pct": round(actual / planned, 4),
        "scrap_rate_pct": round(scrap / (actual + scrap), 4),
        "inspected_units": inspected,
        "defect_count": defects,
        "defect_rate_pct": round(defects / inspected, 4),
        "orders": len(orders),
        "open_orders": sum(1 for r in orders if r["ActualShipDate"].strip() == ""),
        "late_orders": sum(int(r["LateShipmentFlag"]) for r in orders),
        "total_revenue": round(sum(float(r["Revenue"].replace(",", "")) for r in orders), 2),
        "maintenance_events": len(maint),
        "preventive_events": preventive,
        "preventive_maintenance_pct": round(preventive / len(maint), 4),
        "maintenance_downtime_minutes": sum(int(r["DowntimeMinutes"]) for r in maint),
        "plant_months": len({(r["PlantKey"], r["DateKey"][:6]) for r in runs}),
    }


def curate_bills(source_dir: Path, out_dir: Path, bills_src: Path | None) -> dict[str, int]:
    manifest = [
        r for r in read_table(source_dir / "utility_bills" / "manifest.csv").rows if r["billing_period"] in BILL_PERIODS
    ]
    truth = read_table(source_dir / "utility_bills" / "ground_truth_bill.csv")
    truth.rows = [r for r in truth.rows if r["billing_period"] in BILL_PERIODS]
    write_table(out_dir / "data" / "landing" / "reference" / "utility_bills_ground_truth.csv", truth)
    if bills_src is not None:
        for m in manifest:
            # flat folder: the Lakehouse upload pane accepts files, not folders
            dest = out_dir / "data" / "landing" / "utility_bills" / m["file_name"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(bills_src / m["relative_path"], dest)
    scanned = sum(1 for m in manifest if m["render_mode"] == "scanned")
    return {"documents": len(manifest), "scanned": scanned, "digital": len(manifest) - scanned}


def build_kit(source_dir: Path, out_dir: Path, bills_src: Path | None, counts_path: Path | None = None) -> dict:
    rng = random.Random(SEED)
    plant_src = source_dir / "kcorp_plant"
    plant_out = out_dir / "data" / "landing" / "plant"
    plant_out.mkdir(parents=True, exist_ok=True)

    source = {name: read_table(plant_src / f"{name}.csv") for name in PLANT_FILES}
    seeded: dict[str, Table] = {}
    for name in PLANT_FILES:
        if name in UNTOUCHED:
            shutil.copyfile(plant_src / f"{name}.csv", plant_out / f"{name}.csv")
            seeded[name] = source[name]
        else:
            seeded[name] = SEEDERS[name](rng, source[name])
            write_table(plant_out / f"{name}.csv", seeded[name])

    issues = {name: t.issues for name, t in seeded.items() if t.issues}
    pr, qi = issues["FactProductionRun"], issues["FactQualityInspection"]
    pr_rejects = pr["negative_scrap"] + pr["invalid_datekey"] + pr["missing_actual_units"]
    silver = {
        "fact_production_run": len(seeded["FactProductionRun"].rows) - pr["exact_duplicates"] - pr_rejects,
        "fact_quality_inspection": len(seeded["FactQualityInspection"].rows) - qi["defects_exceed_inspected"],
        "fact_maintenance_event": len(seeded["FactMaintenanceEvent"].rows),
        "fact_customer_order": len(seeded["FactCustomerOrder"].rows),
        "dim_product": len(source["DimProduct"].rows),
        "dim_customer": len(source["DimCustomer"].rows),
        "dim_plant": len(source["DimPlant"].rows),
        "dim_date": len(source["DimDate"].rows),
        "dim_shift": len(source["DimShift"].rows),
        "dim_line": len(source["DimLine"].rows),
        "dim_asset": len(source["DimAsset"].rows),
        "dim_defect_type": len(source["DimDefectType"].rows),
        "dq_rejects": pr_rejects + qi["defects_exceed_inspected"],
    }
    kpis = silver_kpis(seeded)
    gold = {
        "dim_date": silver["dim_date"],
        "dim_plant": silver["dim_plant"],
        "dim_line": silver["dim_line"],
        "dim_asset": silver["dim_asset"],
        "dim_shift": silver["dim_shift"],
        "dim_product": silver["dim_product"],
        "dim_customer": silver["dim_customer"] + 1,
        "dim_defect_type": silver["dim_defect_type"] + 1,
        "fact_production_run": silver["fact_production_run"],
        "fact_quality_inspection": silver["fact_quality_inspection"],
        "fact_maintenance_event": silver["fact_maintenance_event"],
        "fact_customer_order": silver["fact_customer_order"],
        "agg_plant_month": kpis["plant_months"],
    }
    counts = {
        "kit_version": KIT_VERSION,
        "seed": SEED,
        "bronze": {name: len(t.rows) for name, t in seeded.items()},
        "seeded_issues": issues,
        "silver": silver,
        "gold": gold,
        "kpis": kpis,
        "utility_bills": curate_bills(source_dir, out_dir, bills_src),
    }
    target = counts_path or out_dir / "expected_counts.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(counts, indent=2) + "\n", encoding="utf-8")
    return counts


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bills-src", type=Path, default=None, help="folder holding YYYYMM/<doc>.pdf bills")
    args = parser.parse_args()
    counts = build_kit(
        source_dir=root / "tools" / "source",
        out_dir=root,
        bills_src=args.bills_src,
        counts_path=root / "tools" / "expected_counts.json",
    )
    print(json.dumps({"bronze": counts["bronze"], "silver": counts["silver"], "kpis": counts["kpis"]}, indent=2))


if __name__ == "__main__":
    main()
