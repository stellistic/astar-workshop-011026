[← Lab 9](../README.md)

# Questions to ask your data agent

The **numbers** must match; the wording won't. Every expected value here was checked with DAX against the golden
model. After each answer, open **steps → DAX** and check which **measure** and which **period** the agent used.

| # | Ask | Expected |
|---|---|---|
| 1 | What is the scrap rate for each plant? | MY-01 **3.79%** · AU-01 **2.94%** · IN-01 **2.92%** · SG-01 **2.91%** |
| 2 | Which plant uses the most energy per unit produced? | **SG-01 22.05** kWh/unit · MY-01 18.28 · AU-01 15.68 · IN-01 11.84 |
| 3 | Which plant has the best yield, and how does MY-01 compare? | **SG-01 97.09%** · IN-01 97.08% · AU-01 97.06% · MY-01 **96.21%** |
| 4 | How many units did our plants produce in 2025? | **415,260** (AU-01 112,917 · IN-01 105,733 · MY-01 101,753 · SG-01 94,857) |
| 5 | How many units did we produce each year? | 2024 **415,861** · 2025 **415,260** · 2026 (Jan–Jun) **201,583** |
| 6 | What is the overall late order rate? | **5.4%** |
| 7 | Which plant has the highest late order rate? | **SG-01 6.6%** (AU-01 5.6% · IN-01 5.2% · MY-01 4.1%) |
| 8 | What share of maintenance is preventive, by plant? | AU-01 **72.6%** · IN-01 66.1% · MY-01 64.6% · SG-01 62.7% (overall 67.0%) |
| 9 | Compare the defect rate of the four plants. | MY-01 **2.70%** · SG-01 2.66% · IN-01 2.19% · AU-01 2.08% (overall 2.41%) |
| 10 | What was MY-01's scrap rate in each year? | 2024 **2.78%** · 2025 **4.07%** · 2026 **5.24%**: it's getting worse |

### Questions that test the agent's limits

- *"Why did MY-01's scrap rate rise in 2026?"* The data can show **what** changed (for example by line, product or
  shift), but not **why**. A good answer says so.
- *"What were total actual units in 2025?"* In the golden run the agent read *actual* as **ordered/shipped** units
  (`fact_customer_order`) and answered 474,693 or 497,238. Compare with question 4.
- *"What will scrap be next quarter?"* There's no forecast in the model. The agent should say it can't answer.
