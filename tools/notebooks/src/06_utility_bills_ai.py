# %% [markdown]
# # Lab 6 · Unstructured data — turn utility-bill PDFs into rows with Fabric AI Functions
#
# Everything so far arrived as neat CSV rows. Much of a plant's data doesn't: it arrives as **documents**. In this
# lab you process **48 monthly electricity and water bills** (PDF) for the four K-Corp plants, January–June 2026.
# They come from four utility providers, each with its own layout, and some are in two languages. **13 of them are
# scans: pictures of paper with no text inside at all.**
#
# You will:
# 1. See why ordinary PDF text extraction isn't enough.
# 2. Describe the fields you want once, and let **`ai.extract`** read every bill, scans included, into columns.
#    It runs on Fabric's built-in AI endpoint, so there are no keys and no extra Azure services.
# 3. Put the results through the same medallion as the CSVs: **Bronze** (raw extraction) → **Silver** (typed and
#    checked) → **Gold** (`fact_utility_bill`, joined to your plant and date dimensions).
# 4. **Score the AI against the truth** and answer a real question: *how much energy does each plant use per
#    unit it produces?*
#
# > ⚠️ **Prerequisites:** Labs 1–5 complete. Your capacity must be a paid F2+ (or P) SKU with the
# > *Copilot and Azure OpenAI* tenant setting enabled, which your facilitator has checked. If the AI cell fails,
# > use the **catch-up** cell in step 3 and carry on.

# %% [markdown]
# ## 0 · Install two small packages
#
# - `pypdf` is used in step 1 to read a PDF's text layer the ordinary way.
# - `nest_asyncio` is only needed on **Fabric Runtime 2.0**; it is harmless on Runtime 1.3.
#
# `%pip` restarts the Python part of the session, so keep it as the **first** cell you run.

# %%
%pip install -q pypdf nest_asyncio

# %%
import glob
import os
import time

import pandas as pd
import pyspark
import synapse.ml.aifunc as aifunc
from pyspark.sql import functions as F

# Runtime 2.0 (Spark 4.x) needs these temporary settings for pandas AI Functions; Runtime 1.3 uses the defaults.
if int(pyspark.__version__.split(".")[0]) >= 4:
    aifunc.default_conf.model_deployment_name = "gpt-5-mini"
    aifunc.default_conf.reasoning_effort = "low"
    aifunc.default_conf.temperature = None

BILLS = "/lakehouse/default/Files/landing/utility_bills"  # local mount of your default Lakehouse
REFERENCE = "Files/landing/reference"
for schema in ("bronze", "silver", "gold"):
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {schema}")

bill_files = sorted(glob.glob(f"{BILLS}/*/*.pdf"))
print(f"Spark {pyspark.__version__} · found {len(bill_files)} bills")
assert len(bill_files) == 48, "Expected 48 PDFs under Files/landing/utility_bills/ (see Lab 1)."

# %% [markdown]
# ## 1 · Why not just read the text?
#
# A "digital" PDF has a hidden **text layer**, and a library such as `pypdf` can pull that text out. A **scanned**
# PDF is only a picture, so the same library returns nothing. Run the cell and look at `has_text_layer`.

# %%
from pypdf import PdfReader

inventory = pd.DataFrame(
    [{"document": os.path.basename(f)[:-4], "text_chars": len((PdfReader(f).pages[0].extract_text() or "").strip())}
     for f in bill_files]
)
inventory["has_text_layer"] = inventory["text_chars"] > 50
display(inventory.groupby("has_text_layer").size().rename("bills").reset_index())

sample = PdfReader(f"{BILLS}/202601/IN-01-ELEC-202601.pdf").pages[0].extract_text()
print("---- a digital bill: text comes out, but as one long string ----")
print(sample[:700])
print("\n---- a scanned bill ----")
print(repr(PdfReader(f"{BILLS}/202603/SG-01-ELEC-202603.pdf").pages[0].extract_text()))

# %% [markdown]
# **What you should see:** 35 bills have text and 13 don't. Even for the 35, you'd still have to write rules to find
# *"Total Amount Due"*, *"NET PAYABLE"* or *"Jumlah Perlu Dibayar"* in four different layouts, and maintain those
# rules every time a provider changes its template. That is the job `ai.extract` does for you.
#
# > 💡 Open a couple of the PDFs from the Lakehouse **Files** view to see how different the four layouts are.

# %% [markdown]
# ## 2 · Describe the fields once
#
# Each `ExtractLabel` names one field, says what it means in plain English, and gives its type. `max_items=1` asks
# for a single value rather than a list. This description is the *only* "configuration": there are no templates and
# no training, and the same definition works for every layout.

# %%
def label(name, description, kind="string"):
    return aifunc.ExtractLabel(name, description=description, type=kind, max_items=1)


