# %% [markdown]
# # Lab 5 · Gold — a star schema the business can use
#
# Silver is *clean*; Gold is *useful*. You reshape the Silver tables into a **star schema**: fact tables of events
# (runs, inspections, maintenance, orders) surrounded by dimension tables that describe them (date, plant, line,
# product, shift, customer, defect type, asset). Power BI, Copilot and SQL users all work best with this shape, and
# the Lab 7 semantic model sits directly on top of it.
#
# ```
#                 dim_date      dim_shift
#                     \          /
#   dim_customer — fact_customer_order     fact_production_run — dim_line
#                     \                      /
#                      dim_plant ——— dim_product
#                     /                      \
#   dim_asset — fact_maintenance_event    fact_quality_inspection — dim_defect_type
# ```
#
# You'll also add:
# - **Unknown members** (key `-1`), so a fact row with a missing or orphaned key still joins to *something* and is
#   never silently dropped from a report.
# - **`gold.agg_plant_month`**, a small pre-aggregated KPI table (one row per plant per month). It's quick to query
#   and makes a good first table to hand to Copilot.
#
# > **Before you run:** Lab 3 **and** Lab 4 must be complete. The first cell checks for you.

# %% [markdown]
# ## 0 · Pre-flight: are all the Silver tables there?

# %%
from pyspark.sql import functions as F

spark.sql("CREATE SCHEMA IF NOT EXISTS gold")

REQUIRED = ["fact_production_run", "fact_quality_inspection", "fact_maintenance_event", "fact_customer_order",
            "dim_date", "dim_shift", "dim_line", "dim_asset", "dim_defect_type",
            "dim_product", "dim_customer", "dim_plant"]
missing = [t for t in REQUIRED if not spark.catalog.tableExists(f"silver.{t}")]
if missing:
    raise RuntimeError(
        f"Missing Silver tables: {missing}. dim_product / dim_customer / dim_plant come from Lab 4 "
        "(the Dataflow Gen2, or the 04_silver_dims_catchup notebook). The rest come from Lab 3."
    )
print("✅ all 12 Silver tables found")


def save(df, table):
    df.write.mode("overwrite").option("overwriteSchema", True).saveAsTable(table)
    return spark.table(table).count()


# %% [markdown]
# ## 1 · Dimensions
#
# Mostly a straight copy of Silver, with a few extras that make reports friendlier:
# - `dim_date` gets `YearMonth` (e.g. `2026-03`) and `MonthStart`, which make monthly visuals easy.
# - `dim_line` gets its plant code, so a line reads `SG-01 · Production Line 1`.
# - `dim_product` gets unit margin and margin %.
# - `dim_customer` and `dim_defect_type` get their **Unknown** (`-1`) rows.

# %%
dim_date = spark.table("silver.dim_date").select(
    "DateKey", "Date", "Day", "Week", "Month", "MonthName", "Quarter",
    F.col("FiscalYear").alias("Year"), "IsMonthEnd",
    F.date_format("Date", "yyyy-MM").alias("YearMonth"),
    F.trunc("Date", "month").alias("MonthStart"),
)
print("gold.dim_date:", save(dim_date, "gold.dim_date"))

dim_plant = spark.table("silver.dim_plant").withColumn("PlantKey", F.col("PlantKey").cast("int"))
print("gold.dim_plant:", save(dim_plant, "gold.dim_plant"))

dim_line = (spark.table("silver.dim_line").alias("l")
            .join(spark.table("gold.dim_plant").select("PlantKey", "PlantCode"), "PlantKey", "left")
            .withColumn("LineLabel", F.concat_ws(" · ", "PlantCode", "LineName")))
print("gold.dim_line:", save(dim_line, "gold.dim_line"))

print("gold.dim_asset:", save(spark.table("silver.dim_asset"), "gold.dim_asset"))
print("gold.dim_shift:", save(spark.table("silver.dim_shift"), "gold.dim_shift"))

dim_product = (spark.table("silver.dim_product")
               .withColumn("ProductKey", F.col("ProductKey").cast("int"))
               .withColumn("UnitMargin", F.round(F.col("UnitPrice") - F.col("StandardCost"), 2))
               .withColumn("MarginPct", F.round((F.col("UnitPrice") - F.col("StandardCost")) / F.col("UnitPrice"), 4)))
print("gold.dim_product:", save(dim_product, "gold.dim_product"))

