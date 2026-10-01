[← Workshop home](../../README.md)

# Pre-flight checklist for the Astar Fabric admin

Complete this **at least one working day before** the workshop. Every item was verified in the golden run. The
golden workspace ran on an **F2** with a single user.

## 1 · Tenant settings (Fabric admin portal → Tenant settings)

| Setting | Required for | Set to |
|---|---|---|
| **Users can create Fabric items** | Every lab | Enabled for the workshop security group |
| **Create workspaces** | Lab 0, if participants create their own | Enabled for the workshop group (or pre-create the workspaces) |
| **Users can use Copilot and other features powered by Azure OpenAI** | **Lab 6 (AI Functions)**, Lab 7 Copilot, Labs ★ (report, data agent) | Enabled for the workshop group |
| **Data sent to Azure OpenAI can be processed outside your capacity's geographic region, compliance boundary, or national cloud instance** | Same as above, **for capacities outside the US/EU** (e.g. Southeast Asia) | Enabled (tenant or capacity level) |
| **Data sent to Azure OpenAI can be stored outside your capacity's geographic region, compliance boundary, or national cloud instance** | **Lab 9 (data agent)** keeps chat history; **required for capacities outside the US/EU** | Enabled (tenant or capacity level) |
| **Capacities can be designated as Fabric Copilot capacities** | Copilot and data agent billing to a chosen capacity | Enabled if you use a Copilot capacity |
| **Users can use Copilot, AI Agents, and other AI experiences powered by OpenAI as a Microsoft subprocessor** | Newer Copilot models (if shown in your tenant) | Enabled if your policy allows |

> **Without the Azure OpenAI settings**, Lab 6 fails at step 2 with an AI Functions authorisation error. The lab has
> a catch-up path (`USE_CATCHUP = True`), so the workshop still runs, but the best moment of the afternoon is
> lost. Test it (section 5).

> **Lab 9 (data agent)** needs the *processed* **and** *stored* outside-region settings when the capacity is in
> Southeast Asia. Tenant settings can take **up to an hour** to apply. There's no longer a separate "data agent"
> switch; the Azure OpenAI settings above cover it.