BILL_FIELDS = [
    label("provider_name", "Legal name of the utility company that issued the bill"),
    label("account_number", "Customer account number / consumer number"),
    label("invoice_number", "Bill or invoice number"),
    label("site_reference", "Site reference or plant code of the customer site, such as SG-01, MY-01, IN-01, AU-01"),
    label("utility_type", "Either Electricity or Water"),
    label("billing_period_start", "First day of the billing period, formatted YYYY-MM-DD"),
    label("billing_period_end", "Last day of the billing period, formatted YYYY-MM-DD"),
    label("meter_number", "Meter serial number"),
    label("previous_reading", "Previous meter reading, as a plain number without separators", "number"),
    label("current_reading", "Current / present meter reading, as a plain number without separators", "number"),
    label("consumption", "Total consumption for the period (kWh for electricity, volume for water), plain number", "number"),
    label("consumption_unit", "Unit of the consumption exactly as printed, for example kWh, m3, Cu M, kL"),
    label("peak_demand_kw", "Maximum / recorded / contracted demand in kW or kVA, if shown; else null", "number"),
    label("currency_code", "ISO currency code of the amounts: SGD, MYR, INR or AUD"),
    label("subtotal_amount", "Amount before tax (sub-total / gross charges), plain number", "number"),
    label("tax_amount", "Total tax amount (GST, SST, CGST+SGST combined), plain number", "number"),
    label("total_amount_due", "Final total amount payable including tax, plain number", "number"),
    label("grid_emission_factor", "Grid emission factor in kg CO2e per kWh, if shown; else null", "number"),
    label("estimated_emissions_kg", "Estimated emissions for the period in kg CO2e, if shown; else null", "number"),
]
print(f"{len(BILL_FIELDS)} fields defined")

# %% [markdown]
# ### Try it on one scanned bill first
#
# This is the heavily degraded scan from step 1, the one `pypdf` read as an empty string. It takes about
# 10–30 seconds.

# %%
one = pd.DataFrame({"file_path": [f"{BILLS}/202603/SG-01-ELEC-202603.pdf"]})
display(one["file_path"].ai.extract(*BILL_FIELDS, column_type="path").T)

# %% [markdown]
# ## 3 · Bronze: extract all 48 bills
#
# The same call, on every file. AI Functions run the requests in parallel; expect about **1–3 minutes**.
#
# Bronze keeps the **raw** answer: every value is stored as a string, together with the source file and the time of
# extraction, so Silver can re-check it later without paying to read the PDFs again.
#
# > 🆘 **Catch-up:** if this cell errors (for example, AI Functions aren't enabled on your capacity), set
# > `USE_CATCHUP = True` and run it again. It loads the golden workspace's extraction results from
# > `Files/landing/reference/` into the same Bronze table, so the rest of the lab still works.

# %%
USE_CATCHUP = False

if not USE_CATCHUP:
    started = time.time()
    docs = pd.DataFrame({"file_path": bill_files})
    extracted = docs["file_path"].ai.extract(*BILL_FIELDS, column_type="path")
    bronze_pdf = pd.concat([docs, extracted], axis=1).astype(str).replace({"None": None, "nan": None, "<NA>": None})
    bronze_pdf.insert(0, "document_id", bronze_pdf["file_path"].str.extract(r"([A-Z]{2}-\d{2}-[A-Z]{4}-\d{6})\.pdf$")[0])
    all_strings = ", ".join(f"`{c}` string" for c in bronze_pdf.columns)
    bills_bronze = (spark.createDataFrame(bronze_pdf, schema=all_strings)
                    .withColumn("_source_file", F.regexp_replace("file_path", "^/lakehouse/default/", ""))
                    .drop("file_path")
                    .withColumn("_extracted_at", F.current_timestamp())
                    .withColumn("_extraction_method", F.lit("fabric-ai-functions:ai.extract")))
    print(f"extracted {len(bronze_pdf)} bills in {time.time() - started:.0f}s")
else:
    bills_bronze = (spark.read.option("header", True).csv(f"{REFERENCE}/utility_bills_extracted_catchup.csv")
                    .withColumn("_extracted_at", F.current_timestamp())
                    .withColumn("_extraction_method", F.lit("catch-up file")))
    print("loaded catch-up extraction results")

bills_bronze.write.mode("overwrite").option("overwriteSchema", True).saveAsTable("bronze.utility_bill_extract")
display(spark.table("bronze.utility_bill_extract").orderBy("document_id"))

