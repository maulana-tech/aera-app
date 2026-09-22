# Modelled data

Nothing in this folder is real. It exists so the system can be run before an SAP
API key is available.

Any tool that falls back to a fixture labels its result `Origin.MODELLED`, never
`Origin.LIVE` — so the badge in the UI differs and the two can never be confused.
The calculator refuses to emit rupiah figures from data labelled this way.

Once `SAP_API_KEY` is set, the tools use real data automatically. Uploaded company
CSV ranks above a fixture and is labelled `Origin.CACHED`.
