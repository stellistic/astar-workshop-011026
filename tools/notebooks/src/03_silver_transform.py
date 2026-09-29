# %% [markdown]
# # Lab 3 · Silver — clean, type and conform the plant facts
#
# Bronze holds the data exactly as it arrived, dirt included. **Silver decides what is true.** In this notebook you
# turn the four Bronze fact tables and five simple dimensions into typed, de-duplicated, conformed **`silver.*`**
# tables. Rows that can't be trusted are **quarantined** in `silver.dq_rejects` with a reason, rather than silently
# dropped.
#
# | Problem found in Bronze | Example | Silver's decision |
# |---|---|---|
# | Exact duplicate rows (a re-sent extract) | the same run twice | keep one |
# | Impossible dates | `DateKey = 20250230` | quarantine: `invalid_date` |
# | Missing measures | blank `ActualUnits` | quarantine: `missing_actual_units` |
# | Negative quantities | `ScrapUnits = -12` | quarantine: `negative_scrap` |
# | Defects > units inspected | 180 defects in 150 units | quarantine: `defects_exceed_inspected` |
# | Free-text spelling | `team-a`, `TEAM-A `, `Team A` | conform to `Team-A` |
# | Mixed case / padding | `low`, ` Low`, `MEDIUM ` | conform to `Low`, `Medium` |
# | Mixed flag styles | `1`, `Y`, `yes`, `TRUE` | conform to `1` / `0` |
# | Mixed date formats | `2024-03-05` and `05/03/2024` | parse both |
# | Formatted numbers | `"198,801"` | strip separators, cast |
# | Blank codes | empty `DefectTypeKey`, `RootCause` | `-1` (unknown) and `Unknown` |
#
# > **Before you run:** Lab 2 must be complete (13 `bronze.*` tables), and **`lh_kcorp_plant`** must be the
# > default Lakehouse in the Explorer.

# %% [markdown]
# ## 0 · Setup: small helper functions
#
# Bronze columns are all strings, so every column needs converting. Plain `CAST` fails on bad input (or, on newer
# runtimes, stops the whole job). These helpers use Spark's **`try_`** functions instead, which return `null` for a
# value that can't be converted. The rules that follow then decide what a `null` means.

# %%
from functools import reduce

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

spark.sql("CREATE SCHEMA IF NOT EXISTS silver")

LINEAGE = ["_source_file", "_ingested_at"]


def to_int(col: str):
    return F.expr(f"try_cast(trim(`{col}`) AS INT)")


def to_decimal(col: str, scale: int = 2):
    # strips thousands separators and currency symbols first: "198,801" -> 198801.00
    return F.expr(f"try_cast(regexp_replace(trim(`{col}`), '[,$]', '') AS DECIMAL(18,{scale}))")


def date_from_key(col: str):
    # 20240315 -> 2024-03-15 ; 20250230 -> null (there is no 30 February)
    return F.expr(f"to_date(try_to_timestamp(trim(`{col}`), 'yyyyMMdd'))")


def parse_date(col: str):
    # accepts both 2024-03-05 and 05/03/2024 (day first)
    return F.expr(
        f"coalesce(to_date(try_to_timestamp(trim(`{col}`), 'yyyy-MM-dd')), "
        f"to_date(try_to_timestamp(trim(`{col}`), 'dd/MM/yyyy')))"
    )


def blank_to(col: str, default: str):
    return F.coalesce(F.when(F.trim(F.col(col)) != "", F.trim(F.col(col))), F.lit(default))


def save(df: DataFrame, table: str) -> int:
    df.write.mode("overwrite").option("overwriteSchema", True).saveAsTable(table)
    return spark.table(table).count()


rejected: list[DataFrame] = []  # quarantined rows from every fact; written once at the end


def split_and_quarantine(checked: DataFrame, source_table: str, key_col: str) -> DataFrame:
    """Rows with a _dq_reason go to quarantine; the rest are returned without the helper column."""
    bad = checked.filter(F.col("_dq_reason").isNotNull())
    rejected.append(
        bad.select(
            F.lit(source_table).alias("SourceTable"),
            F.col(key_col).cast("string").alias("RecordKey"),
            F.col("_dq_reason").alias("DqReason"),
            F.to_json(F.struct(*[c for c in bad.columns if c != "_dq_reason"])).alias("RecordJson"),
            F.current_timestamp().alias("RejectedAt"),
        )
    )
    return checked.filter(F.col("_dq_reason").isNull()).drop("_dq_reason")


