# Tool sweep · every read-only tool, called once against live data

No model involved. Tools that change something outside SIGAP were skipped by name.

| Agent | live | derived | modelled | missing | skipped (writes) |
|---|---|---|---|---|---|
| `compliance` | 0 | 0 | 2 | 0 | 0 |
| `demand` | 0 | 1 | 0 | 2 | 0 |
| `execution` | 0 | 0 | 0 | 0 | 9 |
| `exposure` | 0 | 2 | 1 | 1 | 0 |
| `impact` | 3 | 1 | 0 | 0 | 0 |
| `inventory` | 2 | 1 | 0 | 0 | 0 |
| `logistics` | 4 | 1 | 1 | 1 | 0 |
| `precedent` | 0 | 0 | 0 | 0 | 0 |
| `procurement` | 5 | 0 | 0 | 0 | 1 |
| `simulation` | 1 | 1 | 0 | 0 | 0 |
| `sourcing` | 0 | 2 | 0 | 1 | 0 |
| `supervisor` | 0 | 0 | 0 | 1 | 0 |

**45 tools · live 15 · derived 9 · modelled 4 · missing 6 · skipped 10**

Every `missing` carries its reason — none of them guessed. The one `ERROR` in the raw
log was the sweep's own fault: it passed a list where `search_past_incidents` declares a
string, and the tool was right to refuse. Called correctly it answers `missing` with
"nothing has been handled to completion yet… This is the first one".

Raw output: [`tool-sweep.txt`](tool-sweep.txt) · [`tool-sweep.json`](tool-sweep.json)
