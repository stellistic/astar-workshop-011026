"""Tests for the seeded data-quality issues in the participant data kit.

Each test recounts an issue directly from the generated CSVs, independently of the seeding code, and checks it
against the numbers the lab guides promise (tools/expected_counts.json).
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

import pytest

from tools.kit import build

ROOT = Path(__file__).resolve().parents[1]


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _valid_yyyymmdd(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y%m%d")
    except ValueError:
        return False
    return True


@pytest.fixture(scope="module")
def kit(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("kit")
    build.build_kit(source_dir=ROOT / "tools" / "source", out_dir=out, bills_src=None)
    return out


@pytest.fixture(scope="module")
def expected(kit: Path) -> dict:
    return json.loads((kit / "expected_counts.json").read_text())


def plant(kit: Path, name: str) -> list[dict[str, str]]:
    return _rows(kit / "data" / "landing" / "plant" / f"{name}.csv")


def test_all_thirteen_plant_files_are_written(kit: Path) -> None:
    files = sorted(p.stem for p in (kit / "data" / "landing" / "plant").glob("*.csv"))
    assert files == sorted(build.PLANT_FILES)
    assert len(files) == 13


def test_untouched_dimensions_match_source_exactly(kit: Path) -> None:
    for name in ["DimDate", "DimShift", "DimLine", "DimAsset", "DimDefectType", "FactAnomalyEvent"]:
        src = (ROOT / "tools" / "source" / "kcorp_plant" / f"{name}.csv").read_bytes()
        assert (kit / "data" / "landing" / "plant" / f"{name}.csv").read_bytes() == src, name


def test_production_run_issues(kit: Path, expected: dict) -> None:
    rows = plant(kit, "FactProductionRun")
    exp = expected["seeded_issues"]["FactProductionRun"]
    keyed = [tuple(r.values()) for r in rows]
    assert len(keyed) - len(set(keyed)) == exp["exact_duplicates"] == 25
    assert sum(1 for r in rows if r["ScrapUnits"].startswith("-")) == exp["negative_scrap"] == 8
    assert sum(1 for r in rows if not _valid_yyyymmdd(r["DateKey"])) == exp["invalid_datekey"] == 5
    assert sum(1 for r in rows if r["ActualUnits"].strip() == "") == exp["missing_actual_units"] == 6
    canonical = {"Team-A", "Team-B", "Team-C"}
    variants = [r["OperatorTeam"] for r in rows if r["OperatorTeam"] not in canonical]
    assert len(variants) == exp["operator_team_variants"] == 120
    for v in variants:
        assert re.search(r"TEAM[-_ ]?([A-C])", v.upper()), v


def test_quality_inspection_issues(kit: Path, expected: dict) -> None:
    rows = plant(kit, "FactQualityInspection")
    exp = expected["seeded_issues"]["FactQualityInspection"]
    over = [r for r in rows if r["DefectCount"] and int(r["DefectCount"]) > int(r["InspectedUnits"])]
    assert len(over) == exp["defects_exceed_inspected"] == 7
    assert sum(1 for r in rows if r["DefectTypeKey"].strip() == "") == exp["missing_defect_type"] == 12
    variants = [r["Severity"] for r in rows if r["Severity"] not in {"Low", "Medium", "High"}]
    assert len(variants) == exp["severity_variants"] == 150
    assert {v.strip().title() for v in variants} <= {"Low", "Medium", "High"}


def test_maintenance_issues(kit: Path, expected: dict) -> None:
    rows = plant(kit, "FactMaintenanceEvent")
    exp = expected["seeded_issues"]["FactMaintenanceEvent"]
    assert sum(1 for r in rows if r["RootCause"].strip() == "") == exp["blank_root_cause"] == 9
    variants = [r["PreventiveFlag"] for r in rows if r["PreventiveFlag"] not in {"0", "1"}]
    assert len(variants) == exp["preventive_flag_variants"] == 60
    assert {v.strip().upper() for v in variants} <= {"Y", "N", "YES", "NO", "TRUE", "FALSE"}


def test_customer_order_issues(kit: Path, expected: dict) -> None:
    rows = plant(kit, "FactCustomerOrder")
    exp = expected["seeded_issues"]["FactCustomerOrder"]
    dmy = re.compile(r"^\d{2}/\d{2}/\d{4}$")
    assert sum(1 for r in rows if dmy.match(r["RequiredShipDate"])) == exp["dmy_required_ship_date"] == 300
    open_orders = [r for r in rows if r["ActualShipDate"].strip() == ""]
    assert len(open_orders) == exp["open_orders"] == 40
    assert all(r["ShippedUnits"] == "0" for r in open_orders)
    assert sum(1 for r in rows if r["CustomerKey"] == "999") == exp["orphan_customer"] == 6
    assert sum(1 for r in rows if "," in r["Revenue"]) == exp["revenue_with_thousands_separator"] == 50


def test_product_dimension_issues(kit: Path, expected: dict) -> None:
    rows = plant(kit, "DimProduct")
    exp = expected["seeded_issues"]["DimProduct"]
    assert len(rows) == 21
    assert len(rows) - len({r["ProductKey"] for r in rows}) == exp["duplicate_keys"] == 1
    assert sum(1 for r in rows if r["ProductName"] != r["ProductName"].strip()) == exp["untrimmed_names"] == 4
    assert sum(1 for r in rows if r["UnitPrice"].startswith("$")) == exp["currency_formatted_price"] == 5
    assert sum(1 for r in rows if r["Category"] != r["Category"].title()) == exp["lowercase_category"] == 2


def test_customer_dimension_issues(kit: Path, expected: dict) -> None:
    rows = plant(kit, "DimCustomer")
    exp = expected["seeded_issues"]["DimCustomer"]
    assert len(rows) - len({r["CustomerKey"] for r in rows}) == exp["duplicate_keys"] == 1
    canonical = {"Singapore", "Malaysia", "India", "Australia"}
    assert sum(1 for r in rows if r["Country"] not in canonical) == exp["country_variants"] == 8


def test_plant_dimension_issues(kit: Path, expected: dict) -> None:
    rows = plant(kit, "DimPlant")
    exp = expected["seeded_issues"]["DimPlant"]
    assert sum(1 for r in rows if r["PlantCode"] != r["PlantCode"].strip().upper()) == exp["messy_plant_code"] == 2


def test_expected_silver_counts_are_consistent(kit: Path, expected: dict) -> None:
    bronze = expected["bronze"]
    silver = expected["silver"]
    for name in build.PLANT_FILES:
        assert bronze[name] == len(plant(kit, name)), name
    pr = expected["seeded_issues"]["FactProductionRun"]
    pr_rejects = pr["negative_scrap"] + pr["invalid_datekey"] + pr["missing_actual_units"]
    assert silver["fact_production_run"] == bronze["FactProductionRun"] - pr["exact_duplicates"] - pr_rejects
    qi = expected["seeded_issues"]["FactQualityInspection"]
    assert silver["fact_quality_inspection"] == bronze["FactQualityInspection"] - qi["defects_exceed_inspected"]
    assert silver["fact_maintenance_event"] == bronze["FactMaintenanceEvent"]
    assert silver["fact_customer_order"] == bronze["FactCustomerOrder"]
    assert silver["dim_product"] == 20
    assert silver["dim_customer"] == 35
    assert silver["dim_plant"] == 4
    assert silver["dq_rejects"] == pr_rejects + qi["defects_exceed_inspected"]


def test_build_is_deterministic(tmp_path: Path, kit: Path) -> None:
    again = tmp_path / "again"
    build.build_kit(source_dir=ROOT / "tools" / "source", out_dir=again, bills_src=None)

    def digest(base: Path) -> dict[str, str]:
        return {
            str(p.relative_to(base)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(base.rglob("*"))
            if p.is_file()
        }

    assert digest(again) == digest(kit)


def test_ground_truth_covers_the_curated_bills(kit: Path, expected: dict) -> None:
    gt = _rows(kit / "data" / "landing" / "reference" / "utility_bills_ground_truth.csv")
    assert len(gt) == expected["utility_bills"]["documents"] == 48
    assert {r["billing_period"] for r in gt} == {f"2026{m:02d}" for m in range(1, 7)}
    assert {r["plant_code"] for r in gt} == {"SG-01", "MY-01", "IN-01", "AU-01"}
    assert expected["utility_bills"]["scanned"] == 13


def test_clean_build_ships_the_lab6_catchup_extraction(kit: Path) -> None:
    ref = kit / "data" / "landing" / "reference"
    assert sorted(p.name for p in ref.glob("*.csv")) == [
        "utility_bills_extracted_catchup.csv",
        "utility_bills_ground_truth.csv",
    ]
    catchup = _rows(ref / "utility_bills_extracted_catchup.csv")
    assert len(catchup) == 48
    # Lab 6 Silver reads these columns from Bronze, so the catch-up file must carry every one
    silver_inputs = {
        "document_id",
        "site_reference",
        "utility_type",
        "provider_name",
        "account_number",
        "invoice_number",
        "meter_number",
        "billing_period_start",
        "billing_period_end",
        "previous_reading",
        "current_reading",
        "consumption",
        "consumption_unit",
        "peak_demand_kw",
        "currency_code",
        "subtotal_amount",
        "tax_amount",
        "total_amount_due",
        "grid_emission_factor",
        "estimated_emissions_kg",
        "_source_file",
    }
    assert silver_inputs <= set(catchup[0])
    assert all(
        r["_source_file"].startswith("Files/landing/utility_bills/") and "/2026" not in r["_source_file"]
        for r in catchup
    )