unknown_customer = spark.createDataFrame(
    [(-1, "Unknown customer", "Unknown", "Unknown", "Unknown", "Unknown")],
    "CustomerKey int, CustomerName string, Industry string, Segment string, Region string, Country string",
)
dim_customer = (spark.table("silver.dim_customer").withColumn("CustomerKey", F.col("CustomerKey").cast("int"))
                .unionByName(unknown_customer))
print("gold.dim_customer:", save(dim_customer, "gold.dim_customer"))

unknown_defect = spark.createDataFrame(
    [(-1, "N/A", "Not recorded", "Unknown", "Unknown")],
    "DefectTypeKey int, DefectCode string, DefectName string, DefectCategory string, SeverityBand string",
)
dim_defect_type = spark.table("silver.dim_defect_type").unionByName(unknown_defect)
print("gold.dim_defect_type:", save(dim_defect_type, "gold.dim_defect_type"))

# %% [markdown]
# ## 2 · Facts
#
# Facts keep their keys and measures. Two small additions:
# - `fact_production_run.TotalUnits` = good units plus scrap, the denominator of *scrap rate*.
# - `fact_customer_order.CustomerKey`: any customer that isn't in `dim_customer` (the orphaned `999`) is remapped
#   to `-1`. Without this, those orders would vanish from any visual filtered by customer.

# %%
runs = spark.table("silver.fact_production_run").withColumn("TotalUnits", F.col("ActualUnits") + F.col("ScrapUnits"))
print("gold.fact_production_run:", save(runs, "gold.fact_production_run"))

print("gold.fact_quality_inspection:", save(spark.table("silver.fact_quality_inspection"), "gold.fact_quality_inspection"))
print("gold.fact_maintenance_event:", save(spark.table("silver.fact_maintenance_event"), "gold.fact_maintenance_event"))

known_customers = spark.table("gold.dim_customer").select(F.col("CustomerKey").alias("_known"))
orders = (spark.table("silver.fact_customer_order")
          .join(known_customers, F.col("CustomerKey") == F.col("_known"), "left")
          .withColumn("CustomerKey", F.when(F.col("_known").isNull(), F.lit(-1)).otherwise(F.col("CustomerKey")))
          .drop("_known"))
print("gold.fact_customer_order:", save(orders, "gold.fact_customer_order"))

# %% [markdown]
# ## 3 · `agg_plant_month`: one row per plant per month
#
# This is a classic Gold aggregate. It joins four facts through the date dimension, sums them by plant and month,
# and pre-computes the KPIs managers ask for first.

# %%
months = spark.table("gold.dim_date").select("DateKey", "YearMonth")

prod = (spark.table("gold.fact_production_run").join(months, "DateKey")
        .groupBy("PlantKey", "YearMonth")
        .agg(F.sum("PlannedUnits").alias("PlannedUnits"), F.sum("ActualUnits").alias("ActualUnits"),
             F.sum("ScrapUnits").alias("ScrapUnits"), F.sum("DowntimeMinutes").alias("ProductionDowntimeMinutes")))
qual = (spark.table("gold.fact_quality_inspection").join(months, "DateKey")
        .groupBy("PlantKey", "YearMonth")
        .agg(F.sum("InspectedUnits").alias("InspectedUnits"), F.sum("DefectCount").alias("DefectCount")))
maint = (spark.table("gold.fact_maintenance_event").join(months, "DateKey")
         .groupBy("PlantKey", "YearMonth")
         .agg(F.count("*").alias("MaintenanceEvents"), F.sum("MaintenanceCost").alias("MaintenanceCost")))
sales = (spark.table("gold.fact_customer_order").join(months, "DateKey")
         .groupBy("PlantKey", "YearMonth")
         .agg(F.count("*").alias("Orders"), F.sum("LateShipmentFlag").alias("LateOrders"), F.sum("Revenue").alias("Revenue")))

agg = (prod.join(qual, ["PlantKey", "YearMonth"], "left")
       .join(maint, ["PlantKey", "YearMonth"], "left")
       .join(sales, ["PlantKey", "YearMonth"], "left")
       .join(spark.table("gold.dim_plant").select("PlantKey", "PlantCode"), "PlantKey")
       .fillna(0, subset=["InspectedUnits", "DefectCount", "MaintenanceEvents", "Orders", "LateOrders"])
       # try_divide returns null instead of failing when a plant had, say, no orders that month
       .withColumn("AttainmentPct", F.expr("round(try_divide(ActualUnits, PlannedUnits), 4)"))
       .withColumn("ScrapRatePct", F.expr("round(try_divide(ScrapUnits, ActualUnits + ScrapUnits), 4)"))
       .withColumn("DefectRatePct", F.expr("round(try_divide(DefectCount, InspectedUnits), 4)"))
       .withColumn("LateOrderPct", F.expr("round(try_divide(LateOrders, Orders), 4)")))