print("✅ helpers ready")

# %% [markdown]
# ## 1 · `fact_production_run`: duplicates, bad dates, missing and negative quantities
#
# Four steps, which you'll repeat for every fact:
#
# 1. **De-duplicate** exact copies. Compare the counts before and after.
# 2. **Type** every column with the helpers.
# 3. **Conform** free text. The regular expression pulls the team letter out of any spelling
#    (`team_b`, ` Team-B`, `TEAM B`…) and rebuilds it as `Team-B`.
# 4. **Check** each row and give it a `_dq_reason` if it fails. The first failing rule wins.

# %%
runs_bronze = spark.table("bronze.fact_production_run").drop(*LINEAGE)
runs_deduped = runs_bronze.dropDuplicates()
print(f"bronze rows: {runs_bronze.count():,}  ->  after removing exact duplicates: {runs_deduped.count():,}")

runs_typed = runs_deduped.select(
    to_int("ProductionRunID").alias("ProductionRunID"),
    to_int("DateKey").alias("DateKey"),
    date_from_key("DateKey").alias("ProductionDate"),
    to_int("PlantKey").alias("PlantKey"),
    to_int("LineKey").alias("LineKey"),
    to_int("ProductKey").alias("ProductKey"),
    to_int("ShiftKey").alias("ShiftKey"),
    to_int("PlannedUnits").alias("PlannedUnits"),
    to_int("ActualUnits").alias("ActualUnits"),
    to_int("ScrapUnits").alias("ScrapUnits"),
    to_int("ReworkUnits").alias("ReworkUnits"),
    to_int("DowntimeMinutes").alias("DowntimeMinutes"),
    to_int("CycleTimeSeconds").alias("CycleTimeSeconds"),
    F.concat(F.lit("Team-"), F.regexp_extract(F.upper("OperatorTeam"), r"TEAM[-_ ]?([A-C])", 1)).alias("OperatorTeam"),
    F.trim("BatchID").alias("BatchID"),
)

runs_checked = runs_typed.withColumn(
    "_dq_reason",
    F.when(F.col("ProductionDate").isNull(), "invalid_date")
    .when(F.col("ActualUnits").isNull(), "missing_actual_units")
    .when(F.col("ScrapUnits") < 0, "negative_scrap"),
)

runs_silver = split_and_quarantine(runs_checked, "fact_production_run", "ProductionRunID")
print("silver.fact_production_run:", save(runs_silver, "silver.fact_production_run"), "rows")
display(spark.table("silver.fact_production_run").groupBy("OperatorTeam").count().orderBy("OperatorTeam"))

# %% [markdown]
# ## 2 · `fact_quality_inspection`: impossible defect counts, blank codes, messy severity
#
# - A blank `DefectTypeKey` becomes **`-1`**, the key of an *Unknown* member Gold will add to the defect dimension.
#   The inspection is still real, so it stays; only its defect code is unknown.
# - More defects than units inspected is physically impossible, so the row goes to **quarantine**.

# %%
insp_typed = spark.table("bronze.fact_quality_inspection").drop(*LINEAGE).select(
    to_int("QualityInspectionID").alias("QualityInspectionID"),
    to_int("DateKey").alias("DateKey"),
    date_from_key("DateKey").alias("InspectionDate"),
    to_int("PlantKey").alias("PlantKey"),
    to_int("LineKey").alias("LineKey"),
    to_int("ProductKey").alias("ProductKey"),
    F.coalesce(to_int("DefectTypeKey"), F.lit(-1)).alias("DefectTypeKey"),
    to_int("InspectedUnits").alias("InspectedUnits"),
    to_int("DefectCount").alias("DefectCount"),
    F.initcap(F.trim("Severity")).alias("Severity"),
    to_int("ReworkFlag").alias("ReworkFlag"),
    F.trim("InspectionMethod").alias("InspectionMethod"),
    F.trim("BatchID").alias("BatchID"),
)

insp_checked = insp_typed.withColumn(
    "_dq_reason",
    F.when(F.col("InspectionDate").isNull(), "invalid_date")
    .when(F.col("DefectCount") > F.col("InspectedUnits"), "defects_exceed_inspected"),
)

