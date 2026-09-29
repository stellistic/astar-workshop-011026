# %% [markdown]
# # Lab 2 · Bronze — land the raw plant files as Delta tables
#
# **Bronze is a faithful copy of the source.** You read the 13 K-Corp plant CSV files exactly as they arrived and
# save each one as a Delta table in the **`bronze`** schema of your Lakehouse. You change **nothing**. The files
# have deliberate data-quality problems, and those are fixed in Silver (Lab 3), not here.
#
# | Layer | Schema | What lands there | Rule of thumb |
# |---|---|---|---|
# | **Bronze** | `bronze` | Raw files as tables, every column a *string* | Keep everything, judge nothing |
# | Silver | `silver` | Cleaned, typed, de-duplicated, conformed | Decide what is true |
# | Gold | `gold` | Star schema and business KPIs | Make it easy to use |
#
# > **Before you run:** the Explorer on the left must show **`lh_kcorp_plant`** under *Data items*, marked as the
# > default Lakehouse (pin icon). If it doesn't, see Lab 2, step 3.

# %% [markdown]
# ## 0 · Setup
#
# Create the `bronze` schema, and set the folder where Lab 1 uploaded the files.

# %%
from pyspark.sql import functions as F

LANDING = "Files/landing/plant"  # the folder you uploaded in Lab 1

spark.sql("CREATE SCHEMA IF NOT EXISTS bronze")
print("✅ bronze schema ready")

# %% [markdown]
# ## 1 · Land one file, step by step
#
# Start with the biggest fact: **`FactProductionRun.csv`**, one row per production run on a plant line.
#
# `inferSchema` is **off** on purpose, so every column arrives as a `string`. If Spark guessed the types here, a
# single bad value such as `20250230` in a date column could silently turn into a null. Bronze keeps the raw text,
# so nothing is lost before Silver has decided what to do with it.

# %%
raw_runs = (
    spark.read
    .option("header", True)
    .option("inferSchema", False)
    .csv(f"{LANDING}/FactProductionRun.csv")
)

raw_runs.printSchema()
display(raw_runs.limit(10))

# %% [markdown]
# ### Add two lineage columns, then save as a Delta table
#
# Every Bronze table gets two extra columns so you can always trace a row back to its origin:
#
# - `_source_file` records the file the row came from. `_metadata` is a hidden column Spark provides for file sources.
# - `_ingested_at` records when the row was loaded.
#
# `saveAsTable("bronze.fact_production_run")` writes a **Delta** table into the `bronze` schema. Delta is the open
# table format behind everything in OneLake, and it is what lets the SQL endpoint, Power BI and other engines read the
# same data without copying it.

# %%
bronze_runs = (
    raw_runs
    .withColumn("_source_file", F.col("_metadata.file_path"))
    .withColumn("_ingested_at", F.current_timestamp())
)

bronze_runs.write.mode("overwrite").option("overwriteSchema", True).saveAsTable("bronze.fact_production_run")
print("bronze.fact_production_run:", spark.table("bronze.fact_production_run").count(), "rows")

# %% [markdown]
# ### Peek at the dirt, but don't fix it here
#
# A notebook cell can also be **SQL**: start it with `%%sql`. The query below counts runs per operator team. You
# should see the three real teams (`Team-A`, `Team-B`, `Team-C`) plus messy spellings such as `team-a`,
# `TEAM-B ` and `Team C`, typed by hand on the shop floor. Silver will conform them.

# %%
%%sql
SELECT OperatorTeam, COUNT(*) AS runs
FROM bronze.fact_production_run
GROUP BY OperatorTeam
ORDER BY OperatorTeam

# %% [markdown]
# ## 2 · Land the other twelve files with a loop
#
# Now that you have seen each step, wrap them in a small function and run it for every CSV in the folder.
# File names in `PascalCase` become `snake_case` table names, so `FactCustomerOrder.csv` lands as
# `bronze.fact_customer_order`.

# %%
import re


def to_snake(name: str) -> str:
    """FactCustomerOrder -> fact_customer_order"""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def land_csv(file_stem: str) -> tuple[str, int]:
    table = f"bronze.{to_snake(file_stem)}"
    df = (
        spark.read.option("header", True).option("inferSchema", False)
        .csv(f"{LANDING}/{file_stem}.csv")
        .withColumn("_source_file", F.col("_metadata.file_path"))
        .withColumn("_ingested_at", F.current_timestamp())
    )
    df.write.mode("overwrite").option("overwriteSchema", True).saveAsTable(table)
    return table, spark.table(table).count()


csv_files = sorted(f.name[:-4] for f in notebookutils.fs.ls(LANDING) if f.name.endswith(".csv"))
print(f"Found {len(csv_files)} CSV files in {LANDING}\n")

for stem in csv_files:
    table, rows = land_csv(stem)
    print(f"{table:38s} {rows:>7,} rows")

# %% [markdown]
# ## 3 · Verify: are all 13 Bronze tables there, with the right row counts?
#
# The workshop data is fixed, so everyone should get exactly these numbers. If a line shows ❌, re-check Lab 1:
# were all 13 files uploaded into `Files/landing/plant/`?

# %%
EXPECTED_BRONZE = {
    "DimAsset": 40, "DimCustomer": 36, "DimDate": 912, "DimDefectType": 12, "DimLine": 8, "DimPlant": 4,
    "DimProduct": 21, "DimShift": 3, "FactAnomalyEvent": 4, "FactCustomerOrder": 4560,
    "FactMaintenanceEvent": 270, "FactProductionRun": 3673, "FactQualityInspection": 2736,
}

problems, total = [], 0
for stem, expected in EXPECTED_BRONZE.items():
    table = f"bronze.{to_snake(stem)}"
    actual = spark.table(table).count() if spark.catalog.tableExists(table) else 0
    total += actual
    ok = actual == expected
    print(f"{'✅' if ok else '❌'} {table:38s} {actual:>7,} (expected {expected:,})")
    if not ok:
        problems.append(table)

assert not problems, f"Row counts differ for: {problems}"
print(f"\n🎉 Bronze complete: {len(EXPECTED_BRONZE)} tables, {total:,} rows. On to Lab 3!")