print("gold.agg_plant_month:", save(agg, "gold.agg_plant_month"))
display(spark.table("gold.agg_plant_month").orderBy(F.desc("YearMonth"), "PlantCode").limit(12))

# %% [markdown]
# ## 4 · Verify: row counts, key integrity and headline KPIs
#
# A star schema is only trustworthy if **every fact key finds its dimension row**. The integrity check below
# counts orphaned keys for every relationship the Lab 7 semantic model will use, and every count must be 0.
# Then the headline KPIs are compared with the known answer.

# %%
EXPECTED_GOLD = {
    "dim_date": 912, "dim_plant": 4, "dim_line": 8, "dim_asset": 40, "dim_shift": 3, "dim_product": 20,
    "dim_customer": 36, "dim_defect_type": 13, "fact_production_run": 3629, "fact_quality_inspection": 2729,
    "fact_maintenance_event": 270, "fact_customer_order": 4560, "agg_plant_month": 120,
}
problems = []
for table, expected in EXPECTED_GOLD.items():
    actual = spark.table(f"gold.{table}").count()
    print(f"{'✅' if actual == expected else '❌'} gold.{table:24s} {actual:>6,} (expected {expected:,})")
    if actual != expected:
        problems.append(table)

RELATIONSHIPS = [
    ("fact_production_run", "DateKey", "dim_date"), ("fact_production_run", "PlantKey", "dim_plant"),
    ("fact_production_run", "LineKey", "dim_line"), ("fact_production_run", "ProductKey", "dim_product"),
    ("fact_production_run", "ShiftKey", "dim_shift"),
    ("fact_quality_inspection", "DateKey", "dim_date"), ("fact_quality_inspection", "PlantKey", "dim_plant"),
    ("fact_quality_inspection", "LineKey", "dim_line"), ("fact_quality_inspection", "ProductKey", "dim_product"),
    ("fact_quality_inspection", "DefectTypeKey", "dim_defect_type"),
    ("fact_maintenance_event", "DateKey", "dim_date"), ("fact_maintenance_event", "PlantKey", "dim_plant"),
    ("fact_maintenance_event", "LineKey", "dim_line"), ("fact_maintenance_event", "AssetKey", "dim_asset"),
    ("fact_customer_order", "DateKey", "dim_date"), ("fact_customer_order", "PlantKey", "dim_plant"),
    ("fact_customer_order", "ProductKey", "dim_product"), ("fact_customer_order", "CustomerKey", "dim_customer"),
]
print()
for fact, key, dim in RELATIONSHIPS:
    orphans = spark.table(f"gold.{fact}").join(spark.table(f"gold.{dim}"), key, "left_anti").count()
    if orphans:
        problems.append(f"{fact}.{key}")
    print(f"{'✅' if orphans == 0 else '❌'} {fact}.{key} → {dim}: {orphans} orphaned rows")

k = spark.table("gold.fact_production_run").agg(
    F.sum("PlannedUnits").alias("planned"), F.sum("ActualUnits").alias("actual"), F.sum("ScrapUnits").alias("scrap")
).first()
q = spark.table("gold.fact_quality_inspection").agg(F.sum("InspectedUnits").alias("i"), F.sum("DefectCount").alias("d")).first()
o = spark.table("gold.fact_customer_order").agg(F.sum("Revenue").alias("rev"), F.sum("LateShipmentFlag").alias("late")).first()
kpis = {
    "Actual Units": (k["actual"], 1032704),
    "Scrap Rate %": (round(k["scrap"] / (k["actual"] + k["scrap"]), 4), 0.0313),
    "Production Attainment %": (round(k["actual"] / k["planned"], 4), 0.9426),
    "Defect Rate %": (round(q["d"] / q["i"], 4), 0.0241),
    "Total Revenue": (float(o["rev"]), 1106432678.0),
    "Late Orders": (o["late"], 245),
}
print()
for name, (actual, expected) in kpis.items():
    ok = actual == expected
    print(f"{'✅' if ok else '❌'} {name:24s} {actual:>16,} (expected {expected:,})")
    if not ok:
        problems.append(name)

assert not problems, f"Gold checks failed: {problems}"
print("\n🎉 Gold star schema complete. Next: Lab 6, turning utility-bill PDFs into rows.")
