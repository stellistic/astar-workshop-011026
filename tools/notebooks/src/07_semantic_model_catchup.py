# %% [markdown]
# # Lab 7 · Catch-up: finish the semantic model's relationships and measures in code
#
# **Use this only if you are behind, or Copilot didn't do what you asked.** It connects to your semantic model
# **`sm_kcorp_plant`** and makes its **20 relationships** and **17 measures** match the lab exactly:
# - adds any relationship or measure that is **missing**,
# - re-activates a relationship that is **inactive**, and sets it to many-to-one, single direction,
# - resets a measure whose **DAX differs** from the lab's (for example, one Copilot rewrote).
#
# Everything else is left alone, so it is safe to run at any point, and more than once.
#
# It uses **Semantic Link Labs** (`sempy_labs`), an open-source library for managing Power BI / Fabric semantic
# models from a notebook. It edits the same Tabular Object Model (TOM) the web model editor does.
#
# > **Before you run:** create the model in the UI first (Lab 7, part A: *New semantic model* on the SQL analytics
# > endpoint, with the 13 gold tables). The model must be named `sm_kcorp_plant` and be in this workspace.

# %%
%pip install -q semantic-link-labs

# %%
import sempy.fabric as fabric
import sempy_labs as labs
from sempy_labs.tom import connect_semantic_model

MODEL = "sm_kcorp_plant"

TABLES = ["dim_date", "dim_plant", "dim_line", "dim_product", "dim_shift", "dim_customer", "dim_defect_type",
          "dim_asset", "fact_production_run", "fact_quality_inspection", "fact_maintenance_event",
          "fact_customer_order", "fact_utility_bill"]

# (fact table, fact column, dimension table, dimension column): every one is many-to-one, single direction
RELATIONSHIPS = [
    ("fact_production_run", "DateKey", "dim_date", "DateKey"),
    ("fact_production_run", "PlantKey", "dim_plant", "PlantKey"),
    ("fact_production_run", "LineKey", "dim_line", "LineKey"),
    ("fact_production_run", "ProductKey", "dim_product", "ProductKey"),
    ("fact_production_run", "ShiftKey", "dim_shift", "ShiftKey"),
    ("fact_quality_inspection", "DateKey", "dim_date", "DateKey"),
    ("fact_quality_inspection", "PlantKey", "dim_plant", "PlantKey"),
    ("fact_quality_inspection", "LineKey", "dim_line", "LineKey"),
    ("fact_quality_inspection", "ProductKey", "dim_product", "ProductKey"),
    ("fact_quality_inspection", "DefectTypeKey", "dim_defect_type", "DefectTypeKey"),
    ("fact_maintenance_event", "DateKey", "dim_date", "DateKey"),
    ("fact_maintenance_event", "PlantKey", "dim_plant", "PlantKey"),
    ("fact_maintenance_event", "LineKey", "dim_line", "LineKey"),
    ("fact_maintenance_event", "AssetKey", "dim_asset", "AssetKey"),
    ("fact_customer_order", "DateKey", "dim_date", "DateKey"),
    ("fact_customer_order", "PlantKey", "dim_plant", "PlantKey"),
    ("fact_customer_order", "ProductKey", "dim_product", "ProductKey"),
    ("fact_customer_order", "CustomerKey", "dim_customer", "CustomerKey"),
    ("fact_utility_bill", "DateKey", "dim_date", "DateKey"),
    ("fact_utility_bill", "PlantKey", "dim_plant", "PlantKey"),
]