insp_silver = split_and_quarantine(insp_checked, "fact_quality_inspection", "QualityInspectionID")
print("silver.fact_quality_inspection:", save(insp_silver, "silver.fact_quality_inspection"), "rows")
display(spark.table("silver.fact_quality_inspection").groupBy("Severity").count())

# %% [markdown]
# ## 3 · `fact_maintenance_event`: blank root causes and six ways to say "yes"
#
# `PreventiveFlag` arrived as `1`, `0`, `Y`, `N`, `yes`, `TRUE`, `false`… Silver keeps just `1` (preventive) and
# `0` (corrective). A blank `RootCause` becomes `Unknown`, so a report can still count it.

# %%
maint_typed = spark.table("bronze.fact_maintenance_event").drop(*LINEAGE).select(
    to_int("MaintenanceEventID").alias("MaintenanceEventID"),
    to_int("DateKey").alias("DateKey"),
    date_from_key("DateKey").alias("EventDate"),
    to_int("PlantKey").alias("PlantKey"),
    to_int("LineKey").alias("LineKey"),
    to_int("AssetKey").alias("AssetKey"),
    F.trim("EventType").alias("EventType"),
    to_int("DowntimeMinutes").alias("DowntimeMinutes"),
    blank_to("RootCause", "Unknown").alias("RootCause"),
    to_decimal("MaintenanceCost", 2).alias("MaintenanceCost"),
    F.when(F.upper(F.trim("PreventiveFlag")).isin("1", "Y", "YES", "TRUE"), 1).otherwise(0).alias("PreventiveFlag"),
    F.trim("TechnicianTeam").alias("TechnicianTeam"),
)

maint_checked = maint_typed.withColumn("_dq_reason", F.when(F.col("EventDate").isNull(), "invalid_date"))
maint_silver = split_and_quarantine(maint_checked, "fact_maintenance_event", "MaintenanceEventID")
print("silver.fact_maintenance_event:", save(maint_silver, "silver.fact_maintenance_event"), "rows")
display(spark.table("silver.fact_maintenance_event").groupBy("PreventiveFlag", "RootCause").count().orderBy("RootCause"))

# %% [markdown]
# ## 4 · `fact_customer_order`: two date formats, formatted revenue, open orders
#
# - Some rows came from a regional system that writes dates day-first (`05/03/2024`). `parse_date` accepts both.
# - `Revenue` sometimes has thousands separators (`"198,801"`). `to_decimal` strips them.
# - A blank `ActualShipDate` means the order **hasn't shipped yet**. That isn't an error, so it stays, marked `Open`.
# - A few orders reference customer `999`, who doesn't exist. Silver keeps them; Gold maps them to *Unknown customer*.

# %%
orders_typed = spark.table("bronze.fact_customer_order").drop(*LINEAGE).select(
    to_int("OrderID").alias("OrderID"),
    to_int("DateKey").alias("DateKey"),
    date_from_key("DateKey").alias("OrderDate"),
    to_int("CustomerKey").alias("CustomerKey"),
    to_int("ProductKey").alias("ProductKey"),
    to_int("PlantKey").alias("PlantKey"),
    to_int("OrderedUnits").alias("OrderedUnits"),
    to_int("ShippedUnits").alias("ShippedUnits"),
    to_int("LateShipmentFlag").alias("LateShipmentFlag"),
    to_decimal("Revenue", 2).alias("Revenue"),
    parse_date("RequiredShipDate").alias("RequiredShipDate"),
    parse_date("ActualShipDate").alias("ActualShipDate"),
    F.trim("Priority").alias("Priority"),
).withColumn("OrderStatus", F.when(F.col("ActualShipDate").isNull(), "Open").otherwise("Shipped"))

orders_checked = orders_typed.withColumn("_dq_reason", F.when(F.col("OrderDate").isNull(), "invalid_date"))
orders_silver = split_and_quarantine(orders_checked, "fact_customer_order", "OrderID")
print("silver.fact_customer_order:", save(orders_silver, "silver.fact_customer_order"), "rows")
display(spark.table("silver.fact_customer_order").groupBy("OrderStatus").agg(F.count("*").alias("orders"), F.sum("Revenue").alias("revenue")))