# %% [markdown]
# ## 4 · Silver: type it, conform it, and **check the AI's arithmetic**
#
# An AI can read a number *confidently and wrongly*. Silver therefore doesn't trust a value just because it's
# there; it checks each bill against itself:
#
# | Check | Rule | Catches |
# |---|---|---|
# | **Meter check** | `current − previous = consumption` | a misread or dropped digit in any of the three |
# | **Money check** | `subtotal + tax = total` | a misread amount |
# | **Identity check** | the plant code is one of the four known plants | a garbled site reference |
#
# Bills that pass every check are `Passed`; the rest are flagged `Review` for a human to look at. Units are
# conformed too. Water arrives as `m3`, `Cu M`, `kL` or `KL`, all the same thing (1 kL = 1 m³). The Malaysian bills
# print electricity in **`kWj`** (*kilowatt-jam*, Bahasa Melayu for kWh). The printed unit is kept in
# `ConsumptionUnitAsPrinted` so you can see it.

# %%
num = lambda c: F.expr(f"try_cast(regexp_replace(`{c}`, '[, ]', '') AS DOUBLE)")  # noqa: E731
iso_date = lambda c: F.expr(f"to_date(try_to_timestamp(trim(`{c}`), 'yyyy-MM-dd'))")  # noqa: E731

known_plants = [r["PlantCode"] for r in spark.table("gold.dim_plant").select("PlantCode").collect()]
PLANT_IN_NAME = r"^([A-Z]{2}-\d{2})"  # SG-01-ELEC-202603 -> SG-01

silver_bills = (
    spark.table("bronze.utility_bill_extract")
    .select(
        F.col("document_id").alias("DocumentId"),
        F.coalesce(F.upper(F.trim("site_reference")), F.regexp_extract("document_id", PLANT_IN_NAME, 1)).alias("PlantCode"),
        F.initcap(F.trim("utility_type")).alias("UtilityType"),
        F.trim("provider_name").alias("ProviderName"),
        F.trim("account_number").alias("AccountNumber"),
        F.trim("invoice_number").alias("InvoiceNumber"),
        F.trim("meter_number").alias("MeterNumber"),
        iso_date("billing_period_start").alias("BillingPeriodStart"),
        iso_date("billing_period_end").alias("BillingPeriodEnd"),
        num("previous_reading").alias("PreviousReading"),
        num("current_reading").alias("CurrentReading"),
        num("consumption").alias("Consumption"),
        F.trim("consumption_unit").alias("ConsumptionUnitAsPrinted"),
        F.when(F.lower(F.trim("utility_type")) == "electricity", "kWh").otherwise("m3").alias("ConsumptionUnit"),
        num("peak_demand_kw").alias("PeakDemandKw"),
        F.upper(F.trim("currency_code")).alias("CurrencyCode"),
        num("subtotal_amount").alias("SubtotalAmount"),
        num("tax_amount").alias("TaxAmount"),
        num("total_amount_due").alias("TotalAmount"),
        num("grid_emission_factor").alias("GridEmissionFactor"),
        num("estimated_emissions_kg").alias("EmissionsKgCo2e"),
        "_source_file",
    )
    .withColumn("MeterCheck", F.abs(F.col("CurrentReading") - F.col("PreviousReading") - F.col("Consumption")) <= 1)
    .withColumn("MoneyCheck", F.abs(F.col("SubtotalAmount") + F.col("TaxAmount") - F.col("TotalAmount")) <= 0.05)
    .withColumn("IdentityCheck", F.col("PlantCode").isin(known_plants) & (F.col("PlantCode") == F.regexp_extract("DocumentId", PLANT_IN_NAME, 1)))
    .withColumn(
        "DqStatus",
        F.when(F.coalesce(F.col("MeterCheck"), F.lit(False)) & F.coalesce(F.col("MoneyCheck"), F.lit(False))
               & F.col("IdentityCheck"), "Passed").otherwise("Review"),
    )
)
silver_bills.write.mode("overwrite").option("overwriteSchema", True).saveAsTable("silver.utility_bill")
display(spark.table("silver.utility_bill").groupBy("DqStatus").count())
display(spark.table("silver.utility_bill").filter("DqStatus = 'Review'"))

# %% [markdown]
# ## 5 · Trust, but verify: score the AI against the truth
#
# The workshop kit includes a **ground-truth** file with the correct values for every bill (you would rarely have
# one in real life; here it lets you *measure* the AI). The cell compares each extracted field with the truth:
# numbers must match within 0.5%, and text must match exactly (ignoring case and spaces).

# %%
truth = spark.read.option("header", True).csv(f"{REFERENCE}/utility_bills_ground_truth.csv").toPandas()
mine = spark.table("silver.utility_bill").toPandas()
paired = mine.merge(truth, left_on="DocumentId", right_on="document_id", how="inner")

FIELD_MAP = {  # silver column -> ground-truth column
    "PlantCode": "plant_code", "UtilityType": "utility_type", "AccountNumber": "account_no",
    "InvoiceNumber": "invoice_no", "MeterNumber": "meter_no", "PreviousReading": "previous_reading",
    "CurrentReading": "current_reading", "Consumption": "consumption", "PeakDemandKw": "demand_kw",
    "CurrencyCode": "currency", "SubtotalAmount": "subtotal_amount", "TaxAmount": "tax_amount",
    "TotalAmount": "total_amount", "GridEmissionFactor": "grid_emission_factor",
}