# (home table, measure name, DAX, format string): identical to the table in the Lab 7 guide
MEASURES = [
    ("fact_production_run", "Planned Units", "SUM ( 'fact_production_run'[PlannedUnits] )", "#,0"),
    ("fact_production_run", "Actual Units", "SUM ( 'fact_production_run'[ActualUnits] )", "#,0"),
    ("fact_production_run", "Scrap Units", "SUM ( 'fact_production_run'[ScrapUnits] )", "#,0"),
    ("fact_production_run", "Scrap Rate %", "DIVIDE ( [Scrap Units], [Actual Units] + [Scrap Units] )", "0.00%"),
    ("fact_production_run", "Production Attainment %", "DIVIDE ( [Actual Units], [Planned Units] )", "0.0%"),
    ("fact_production_run", "Downtime Minutes", "SUM ( 'fact_production_run'[DowntimeMinutes] )", "#,0"),
    ("fact_quality_inspection", "Inspected Units", "SUM ( 'fact_quality_inspection'[InspectedUnits] )", "#,0"),
    ("fact_quality_inspection", "Defect Count", "SUM ( 'fact_quality_inspection'[DefectCount] )", "#,0"),
    ("fact_quality_inspection", "Defect Rate %", "DIVIDE ( [Defect Count], [Inspected Units] )", "0.00%"),
    ("fact_maintenance_event", "Maintenance Events", "COUNTROWS ( 'fact_maintenance_event' )", "#,0"),
    ("fact_maintenance_event", "Preventive Maintenance %",
     "DIVIDE ( CALCULATE ( [Maintenance Events], 'fact_maintenance_event'[PreventiveFlag] = 1 ), [Maintenance Events] )",
     "0.0%"),
    ("fact_customer_order", "Orders", "COUNTROWS ( 'fact_customer_order' )", "#,0"),
    ("fact_customer_order", "Total Revenue", "SUM ( 'fact_customer_order'[Revenue] )", "#,0"),
    ("fact_customer_order", "Late Order %", "DIVIDE ( SUM ( 'fact_customer_order'[LateShipmentFlag] ), [Orders] )", "0.0%"),
    ("fact_utility_bill", "Electricity kWh", "SUM ( 'fact_utility_bill'[ConsumptionKwh] )", "#,0"),
    ("fact_utility_bill", "Utility Cost USD", "SUM ( 'fact_utility_bill'[TotalAmountUsd] )", "#,0"),
    ("fact_utility_bill", "Energy per Unit kWh",
     "VAR BilledMonths = FILTER ( VALUES ( 'dim_date'[YearMonth] ), CALCULATE ( COUNTROWS ( 'fact_utility_bill' ) ) > 0 )\n"
     "RETURN DIVIDE ( [Electricity kWh], CALCULATE ( [Actual Units], BilledMonths ) )",
     "#,0.00"),
]

# %% [markdown]
# ## 1 · Check the model has all 13 gold tables

# %%
model_tables = set(fabric.list_tables(MODEL)["Name"])
missing_tables = [t for t in TABLES if t not in model_tables]
assert not missing_tables, (
    f"The model is missing tables {missing_tables}. Open sm_kcorp_plant → Edit tables and tick them "
    "(Lab 7, part A), then run this notebook again."
)
print(f"✅ {MODEL} has all {len(TABLES)} tables")

# %% [markdown]
# ## 2 · Add what's missing, fix what's wrong

# %%
import re

import Microsoft.AnalysisServices.Tabular as TOM  # available once Semantic Link has loaded .NET


def same_dax(a: str, b: str) -> bool:
    return re.sub(r"\s+", "", a or "") == re.sub(r"\s+", "", b or "")


