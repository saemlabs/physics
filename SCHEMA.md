# CSV Schema — Narrative Extension

Every row of `content_batch.csv` may include three new optional columns
**after** `audio_script`. Rows that leave them empty fall back to the
legacy sequential reveal (header → visual → equations → answer).

## Column: `beats_json`

A JSON array of narrative beats. Each beat has a **timestamp in seconds**
(relative to audio start) and a **type** that determines the visual
treatment. Beats fire in timestamp order.

```json
[
  {"t": 0.0,  "type": "hook",     "content": "What IS energy?"},
  {"t": 3.5,  "type": "analogy",  "focus": "charge_E"},
  {"t": 8.0,  "type": "law"},
  {"t": 14.0, "type": "emphasis", "focus": "energy_flow"},
  {"t": 20.0, "type": "emphasis", "focus": "graph_main"},
  {"t": 26.0, "type": "punchline"}
]
