# %% [markdown]
# # Lab 7 · Catch-up: finish the semantic model's relationships and measures in code
#
# **Use this only if you are behind, or Copilot didn't do what you asked.** It connects to your semantic model
# **`sm_kcorp_plant`** and adds any of the lab's **20 relationships** and **17 measures** that are *missing*.
# Anything you already built is left untouched, so it is safe to run at any point, and more than once.
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
# ## 2 · Add whatever is missing

# %%
added_rel, added_meas = [], []
with connect_semantic_model(dataset=MODEL, readonly=False) as tom:
    existing_rel = {(r.FromTable.Name, r.FromColumn.Name, r.ToTable.Name, r.ToColumn.Name) for r in tom.model.Relationships}
    for ft, fc, tt, tc in RELATIONSHIPS:
        if (ft, fc, tt, tc) in existing_rel:
            continue
        if (tt, tc, ft, fc) in existing_rel:
            print(f"⚠️ {ft}[{fc}] ↔ {tt}[{tc}] exists but points the wrong way; delete it in the model view, then re-run")
            continue
        tom.add_relationship(from_table=ft, from_column=fc, to_table=tt, to_column=tc,
                             from_cardinality="Many", to_cardinality="One", cross_filtering_behavior="OneDirection")
        added_rel.append(f"{ft}[{fc}] → {tt}[{tc}]")

    existing_meas = {m.Name for m in tom.all_measures()}
    for table, name, dax, fmt in MEASURES:
        if name not in existing_meas:
            tom.add_measure(table_name=table, measure_name=name, expression=dax, format_string=fmt)
            added_meas.append(name)

print(f"added {len(added_rel)} relationships:", *added_rel, sep="\n  ")
print(f"added {len(added_meas)} measures:", *added_meas, sep="\n  ")

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

row = result.iloc[0]
assert int(row.iloc[0]) == 1032704, "Actual Units should be 1,032,704"
assert round(float(row.iloc[1]), 4) == 0.0313, "Scrap Rate % should be 3.13%"
assert round(float(row.iloc[2]), 4) == 0.0241, "Defect Rate % should be 2.41%"
print("🎉 Semantic model complete: relationships, measures and numbers all check out.")