changes = []
with connect_semantic_model(dataset=MODEL, readonly=False) as tom:
    existing = {(r.FromTable.Name, r.FromColumn.Name, r.ToTable.Name, r.ToColumn.Name): r for r in tom.model.Relationships}
    for ft, fc, tt, tc in RELATIONSHIPS:
        rel = existing.get((ft, fc, tt, tc))
        if rel is None and (tt, tc, ft, fc) in existing:
            print(f"⚠️ {ft}[{fc}] ↔ {tt}[{tc}] points the wrong way; delete it in Manage relationships, then re-run")
            continue
        if rel is None:
            tom.add_relationship(from_table=ft, from_column=fc, to_table=tt, to_column=tc,
                                 from_cardinality="Many", to_cardinality="One", cross_filtering_behavior="OneDirection")
            changes.append(f"added relationship {ft}[{fc}] → {tt}[{tc}]")
            continue
        wrong = (not rel.IsActive or rel.FromCardinality != TOM.RelationshipEndCardinality.Many
                 or rel.ToCardinality != TOM.RelationshipEndCardinality.One
                 or rel.CrossFilteringBehavior != TOM.CrossFilteringBehavior.OneDirection)
        if wrong:
            rel.IsActive = True
            rel.FromCardinality = TOM.RelationshipEndCardinality.Many
            rel.ToCardinality = TOM.RelationshipEndCardinality.One
            rel.CrossFilteringBehavior = TOM.CrossFilteringBehavior.OneDirection
            changes.append(f"fixed relationship {ft}[{fc}] → {tt}[{tc}] (now active, *:1, single)")

    measures = {m.Name: m for m in tom.all_measures()}
    for table, name, dax, fmt in MEASURES:
        m = measures.get(name)
        if m is None:
            tom.add_measure(table_name=table, measure_name=name, expression=dax, format_string=fmt)
            changes.append(f"added measure [{name}]")
        elif not same_dax(m.Expression, dax) or m.FormatString != fmt:
            m.Expression, m.FormatString = dax, fmt
            changes.append(f"reset measure [{name}] to the lab's DAX and format")

print(f"{len(changes)} change(s):", *changes, sep="\n  ")

# %% [markdown]
# ## 3 · Refresh and sanity-check the numbers
#
# For a Direct Lake model, a refresh only reloads the metadata (it's quick; no data is copied). The DAX query
# then evaluates the headline measures. They must match what your Gold notebook printed.

# %%
labs.refresh_semantic_model(dataset=MODEL)

result = fabric.evaluate_dax(MODEL, """
EVALUATE ROW (
    "Actual Units", [Actual Units],
    "Scrap Rate %", [Scrap Rate %],
    "Defect Rate %", [Defect Rate %],
    "Total Revenue", [Total Revenue],
    "Late Order %", [Late Order %],
    "Preventive Maintenance %", [Preventive Maintenance %],
    "Electricity kWh", [Electricity kWh],
    "Energy per Unit kWh", [Energy per Unit kWh]
)
""")
display(result)

row = result.iloc[0].tolist()
EXPECTED = [  # (name, expected, tolerance); the last two come from AI-read PDFs, so allow a little drift
    ("Actual Units", 1032704, 0), ("Scrap Rate %", 0.0313, 0.00005), ("Defect Rate %", 0.0241, 0.00005),
    ("Total Revenue", 1106432678, 1), ("Late Order %", 0.0537, 0.00005), ("Preventive Maintenance %", 0.6704, 0.00005),
    ("Electricity kWh", 3355595, 3355595 * 0.02), ("Energy per Unit kWh", 16.65, 0.35),
]
problems = []
for (name, expected, tol), actual in zip(EXPECTED, row, strict=True):
    ok = actual is not None and abs(float(actual) - expected) <= tol
    print(f"{'✅' if ok else '❌'} {name:26s} {actual} (expected {expected})")
    if not ok:
        problems.append(name)

# Grouping by a dimension exercises the relationships, not just the measures
by_plant = fabric.evaluate_dax(MODEL, """
EVALUATE SUMMARIZECOLUMNS ( 'dim_plant'[PlantCode], "Scrap", ROUND ( [Scrap Rate %], 4 ), "kWh per unit", ROUND ( [Energy per Unit kWh], 2 ) )
ORDER BY 'dim_plant'[PlantCode]
""")
display(by_plant)
scrap = dict(zip(by_plant.iloc[:, 0], by_plant.iloc[:, 1]))
expected_scrap = {"AU-01": 0.0294, "IN-01": 0.0292, "MY-01": 0.0379, "SG-01": 0.0291}
if {k: round(float(v), 4) for k, v in scrap.items()} != expected_scrap:
    problems.append("Scrap Rate % by plant (a relationship to dim_plant is missing or inactive)")
    print("❌ Scrap Rate % by plant:", scrap, "expected", expected_scrap)
else:
    print("✅ Scrap Rate % by plant matches, so the plant relationships work")

assert not problems, f"Still not right: {problems}. Check the ⚠️ messages above, fix in the model view, and re-run."
print("🎉 Semantic model complete: relationships, measures and numbers all check out.")
