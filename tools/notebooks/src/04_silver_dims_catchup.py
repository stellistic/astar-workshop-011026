# %% [markdown]
# # Lab 4 · Catch-up: build the three Silver dimensions in code
#
# **Use this notebook only if your Dataflow Gen2 in Lab 4 did not finish**, or you ran out of time. It creates
# exactly the same tables the Dataflow produces:
#
# | Table | Rows | Cleaning applied (same steps as the Dataflow) |
# |---|---|---|
# | `silver.dim_product` | 20 | trim names; `Capitalize Each Word` category; strip `$` and `,` from price; remove the duplicate key |
# | `silver.dim_customer` | 35 | trim text; `SG/MY/IN/AU` → full country name; `Capitalize Each Word` country; remove the duplicate key |
# | `silver.dim_plant` | 4 | trim text; upper-case the plant code |
#
# Compare each step below with the Power Query step of the same name in the Lab 4 guide: code and no-code are two
# routes to the same result.

# %%
from pyspark.sql import functions as F

spark.sql("CREATE SCHEMA IF NOT EXISTS silver")


def trim_all(df):
    return df.select(*[F.trim(F.col(c)).alias(c) for c in df.columns if not c.startswith("_")])


def save(df, table):
    df.write.mode("overwrite").option("overwriteSchema", True).saveAsTable(table)
    return spark.table(table).count()


# %% [markdown]
# ## dim_product
#
# The order matters: **clean first, then remove duplicates.** The duplicate row for one product only matches its
# twin once the text is trimmed.

# %%
product = (
    trim_all(spark.table("bronze.dim_product"))
    .withColumn("Category", F.initcap("Category"))
    .withColumn("UnitPrice", F.regexp_replace("UnitPrice", "[$,]", ""))
    .select(
        F.col("ProductKey").cast("bigint").alias("ProductKey"),
        "ProductCode", "ProductName", "ProductFamily", "Category",
        F.col("UnitPrice").cast("double").alias("UnitPrice"),
        F.col("StandardCost").cast("double").alias("StandardCost"),
    )
    .dropDuplicates(["ProductKey"])
)
print("silver.dim_product:", save(product, "silver.dim_product"), "rows")

# %% [markdown]
# ## dim_customer

# %%
country_codes = {"SG": "Singapore", "MY": "Malaysia", "IN": "India", "AU": "Australia"}
country_fix = F.col("Country")
for code, name in country_codes.items():
    country_fix = F.when(F.col("Country") == code, name).otherwise(country_fix)

customer = (
    trim_all(spark.table("bronze.dim_customer"))
    .withColumn("Country", F.initcap(country_fix))
    .select(
        F.col("CustomerKey").cast("bigint").alias("CustomerKey"),
        "CustomerName", "Industry", "Segment", "Region", "Country",
    )
    .dropDuplicates(["CustomerKey"])
)
print("silver.dim_customer:", save(customer, "silver.dim_customer"), "rows")

# %% [markdown]
# ## dim_plant

# %%
plant = (
    trim_all(spark.table("bronze.dim_plant"))
    .withColumn("PlantCode", F.upper("PlantCode"))
    .select(
        F.col("PlantKey").cast("bigint").alias("PlantKey"),
        "PlantCode", "PlantName", "Country", "Region", "PlantType", "PlantManager",
    )
)
print("silver.dim_plant:", save(plant, "silver.dim_plant"), "rows")

# %% [markdown]
# ## Verify

# %%
checks = {
    "dim_product": (20, "ProductKey"),
    "dim_customer": (35, "CustomerKey"),
    "dim_plant": (4, "PlantKey"),
}
for table, (expected, key) in checks.items():
    df = spark.table(f"silver.{table}")
    rows, keys = df.count(), df.select(key).distinct().count()
    print(f"{'✅' if rows == expected == keys else '❌'} silver.{table:14s} {rows} rows, {keys} distinct keys (expected {expected})")

countries = sorted(r["Country"] for r in spark.table("silver.dim_customer").select("Country").distinct().collect())
plant_codes = sorted(r["PlantCode"] for r in spark.table("silver.dim_plant").collect())
print("countries:", countries)
print("plant codes:", plant_codes)
assert countries == ["Australia", "India", "Malaysia", "Singapore"], countries
assert plant_codes == ["AU-01", "IN-01", "MY-01", "SG-01"], plant_codes
print("\n🎉 Silver dimensions ready. On to Lab 5 (Gold).")
