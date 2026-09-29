[← Workshop home](../README.md)

# Lab 4 · Silver: clean the dimensions without code (Dataflow Gen2)

**⏱ 20 min** · **🎯 Goal:** clean `dim_product`, `dim_customer` and `dim_plant` with **Power Query** clicks, and
write them to the `silver` schema, with no code.

### What you'll build

Lab 3 cleaned the facts with PySpark. Plenty of data work doesn't need code. **Dataflow Gen2** is Fabric's
low-code transformation tool: the same **Power Query** editor you may know from Excel and Power BI, running in
the cloud and writing straight to your Lakehouse. Every click becomes an **Applied step**, so the recipe is
visible, repeatable and editable.

```mermaid
flowchart LR
  B["bronze.dim_product<br/>bronze.dim_customer<br/>bronze.dim_plant"] -->|"df_silver_dimensions<br/>(Dataflow Gen2 · Power Query)"| S["silver.dim_product · 20<br/>silver.dim_customer · 35<br/>silver.dim_plant · 4"]
  classDef done fill:#eeeeee,stroke:#999999,color:#333333;
  class B done;
```

The problems you'll fix (you saw some of them in the Lab 1 preview):

| Table | Problem | Power Query step |
|---|---|---|
| `dim_product` | ` kPods Max` has stray spaces | **Format → Trim** |
| | `smartphones`, `tablets` in lower case | **Format → Capitalize Each Word** |
| | Prices like `$1,199.00` | **Replace values** (twice) → **Decimal number** |
| | `ProductKey 19` appears twice | **Remove duplicates** |
| `dim_customer` | `SG`, `MY`, `singapore`, ` Australia`… | Trim → Replace values → Capitalize |
| `dim_plant` | `sg-01`, ` IN-01 ` | Trim → **UPPERCASE** |

### Files
- [`assets/dim_customer.pq`](assets/dim_customer.pq) · [`assets/dim_plant.pq`](assets/dim_plant.pq) · [`assets/dim_product.pq`](assets/dim_product.pq): the finished Power Query (M) scripts, to paste in when short of time
- [`notebooks/04_silver_dims_catchup.ipynb`](notebooks/04_silver_dims_catchup.ipynb): **catch-up** that builds the same three tables in code

---

### Task A: Create the Dataflow and connect to Bronze

1. In your workspace click **+ New item**, filter for `dataflow`, and choose **Dataflow Gen2**.

   ![New item filtered to "dataflow" with the Dataflow Gen2 tile highlighted.](../docs/images/lab04/lab04-01-new-item-dataflow-gen2.png)

2. Name it **`df_silver_dimensions`** and click **Create**.

   ![The New Dataflow Gen2 dialog with the name df_silver_dimensions.](../docs/images/lab04/lab04-02-name-dataflow.png)

3. The Power Query editor opens. Click **Get data from another source**.

   ![The empty Power Query editor with "Get data from another source" highlighted.](../docs/images/lab04/lab04-03-power-query-editor.png)

4. Search for `lakehouse` and click the **Lakehouse** connector.

   ![Get data filtered to "lakehouse", with the Lakehouse connector highlighted.](../docs/images/lab04/lab04-04-get-data-lakehouse.png)

5. **Authentication kind** is **Organizational account**, already signed in as you. Click **Next**.

   ![Connection settings: Organizational account, signed in, Next.](../docs/images/lab04/lab04-05-lakehouse-connection-signin.png)

6. In **Choose data**, type `bronze.dim_` into the **Search** box (top left) so only your tables show. Tick
   **`bronze.dim_customer`**, **`bronze.dim_plant`** and **`bronze.dim_product`**, then click **Create**.

   > 💡 Click a table's *name* to preview it. In `bronze.dim_product` you can already see `$999.00`,
   > `smartphones`, and `kWatch SE` twice.

   ![Choose data: search "bronze.dim_", three dims ticked, dim_product previewed, Create.](../docs/images/lab04/lab04-06-choose-bronze-dims.png)

7. You now have **three queries** on the left, one per table.

   ![The editor with three queries; the Country column shows SG, MY, IN, AU and case variants.](../docs/images/lab04/lab04-07-queries-loaded.png)

### Task B: Clean `dim_product` step by step

Select **`bronze dim_product`** in the **Queries** list. Watch the **Applied steps** list on the right grow as you go:
each step is one click, and you can select any step to see the data *as it was* at that point.

8. **Rename the query:** in **Query settings → Name**, type **`dim_product`** and press Enter. The query name
   becomes the table name in the Lakehouse.

   ![Query settings: the Name box set to dim_product.](../docs/images/lab04/lab04-08-rename-query.png)

9. **Drop the lineage columns.** **Home → Choose columns**, untick **`_source_file`** and **`_ingested_at`**
   (Bronze bookkeeping, not product attributes) → **OK**.

   ![Choose columns with _source_file and _ingested_at unticked.](../docs/images/lab04/lab04-09-choose-columns.png)

10. **Trim `ProductName`.** Click the **ProductName** column header, then **Transform → Format** (the pen icon) →
    **Trim**.

    ![ProductName selected; Transform → Format → Trim.](../docs/images/lab04/lab04-10-trim-product-name.png)

11. **Fix `Category` casing.** Click the **Category** header → **Transform → Format → Capitalize Each Word**.
    `smartphones` becomes `Smartphones`.