References: [Copilot tenant settings](https://learn.microsoft.com/fabric/admin/service-admin-portal-copilot) ·
[Data agent tenant settings](https://learn.microsoft.com/fabric/data-science/data-agent-tenant-settings) ·
[AI Functions prerequisites](https://learn.microsoft.com/fabric/data-science/ai-functions/overview#prerequisites)

## 2 · Capacity sizing: Spark concurrency is the constraint

Every participant runs notebooks, and **every notebook session reserves Spark cores** until it's stopped or
times out (about 20 minutes idle). Fabric gives **2 Spark VCores per capacity unit**, with **3× burst** for
concurrency. A default starter-pool session is admitted at roughly **8–16 VCores**.

| SKU | Spark VCores (burst) | Comfortable concurrent notebook sessions* | Recommended for |
|---|---:|---:|---|
| F2 | 4 (20) | 1 | the facilitator's golden run only |
| F8 | 16 (48) | 3–5 | a demo, not a room |
| F16 | 32 (96) | 6–10 | ≤ 8 participants |
| **F32** | 64 (192) | 12–20 | **10–16 participants** |
| **F64** | 128 (384) | 24–40 | **16–30 participants** |

\*Rule of thumb, assuming Medium starter-pool nodes. Halve the per-session footprint by using **Small** nodes
(below). Source: [Spark concurrency limits](https://learn.microsoft.com/fabric/data-engineering/spark-job-concurrency-and-queueing).

When the capacity is full, a participant's **Run all** fails immediately with **`HTTP 430 TooManyRequestsForCapacity`**.
Interactive notebooks are **not queued**. See [troubleshooting](troubleshooting.md#spark-430).

**To stretch a smaller capacity:**
1. **Scale up for the afternoon.** F-SKUs are pay-as-you-go: resize in the Azure portal before 14:00 and
   back afterwards.
2. **Smaller nodes.** Capacity settings → *Data Engineering/Science* → create a **capacity pool** named `workshop-small` with
   **Small** nodes, autoscale **1–2**, dynamic executors **1**. Participants can pick it in *Workspace settings → Data
   Engineering/Science → Spark settings → Default pool*.
3. **Remind people to click ■ Stop session** at the end of each notebook lab. The guides say so; say it out loud too.
4. Consider **Autoscale Billing for Spark**, which moves Spark off the shared capacity and bills it per use.

**Other workloads on the same capacity:** Dataflow Gen2 (Lab 4), the SQL endpoint, Direct Lake and Copilot all
consume capacity units too. An F32 or above has comfortable headroom; on an F16, stagger Lab 4.

## 3 · Runtime version

Fabric **Runtime 2.0** (Spark 4.1) becomes the default for new workspaces in late September 2026. The workshop
notebooks were verified on **both Runtime 1.3 and Runtime 2.0**. No action is needed, but if a participant's
workspace has a custom environment pinned to something older than 1.3, AI Functions won't load.

## 4 · Participant accounts and workspaces

- **Licences.** A **Fabric (Free)** licence is enough for Labs 0–6 (Lakehouse, notebooks, Dataflow Gen2, AI
  Functions) in a workspace on an F-SKU. **Lab 7 and Lab ★ create a semantic model and a report, which are Power
  BI items (Lab 9's data agent needs no extra licence, but builds on the Lab 7 model), so each participant needs Power BI Pro or Premium Per User** (Microsoft 365 E5 includes Pro).
  A free user can only create them in *My workspace*. Check this early: it's the most common surprise.
  [Reference](https://learn.microsoft.com/power-bi/consumer/end-user-features)
- Decide: **participants create their own workspace** (Lab 0, needs *Create workspaces*) **or** you pre-create
  `Fabric Workshop - <name>` workspaces on the capacity and give each person **Admin** or **Member**.
- Participants need **outbound HTTPS** to `app.fabric.microsoft.com`, `*.powerbi.com`, `onelake.dfs.fabric.microsoft.com`
  and `github.com` (to download the kit), and must be able to **upload files from their laptop** (no DLP block on the
  browser upload).

## 5 · Dry run (30 minutes)

With a participant-like account (not a Fabric admin):

1. Create a workspace on the capacity (Lab 0).
2. Create `lh_kcorp_plant` and upload **one** CSV and **one** PDF (Lab 1).
3. Create a new notebook, attach the Lakehouse, and run this cell (it reads the one PDF you uploaded):

   ```python
   import glob, pandas as pd
   import synapse.ml.aifunc as aifunc

   pdf = glob.glob("/lakehouse/default/Files/landing/utility_bills/*.pdf")[0]
   label = aifunc.ExtractLabel("total_amount_due", description="Final total payable", type="number", max_items=1)
   display(pd.DataFrame({"file_path": [pdf]})["file_path"].ai.extract(label, column_type="path"))
   ```

   A number comes back → AI Functions work. ✅ An authorisation or "not enabled" error → revisit section 1.
4. Create a Dataflow Gen2 and confirm the **Lakehouse** destination lists your `silver` schema (Lab 4).
5. Delete the test workspace.

## 6 · Make sure the capacity stays on

If the capacity is **paused** by an automation (a common cost-saving setup), every notebook, query and report fails
at once. The golden run's own F2 is suspended nightly by a runbook. Disable any schedule that pauses the workshop
capacity on the day, and check it's **Active** at 13:30.

## 7 · On the day

- Put the **capacity name** and the **GitHub kit URL** on the first slide.
- Open the [Capacity Metrics app](https://learn.microsoft.com/fabric/enterprise/metrics-app) and watch CU% during
  Labs 2–6. Above 80%, remind people to stop idle sessions.
- Keep the [expected results](expected-results.md) and [troubleshooting](troubleshooting.md) pages open.
