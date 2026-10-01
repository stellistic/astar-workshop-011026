[← Workshop home](../../README.md)

# Run of show: 1 October, 14:00–17:00

| Time | Block | Facilitator notes |
|---|---|---|
| 13:30 | Doors, Wi-Fi, sign-in | Capacity name and kit URL on screen. Check the [pre-flight](preflight-checklist.md) is done. Capacity Metrics app open. |
| 14:00 | **Welcome · Fabric in 10 minutes** | One lake (OneLake), one copy, many engines. Medallion in one picture. Today's story: K-Corp's four plants. |
| 14:10 | **Lab 0** Setup | Everyone on the **same capacity**. Confirm *Workspace type = Fabric* on each screen, or at least a show of hands. |
| 14:15 | **Lab 1** Land | The *Add to favorites* pop-up blocks the tiles: warn people. Stress **Lakehouse schemas ✔** and the exact folder names. Early finishers: open a few PDFs in the Lakehouse preview, ready for Lab 6. |
| 14:35 | **Lab 2** Bronze | First Spark session start = the capacity's busiest moment. Stagger if needed (*"odd rows, click Run all now"*). Point at `printSchema()`: everything is a string. |
| 14:50 | **Lab 3** Silver | Talk through the rules table *while* it runs. Show `dq_rejects`: nothing is silently dropped. Optional: Data Wrangler. **Say "Stop session" at the end.** |
| 15:15 | **Lab 4** Dataflow Gen2 | Same problems, no code. Explain Applied steps = recipe. The **Navigate using full hierarchy** gotcha is the one to watch. Catch-up notebook for anyone stuck at 15:30. |
| 15:35 | ☕ Break | Look at Monitor for stuck sessions; cancel them. |
| 15:45 | **Lab 5** Gold | Star schema drawing on the whiteboard. Unknown members (`-1`) and why they matter. SQL endpoint query: no Spark needed. |
| 16:05 | **Lab 6** PDFs with AI | **The highlight.** Show one digital and one scanned PDF first. Run cells one at a time. Discussion: *confidence ≠ correctness*. Finish on *kWh per unit*. |
| 16:35 | **Lab 7** Semantic model | Build one relationship and three measures by hand; Copilot or the catch-up notebook does the rest. Check *Scrap Rate % = 3.13%*. |
| 16:55 | Wrap-up | Recap the medallion; point to the ★ labs (Copilot report, **Lab 9 data agent**) as homework; clean-up note (delete workspaces after a week). |

## Buffers and cut lines

- **Running late at 15:35?** Lab 4 becomes a demo: the facilitator shows the Dataflow while participants run the
  catch-up notebook (2 minutes).
- **Running late at 16:35?** In Lab 7, create the model in the UI, then run the catch-up notebook for relationships and
  measures, and spend the time on checking the numbers.
- **AI Functions unavailable?** Lab 6 still runs end to end with `USE_CATCHUP = True`. Demo the live extraction from
  the golden workspace.

## Fast finishers: Lab 9 data agent

Anyone who finishes Lab 7 early can start [Lab 9](../../lab09-data-agent/README.md) (about 25 minutes, no Spark).
If there's no time, **demo it from the golden workspace** in 5 minutes during wrap-up: open `agent_kcorp_plant`,
ask *"What is the scrap rate for each plant?"*, open **steps → DAX**, then show **Prep data for AI** on the model.
The point to land: **check the query, not just the answer**, and put business definitions in the model.

## Golden workspace

`Astar Fabric Workshop - GOLDEN` (k-corp.dev tenant, `capacityshared1`, F2) holds the finished result of every lab.
Use it to demo any step, or to show the end state when someone is stuck.
