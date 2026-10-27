# End-to-end test · 27 October 2026

SIGAP run against **live SAP S/4HANA**, **live SAP AI Core**, and a verified call to
**Amazon Bedrock** — the first time every connector answered at once.

**[SIGAP-E2E-test-report.pdf](SIGAP-E2E-test-report.pdf)** — the report: what was tested,
what passed, the one defect found, and nine screenshots.

| | |
|---|---|
| [`agent-output/`](agent-output/) | What the system itself produced: three PDFs, three workbooks, and the rollup's figures as JSON. Not written for this test — these are the files a user downloads from the Reports page |
| [`screenshots/`](screenshots/) | The six UI pages, captured headless against the same database |

## What ran

**One live agent handling.** `Supplier halt threatens TG0011 at plant 1010`, on a material
that really exists in the SAP sandbox. Done in 60 s, 6 steps, autonomous, lead on
`aicore:gpt-5.4`. It read SAP, found stock on hand 10,020 PC, consumption 0.0 PC/day and
no open purchase orders into that plant — and **stopped**, stating that no cost figure
could be given and that calling more specialists would not earn its keep. No action was
raised, which is the right answer for an exposure it could not prove.

**One seeded handling**, deterministic, no model: the Ningbo scenario with three actions,
a priced veto and two recorded outcomes — one with a realized figure, one without. It
exists so the reporting path that needs those things could be exercised. Both handlings
appear in the rollup together.

## The run that pulled in Kira and Tara

Added after the first pass, because the two handlings above never reached the veto or the
calculator: the lead judged, correctly, that neither case had an exposure worth costing.
So the Ningbo scenario was uploaded as the company's own master data (labelled `cached`,
which is what makes the calculator willing to state rupiah at all) and handled live.

**Six of the twelve agents ran, in order: Arya → Elsa → Iris → Clint → Kira → Tara.**
31 steps, `done`, lead on `aicore:gpt-5.4`.

Kira ruled on every option Clint found, and the rulings are the ones the deterministic
engine gives — but produced here by the live team:

```
C  ALLOWED  no rule breached
A  ALLOWED  no rule breached
B  ALLOWED  TKDN rises to 41.6%, back above the 40.0% floor
D  BLOCKED  TKDN falls from 38.2% to 36.1% ... LARTAS: new origin VN adds 10 working days
E  BLOCKED  TKDN falls from 38.2% to 34.8%
```

Tara then costed **only what cleared**: `B+C · Rp 116,000,000 · TKDN 41.6%`, stock
depleted without action on 2026-09-13, and **what the rules cost: Rp 46,000,000** —
`C+E` at Rp 70,000,000 would have been cheaper, struck out by E's TKDN.

The workbook for that run carries **13 sheets**, one per tool actually called, including
`check_local_constraints` and `simulate_scenario`:
[`agent-output/kira-tara-…xlsx`](agent-output/).

### A defect this run found, and the fix

The first attempt failed completely. Clint returned the options under their real ids
(`A`, `B`, `C`, `D`, `E`); Arya **renumbered them** `(1) (2) (3)` when writing the task for
Kira, and every `check_local_constraints` call then missed with `unknown option '1'`.
Nothing cleared, so Tara was never called and the handling produced nothing.

The system failed safely — `missing`, never a guess, no figure invented — but a whole
handling was wasted. Two fixes, both small:

- `tools/compliance.py` now **names the ids that do exist** when one is not found, so the
  next call can be right instead of the agent guessing again.
- `prompts/supervisor.txt` rule 4b: carry every identifier exactly as it came back, never
  renumber a list into `(1) (2) (3)`.

With both in place the run above went through. The lead still invented two ids on the way
(`INT-SBY1`, `SUB M-4472`) and said so in its own recommendation rather than hiding it.

## Connectors, as measured

```
Amazon Bedrock    HTTP 200 in 2.0s · MiniMax M2.5 answered, 74 tokens
SAP AI Core       OAuth ok · 7 deployments · gpt-5.4 and sap-rpt-1.6 present
SAP S/4HANA       live · 1,043 stock · 2,000 PO · 648 sources · 1,766 suppliers
manage.py check   47 modules ok · 45/45 tools · 12/12 prompts
GET /health       model_ready True · sap_ready True
```

Bedrock answers when called directly. `core/llm.py _fallback_aws_options` refuses to build
a Bedrock backend without a **second** AWS account, which the credential bundle does not
carry, so the handling above ran its lead on SAP AI Core instead.

## Defect found

Model cost reports **Rp 0** on every AI Core run: `llm.usd_per_mtok` carries no price for
the `aicore` provider, so token spend is never priced and `SIGAP_COST_CAP_IDR` cannot bite
while the lead runs there. Invisible in a demo; it does disable the spend cap.

## Reproducing it

The run used a scratch database, not `data/sigap.db`. Nothing here touched the record.