12. **Clean `UnitPrice`.** Right-click the **UnitPrice** header → **Replace values…**. Value to find: **`$`**;
    Replace with: *(leave empty)* → **OK**. Repeat with **`,`** (a comma).

    ![Replace values: find "$", replace with nothing.](../docs/images/lab04/lab04-11-replace-dollar.png)

13. **Set data types.** Click the **ABC** icon at the left of each header and pick a type:
    - **ProductKey** → **Whole number**
    - **UnitPrice** and **StandardCost** → **Decimal number**

    ![The data type menu on ProductKey, with Whole number highlighted.](../docs/images/lab04/lab04-12-change-type.png)

14. **Remove the duplicate.** Click the **ProductKey** header (select *only* this column), right-click it →
    **Remove duplicates**. The row count at the bottom goes from **21** to **20**.

    > ⚠️ Select only **ProductKey** first. With several columns selected, *Remove duplicates* compares the
    > whole selection instead of the key.

    ![Right-click ProductKey → Remove duplicates.](../docs/images/lab04/lab04-13-remove-duplicates.png)

    Your product query is clean. Compare the **Applied steps** with the table at the top of this page:

    ![Clean dim_product: 20 rows, typed prices, and the full Applied steps list.](../docs/images/lab04/lab04-14-product-clean-applied-steps.png)

### Task C: Send it to the Silver schema

15. At the bottom right, under **Data destination**, click **+** → **Lakehouse**.

    ![Data destination + → Lakehouse.](../docs/images/lab04/lab04-15-add-destination-lakehouse.png)

16. Expand **Advanced options** and check that **Navigate using full hierarchy (enables schema support)** is
    **True**. That's what makes the `silver` schema selectable. Click **Next**.

    ![Advanced options with Navigate using full hierarchy = True.](../docs/images/lab04/lab04-16-destination-full-hierarchy.png)

17. Expand **(Current Workspace)** → **`lh_kcorp_plant`** and select the **`silver`** folder (that's the schema).
    Keep **New table**, with the table name **`dim_product`**. The banner should read *"A new table will be created
    in silver"*. Click **Next**.

    ![Destination target: lh_kcorp_plant → silver selected, table name dim_product.](../docs/images/lab04/lab04-17-destination-silver-schema.png)

18. Leave **Use automatic settings** on. It replaces the table on each run and maps the types you set. Click
    **Save settings**.

    ![Destination settings: automatic settings on, typed column mapping, Save settings.](../docs/images/lab04/lab04-18-destination-settings.png)

### Task D: `dim_customer` and `dim_plant`, the fast way

You've seen every kind of step, so for the other two tables you can paste the finished recipe. *(If you have
time, build them by clicking instead: the same steps, listed in the table at the top.)*

19. Right-click **`bronze dim_customer`** in the Queries list → **Advanced editor**.

    ![Right-click a query → Advanced editor.](../docs/images/lab04/lab04-20-query-context-advanced-editor.png)

20. Select everything in the editor, delete it, and paste the contents of
    [`assets/dim_customer.pq`](assets/dim_customer.pq) → **OK**. Read the script: it's the same kind of steps, as text.
    Then rename the query to **`dim_customer`**.

    ![The Advanced editor with the dim_customer M script pasted in.](../docs/images/lab04/lab04-19-advanced-editor-customer.png)

21. Do the same for **`bronze dim_plant`** with [`assets/dim_plant.pq`](assets/dim_plant.pq), and rename it to **`dim_plant`**.
22. For **each** of the two, add the **Lakehouse → `silver`** destination exactly as in steps 15–18.

    All three queries now show *Lakehouse* under **Data destination**:

    ![Three queries (dim_customer, dim_plant, dim_product), each with a Lakehouse destination.](../docs/images/lab04/lab04-21-three-queries-with-destination.png)

### Task E: Save, run and check

23. On the **Home** tab open the **Save** drop-down (the first ribbon button) → **Save, run & close**.

    ![Save drop-down with Save, run & close highlighted.](../docs/images/lab04/lab04-22-save-run-close.png)

24. Back in the workspace, `df_silver_dimensions` shows a spinner while it refreshes. It took **about 2 minutes** in the
    golden run. When it finishes, the *Refreshed* column shows the time.

    ![The workspace list with the dataflow refreshing.](../docs/images/lab04/lab04-23-dataflow-refreshing.png)

25. Open **`lh_kcorp_plant`** → **Tables** → **`silver`** (⋯ → **Refresh** if needed). You should see
    `dim_customer`, `dim_plant` and `dim_product` alongside the Lab 3 tables.

> 🆘 **Out of time, or the refresh failed?** Import and run
> [`04_silver_dims_catchup.ipynb`](notebooks/04_silver_dims_catchup.ipynb). It writes the same three tables in
> code (and shows the code equivalent of every step above). See also
> [troubleshooting](../docs/facilitator/troubleshooting.md#lab-4--dataflow-gen2).

---

### ✅ Checkpoint

| Table | Rows | Check |
|---|---:|---|
| `silver.dim_product` | **20** | no `$`, prices are numbers, categories Capitalized |
| `silver.dim_customer` | **35** | exactly 4 countries: Australia, India, Malaysia, Singapore |
| `silver.dim_plant` | **4** | codes `SG-01`, `MY-01`, `IN-01`, `AU-01` |

**Notebook or Dataflow?** Both produce Delta tables in the same Lakehouse, so downstream users can't tell
the difference. Pick by *who maintains it*: engineers who like code and Git, or analysts who like Power Query.

### Next up
**[Lab 5 · Gold: build the star schema](../lab05-gold/README.md)**
