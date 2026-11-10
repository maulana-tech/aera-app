# The rule pack

Kira (Rules) rules from a file the company writes and signs off, not from a
model's memory. `tools/compliance.py` reads it; `get_rule_pack` shows what is
in force. This folder holds the format and an example. The pack itself carries
contract terms and supplier certificates, so it is installed per deployment and
never committed: `rule-pack.json` here is in `.gitignore`.

| Where it is read from | |
| --- | --- |
| `AERA_RULE_PACK` | a path, when set |
| `aera/references/rule-pack.json` | otherwise |

No pack installed is a normal state, and the rulings say so: every rule is then
the built-in assumption or the company profile, and each ruling is labelled
**modelled**.

## What a rule is worth

Each rule carries its value, the document it was read from, and whether a person
checked it there. Only a rule with a `source` and `"verified": true` counts as
**derived**. A rule written down without a source, or not yet checked, is still
an assumption and the ruling stays **modelled**, however official it looks.

A ruling is never more trustworthy than the weakest thing under it: the option
it judges (an upload or the fixture), each rule it applied, and the holiday
calendar when it counted working days.

## Format

```json
{
  "version": "2026-10-01",
  "rules": {
    "tkdn_contract_floor_pct":        {"value": 40.0, "source": "...", "verified": true},
    "tkdn_current_pct":               {"value": 38.2, "source": "...", "verified": true},
    "lartas_new_origin_working_days": {"value": 10,   "source": "...", "verified": false},
    "default_port_dwell_days":        {"value": 4,    "source": "...", "verified": false}
  },
  "collective_leave": [
    {"date": "YYYY-MM-DD", "name": "...", "source": "..."}
  ],
  "certificates": [
    {"supplier": "SUP-4417", "certificate": "...", "tkdn_pct": 41.6,
     "valid_from": "YYYY-MM-DD", "valid_until": "YYYY-MM-DD",
     "source": "...", "verified": true}
  ]
}
```

| Rule | Governs | When the pack is silent |
| --- | --- | --- |
| `tkdn_contract_floor_pct` | the local-content floor in the customer contract | company profile `TkdnContractFloorPct` |
| `tkdn_current_pct` | the company's local-content position today | company profile `TkdnCurrentPct` |
| `lartas_new_origin_working_days` | import-licensing time for an origin country new to the company | built-in 10, an assumption |
| `default_port_dwell_days` | discharge to release, used only when no customs history is on record | built-in 4, an assumption |

`collective_leave` is the cuti bersama. No public calendar carries it, so the
LARTAS working-day count skips only weekends and the Indonesian public holidays
(Nager.Date, live) unless it is listed here.

`certificates` is what `get_supplier_certifications` (Vega) reads to say when a
supplier's TKDN certificate lapses. There is no API for them.

## What it does not hold

No contract clause beyond the TKDN floor is encoded: not certification
requirements, approved-supplier lists or origin restrictions. Kira's prompt tells
her to name such a clause as not checked rather than rule on it.

`rule-pack.example.json` is the format filled with the built-in values and
nothing verified. Copy it to `rule-pack.json`, replace every value with the one
in your contract and regulation, give each its source, and mark it verified
only once someone has checked it there.