# %% [markdown]
# ## 5 · Five clean dimensions: type them and move on
#
# `DimDate`, `DimShift`, `DimLine`, `DimAsset` and `DimDefectType` came through clean, so Silver only gives each
# column a proper type. **Product, customer and plant are *not* here**: you clean those with a no-code
# **Dataflow Gen2** in Lab 4.

# %%
SIMPLE_DIMS = {
    "dim_date": {"DateKey": "int", "Date": "date", "Day": "int", "Week": "int", "Month": "int", "MonthName": "string",
                 "Quarter": "int", "FiscalYear": "int", "IsMonthEnd": "int"},
    "dim_shift": {"ShiftKey": "int", "ShiftName": "string", "StartTime": "string", "EndTime": "string", "IsNightShift": "int"},
    "dim_line": {"LineKey": "int", "PlantKey": "int", "LineCode": "string", "LineName": "string", "ProcessType": "string",
                 "CapacityPerHour": "int"},
    "dim_asset": {"AssetKey": "int", "PlantKey": "int", "LineKey": "int", "AssetCode": "string", "AssetName": "string",
                  "AssetType": "string", "InstallDate": "date", "Criticality": "string"},
    "dim_defect_type": {"DefectTypeKey": "int", "DefectCode": "string", "DefectName": "string", "DefectCategory": "string",
                        "SeverityBand": "string"},
}

for table, columns in SIMPLE_DIMS.items():
    df = spark.table(f"bronze.{table}").select(
        *[F.expr(f"try_cast(trim(`{c}`) AS {t.upper()})").alias(c) for c, t in columns.items()]
    )
    print(f"silver.{table:22s}", save(df, f"silver.{table}"), "rows")

# %% [markdown]
# ## 6 · Write the quarantine table
#
# Every row that failed a rule, from every fact, goes into one table with its reason and the full original record
# as JSON. A data steward can review it, fix the source and re-run; nothing is lost.

# %%
dq_rejects = reduce(DataFrame.unionByName, rejected)
print("silver.dq_rejects:", save(dq_rejects, "silver.dq_rejects"), "rows")
display(spark.table("silver.dq_rejects").groupBy("SourceTable", "DqReason").count().orderBy("SourceTable", "DqReason"))

# %% [markdown]
# ## 7 · Verify
#
# The data is identical for everyone, so these numbers are exact. A ❌ usually means Lab 2 didn't finish, or this
# notebook was run twice with one cell skipped. **Run all** again from the top; every write is an overwrite, so
# re-running is safe.

# %%
EXPECTED_SILVER = {
    "fact_production_run": 3629, "fact_quality_inspection": 2729, "fact_maintenance_event": 270,
    "fact_customer_order": 4560, "dim_date": 912, "dim_shift": 3, "dim_line": 8, "dim_asset": 40,
    "dim_defect_type": 12, "dq_rejects": 26,
}
EXPECTED_REJECTS = {"invalid_date": 5, "missing_actual_units": 6, "negative_scrap": 8, "defects_exceed_inspected": 7}

problems = []
for table, expected in EXPECTED_SILVER.items():
    actual = spark.table(f"silver.{table}").count()
    print(f"{'✅' if actual == expected else '❌'} silver.{table:26s} {actual:>6,} (expected {expected:,})")
    if actual != expected:
        problems.append(table)

by_reason = {r["DqReason"]: r["count"] for r in spark.table("silver.dq_rejects").groupBy("DqReason").count().collect()}
print("\nquarantined by reason:", by_reason)
assert by_reason == EXPECTED_REJECTS, f"Unexpected quarantine breakdown: {by_reason}"
assert not problems, f"Row counts differ for: {problems}"
print("\n🎉 Silver facts complete. Next: Lab 4, where you clean the product, customer and plant dimensions with Dataflow Gen2.")

# %% [markdown]
# ## ⭐ Optional · Delta keeps history (time travel)
#
# Every write to a Delta table is a new **version**. You can list the versions and query an older one, which is
# handy when a bad load needs rolling back. Run this notebook twice, then try it.

# %%
display(spark.sql("DESCRIBE HISTORY silver.fact_production_run").select("version", "timestamp", "operation"))
display(spark.sql("SELECT COUNT(*) AS rows_at_version_0 FROM silver.fact_production_run VERSION AS OF 0"))
