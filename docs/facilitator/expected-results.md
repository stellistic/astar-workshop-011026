[← Workshop home](../../README.md)

# Expected results

> Generated from [`tools/expected_counts.json`](../../tools/expected_counts.json) by
> `python -m tools.kit.expected_doc`. Don't edit by hand.

The workshop data is fixed and seeded deterministically, so **every participant gets exactly these numbers**.
Each notebook's final *verify* cell checks them automatically.

## Lab 1 · Files

| Lakehouse folder | Files |
|---|---:|
| `Files/landing/plant` | 13 |
| `Files/landing/utility_bills` | 48 (35 digital, 13 scanned) |
| `Files/landing/reference` | 2 |

## Lab 2 · Bronze

| Table | Rows |
|---|---:|
| `bronze.dim_asset` | 40 |
| `bronze.dim_customer` | 36 |
| `bronze.dim_date` | 912 |
| `bronze.dim_defect_type` | 12 |
| `bronze.dim_line` | 8 |
| `bronze.dim_plant` | 4 |
| `bronze.dim_product` | 21 |
| `bronze.dim_shift` | 3 |
| `bronze.fact_anomaly_event` | 4 |
| `bronze.fact_customer_order` | 4,560 |
| `bronze.fact_maintenance_event` | 270 |
| `bronze.fact_production_run` | 3,673 |
| `bronze.fact_quality_inspection` | 2,736 |
| **Total** | **12,279** |

## Labs 3–4 · Silver

| Table | Rows | Built in |
|---|---:|---|
| `silver.fact_production_run` | 3,629 | Lab 3 (notebook) |
| `silver.fact_quality_inspection` | 2,729 | Lab 3 (notebook) |
| `silver.fact_maintenance_event` | 270 | Lab 3 (notebook) |
| `silver.fact_customer_order` | 4,560 | Lab 3 (notebook) |
| `silver.dim_product` | 20 | Lab 4 (Dataflow Gen2) |
| `silver.dim_customer` | 35 | Lab 4 (Dataflow Gen2) |
| `silver.dim_plant` | 4 | Lab 4 (Dataflow Gen2) |
| `silver.dim_date` | 912 | Lab 3 (notebook) |
| `silver.dim_shift` | 3 | Lab 3 (notebook) |
| `silver.dim_line` | 8 | Lab 3 (notebook) |
| `silver.dim_asset` | 40 | Lab 3 (notebook) |
| `silver.dim_defect_type` | 12 | Lab 3 (notebook) |
| `silver.dq_rejects` | 26 | Lab 3 (notebook) |

## Lab 5 · Gold

| Table | Rows |
|---|---:|
| `gold.dim_date` | 912 |
| `gold.dim_plant` | 4 |
| `gold.dim_line` | 8 |
| `gold.dim_asset` | 40 |
| `gold.dim_shift` | 3 |
| `gold.dim_product` | 20 |
| `gold.dim_customer` | 36 |
| `gold.dim_defect_type` | 13 |
| `gold.fact_production_run` | 3,629 |
| `gold.fact_quality_inspection` | 2,729 |
| `gold.fact_maintenance_event` | 270 |
| `gold.fact_customer_order` | 4,560 |
| `gold.agg_plant_month` | 120 |
| `gold.fact_utility_bill` (Lab 6) | 48 |

## Lab 7 · Semantic model measures

| Measure | Expected value |
|---|---:|
| Actual Units | 1,032,704 |
| Planned Units | 1,095,550 |
| Scrap Units | 33,404 |
| Scrap Rate % | 3.13% |
| Production Attainment % | 94.26% |
| Inspected Units | 476,972 |
| Defect Count | 11,481 |
| Defect Rate % | 2.41% |
| Orders | 4,560 |
| Late Order % | 5.4% (245 late) |
| Total Revenue | 1,106,432,678 |
| Maintenance Events | 270 |
| Preventive Maintenance % | 67.0% |
| Electricity kWh (Lab 6, from the PDFs) | 3,355,595 |
| Energy per Unit kWh (Lab 6 × MES) | 16.65 (SG-01 22.05 · MY-01 18.28 · AU-01 15.68 · IN-01 11.84) |

## What was seeded

Seed `20261001`. Only the tables below were changed; every other file is byte-identical to the
K-Corp-Plant source.

| File | Issue | Rows | Silver handling |
|---|---|---:|---|
| `DimCustomer.csv` | duplicate key row | 1 | removed (Lab 4) |
| `DimCustomer.csv` | `Country` as SG/MY/IN/AU or odd casing | 8 | conformed |
| `DimPlant.csv` | `PlantCode` lower-case or padded | 2 | conformed |
| `DimProduct.csv` | duplicate key row | 1 | removed (Lab 4) |
| `DimProduct.csv` | untrimmed `ProductName` | 4 | conformed |
| `DimProduct.csv` | `UnitPrice` like `"$1,199.00"` | 5 | conformed |
| `DimProduct.csv` | lower-case `Category` | 2 | conformed |
| `FactCustomerOrder.csv` | dates written dd/MM/yyyy | 300 | conformed |
| `FactCustomerOrder.csv` | blank `ActualShipDate` (open orders) | 40 | kept, `OrderStatus = Open` |
| `FactCustomerOrder.csv` | `CustomerKey = 999` (no such customer) | 6 | kept; Gold → `-1` *Unknown customer* |
| `FactCustomerOrder.csv` | `Revenue` like `"198,801"` | 50 | conformed |
| `FactMaintenanceEvent.csv` | blank `RootCause` | 9 | conformed |
| `FactMaintenanceEvent.csv` | `PreventiveFlag` as Y/N/yes/TRUE… | 60 | conformed |
| `FactProductionRun.csv` | exact duplicate rows | 25 | removed |
| `FactProductionRun.csv` | negative `ScrapUnits` | 8 | quarantined |
| `FactProductionRun.csv` | impossible `DateKey` (e.g. 20250230) | 5 | quarantined |
| `FactProductionRun.csv` | blank `ActualUnits` | 6 | quarantined |
| `FactProductionRun.csv` | `OperatorTeam` spelling variants | 120 | conformed |
| `FactQualityInspection.csv` | `DefectCount` > `InspectedUnits` | 7 | quarantined |
| `FactQualityInspection.csv` | blank `DefectTypeKey` | 12 | → `-1` *Not recorded* |
| `FactQualityInspection.csv` | `Severity` case/padding variants | 150 | conformed |