def same(a, b):
    if pd.isna(b) or b == "":
        return pd.isna(a)
    try:
        return abs(float(a) - float(b)) <= 0.005 * abs(float(b)) + 1e-9
    except (TypeError, ValueError):
        return str(a).replace(" ", "").lower() == str(b).replace(" ", "").lower()


scores = pd.DataFrame(
    [{"field": col, "correct": sum(same(r[col], r[gt]) for _, r in paired.iterrows()), "bills": len(paired)}
     for col, gt in FIELD_MAP.items()]
)
scores["accuracy"] = (scores["correct"] / scores["bills"]).round(3)
display(scores)
print(f"Overall field accuracy: {scores['correct'].sum() / scores['bills'].sum():.1%} across {len(paired)} bills")

# %% [markdown]
# **Discuss:** are the misses on scans or on digital bills? Did the Silver checks flag the bills that actually
# contain errors? This is why Silver exists: *confidence is not correctness*.

# %% [markdown]
# ## 6 · Gold: `fact_utility_bill`, joined to the star schema
#
# Gold links each bill to the same **`dim_plant`** and **`dim_date`** as the production data. That shared context
# is what lets one question span a PDF and an MES table. Amounts are converted to USD at fixed, illustrative rates,
# so the four currencies can be added up.

# %%
fx = spark.createDataFrame(
    [("SGD", 0.74), ("MYR", 0.22), ("INR", 0.012), ("AUD", 0.66)], "CurrencyCode string, UsdRate double"
)
fact_bill = (
    spark.table("silver.utility_bill")
    .join(spark.table("gold.dim_plant").select("PlantKey", "PlantCode"), "PlantCode", "left")
    .join(fx, "CurrencyCode", "left")
    .select(
        "DocumentId", "PlantKey",
        F.date_format("BillingPeriodStart", "yyyyMMdd").cast("int").alias("DateKey"),
        "UtilityType", "ProviderName", "InvoiceNumber",
        F.when(F.col("UtilityType") == "Electricity", F.col("Consumption")).alias("ConsumptionKwh"),
        F.when(F.col("UtilityType") == "Water", F.col("Consumption")).alias("ConsumptionM3"),
        "PeakDemandKw", "CurrencyCode", "TotalAmount", "TaxAmount",
        F.round(F.col("TotalAmount") * F.col("UsdRate"), 2).alias("TotalAmountUsd"),
        "EmissionsKgCo2e", "DqStatus",
    )
)
fact_bill.write.mode("overwrite").option("overwriteSchema", True).saveAsTable("gold.fact_utility_bill")
print("gold.fact_utility_bill:", spark.table("gold.fact_utility_bill").count(), "rows")

# %% [markdown]
# ## 7 · The payoff: energy per unit produced
#
# Electricity comes from the **PDFs**; units produced come from the **MES** production runs. Neither source can
# answer this alone, but the Gold star schema answers it in a few lines.

# %%
energy = (
    spark.table("gold.fact_utility_bill").filter("UtilityType = 'Electricity'")
    .join(spark.table("gold.dim_date").select("DateKey", "YearMonth"), "DateKey")
    .groupBy("PlantKey", "YearMonth").agg(F.sum("ConsumptionKwh").alias("ElectricityKwh"))
)
per_unit = (
    spark.table("gold.agg_plant_month").join(energy, ["PlantKey", "YearMonth"])
    .groupBy("PlantCode")
    .agg(F.sum("ElectricityKwh").alias("ElectricityKwh"), F.sum("ActualUnits").alias("UnitsProduced"))
    .withColumn("KwhPerUnit", F.round(F.col("ElectricityKwh") / F.col("UnitsProduced"), 2))
    .orderBy(F.desc("KwhPerUnit"))
)
display(per_unit)

# %% [markdown]
# ## 8 · Verify

# %%
checks = {
    "bronze.utility_bill_extract": 48,
    "silver.utility_bill": 48,
    "gold.fact_utility_bill": 48,
}
for table, expected in checks.items():
    actual = spark.table(table).count()
    print(f"{'✅' if actual == expected else '❌'} {table:30s} {actual} (expected {expected})")
unresolved = spark.table("gold.fact_utility_bill").filter("PlantKey IS NULL OR DateKey IS NULL").count()
print(f"{'✅' if unresolved == 0 else '❌'} bills without a plant or date key: {unresolved}")
assert unresolved == 0 and all(spark.table(t).count() == n for t, n in checks.items())
print("\n🎉 Unstructured data is now part of your star schema. Next: Lab 7, the semantic model.")
