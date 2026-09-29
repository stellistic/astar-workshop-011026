[← Lab 7](../README.md)

# Copilot prompts for Lab 7

Paste these into the **Copilot** pane of the semantic model (you must be in **Editing** mode). Copilot is not
deterministic: always check its work against the tables in the Lab 7 guide. If it gets something wrong, run
[`07_semantic_model_catchup`](../notebooks/07_semantic_model_catchup.ipynb), which adds only what's missing.

## Prompt 1 · The remaining 19 relationships

```text
In this semantic model, create these relationships. Every one is many-to-one (*:1) from the fact table column
to the dimension table column, cross-filter direction Single, and active. Do not create any other relationships.

fact_production_run[DateKey] -> dim_date[DateKey]
fact_production_run[LineKey] -> dim_line[LineKey]
fact_production_run[ProductKey] -> dim_product[ProductKey]
fact_production_run[ShiftKey] -> dim_shift[ShiftKey]
fact_quality_inspection[DateKey] -> dim_date[DateKey]
fact_quality_inspection[PlantKey] -> dim_plant[PlantKey]
fact_quality_inspection[LineKey] -> dim_line[LineKey]
fact_quality_inspection[ProductKey] -> dim_product[ProductKey]
fact_quality_inspection[DefectTypeKey] -> dim_defect_type[DefectTypeKey]
fact_maintenance_event[DateKey] -> dim_date[DateKey]
fact_maintenance_event[PlantKey] -> dim_plant[PlantKey]
fact_maintenance_event[LineKey] -> dim_line[LineKey]
fact_maintenance_event[AssetKey] -> dim_asset[AssetKey]
fact_customer_order[DateKey] -> dim_date[DateKey]
fact_customer_order[PlantKey] -> dim_plant[PlantKey]
fact_customer_order[ProductKey] -> dim_product[ProductKey]
fact_customer_order[CustomerKey] -> dim_customer[CustomerKey]
fact_utility_bill[DateKey] -> dim_date[DateKey]
fact_utility_bill[PlantKey] -> dim_plant[PlantKey]
```

## Prompt 2 · The remaining measures

```text
Add these measures to the semantic model exactly as written: put each measure on the table named in brackets,
and use the given DAX and format string. Do not rename anything or change the DAX.

[fact_production_run] Scrap Units = SUM ( 'fact_production_run'[ScrapUnits] )  format #,0
[fact_production_run] Scrap Rate % = DIVIDE ( [Scrap Units], [Actual Units] + [Scrap Units] )  format 0.00%
[fact_production_run] Production Attainment % = DIVIDE ( [Actual Units], [Planned Units] )  format 0.0%
[fact_production_run] Downtime Minutes = SUM ( 'fact_production_run'[DowntimeMinutes] )  format #,0
[fact_quality_inspection] Inspected Units = SUM ( 'fact_quality_inspection'[InspectedUnits] )  format #,0
[fact_quality_inspection] Defect Count = SUM ( 'fact_quality_inspection'[DefectCount] )  format #,0
[fact_quality_inspection] Defect Rate % = DIVIDE ( [Defect Count], [Inspected Units] )  format 0.00%
[fact_maintenance_event] Maintenance Events = COUNTROWS ( 'fact_maintenance_event' )  format #,0
[fact_maintenance_event] Preventive Maintenance % = DIVIDE ( CALCULATE ( [Maintenance Events], 'fact_maintenance_event'[PreventiveFlag] = 1 ), [Maintenance Events] )  format 0.0%
[fact_customer_order] Orders = COUNTROWS ( 'fact_customer_order' )  format #,0
[fact_customer_order] Total Revenue = SUM ( 'fact_customer_order'[Revenue] )  format #,0
[fact_customer_order] Late Order % = DIVIDE ( SUM ( 'fact_customer_order'[LateShipmentFlag] ), [Orders] )  format 0.0%
[fact_utility_bill] Electricity kWh = SUM ( 'fact_utility_bill'[ConsumptionKwh] )  format #,0
[fact_utility_bill] Utility Cost USD = SUM ( 'fact_utility_bill'[TotalAmountUsd] )  format #,0
```

## Prompt 3 · Ask it about your model (try after the measures exist)

```text
Which plant has the highest scrap rate, and how does its energy per unit compare with the other plants?
```
