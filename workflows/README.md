# workflows/

`battery_v2.mjs` runs the **Grounded Forensic Battery** as a multi-agent workflow for Claude Code's `Workflow` tool (it is plain JavaScript; the
tool supplies `agent()`, `parallel()`, `args`). Everything a model writes is treated as a claim to verify; nothing is trusted because an agent says so.

## Phases

| phase | what happens | deterministic check behind it |
|---|---|---|
| **Analyze** | one analyst per chunk executes a self-contained task packet (`scripts/make_packets.py`): reads the whole chunk, writes claims with `(event ref, verbatim quote)` evidence, repairs what the checker rejects | `scripts/accept_packet.py` recomputes quote verification, checks reading receipts, evidence spread, immutable first pass, logged deletions, tripwire on the tool/protocol. The operator re-runs it independently (`scripts/accept_all.py`) |
| **Benchmark** | the same chunks on other models (`benchModels`) | first-pass misquote rate per model, measured before any repair |
| **Synthesize** | one agent per episode turns the accepted claims into candidate findings, must search for counter-evidence, and proves every quote with `verify-findings` | `swarmscope verify-findings` |
| **Review** | four adversarial reviewers per finding: `support` (does each quote, in context, support the sentence; re-count numbers), `context` (scaffolding, nudger bot, assigned goals), `significance` (is it non-trivial, is the wording over-claiming), `did` (what did the agent actually execute, from the computer-use turns) | reviewers are told to default to `reject` / `revise` |
| **Reconcile** | one editor re-verifies every factual claim of the draft itself, writes only what the log supports (`accept` / `narrow` / `reject`), and re-proves its quotes | `scripts/merge_final.py` re-verifies every quote against the log and the turns database; a finding with one unverified quote is dropped |
| **Audit** | a random sample of verified claims is re-read in context by a separate reviewer: supported / partially / unsupported / misleading | headline metric: how often a verified quote really supports its claim |

The original survival rule (two `accept` verdicts, `support` not rejecting, actions not contradicting) is kept in the output as `strict_survives`; on the
first episodes no finding passed it as first written, which is why the Reconcile step exists: the published version of a finding is the narrowed one,
and the viewer shows, per finding, which factual claims were supported, overstated (corrected) or unsupported (removed).

## Arguments (`args`)

```json
{
  "py": "<venv>/Scripts/python.exe",
  "run": "<repo>/data/work/tool/run.py",
  "accept": "<repo>/swarmscope/scripts/accept_packet.py",
  "root": "<repo>/data/work",
  "turnsDb": "<repo>/data/turns.duckdb",
  "episodes": { "E4_tooler": "<the episode entry of data/work/windows/manifest.json, paths re-anchored to this machine>" },
  "only": ["E4_tooler"],
  "analysts": ["E4_tooler:1", "E4_tooler:2"],
  "synthEpisodes": ["E4_tooler"],
  "maxFindings": 6,
  "analystModel": "sonnet", "judgeModel": "opus", "reviewModel": "sonnet"
}
```

- `analysts`: only these chunk ids are analysed (`[]` = skip the analysis and synthesize episodes that were analysed earlier, use with `synthEpisodes`).
- `judgeModel` = synthesizer and reconciler, `reviewModel` = the four lens reviewers and the audit (defaults to `judgeModel`), `analystModel` = analysts.
- `bench` + `benchModels`: `[{ "ep": "E1_leader", "chunk": 2 }]` with packets `BENCH<model>_<ep>_cNN.md` present.
- `reconcile: false` skips the Reconcile step; `skipSynthesis: true` stops after the analysis.
- `ep.hint` (optional per episode) steers the synthesizer towards what the operator considers most interesting.

Preparing the input on a new machine: `scripts/make_windows.py`, `scripts/make_context.py` (episode windows and context files), copy `src/swarmscope` to
`data/work/tool/swarmscope` plus `data/work/tool/run.py` (the frozen copy the workers use), `scripts/make_packets.py`, then
`scripts/accept_packet.py --baseline` to fix the tripwire. Packets and manifest paths are re-anchored under the local `data/work`, so the same disk can be
used from two machines; set `SWARMSCOPE_PY` to a virtual environment that lives on the local drive.

Results: `python scripts/save_workflow_result.py <task output> data/work/workflow_result_<ep>.json`, then
`python scripts/merge_final.py data/work/workflow_result_<ep>.json data/work/findings_final_<ep>.json`,
then `python scripts/build_final_report.py --runs claude --findings data/work/findings_final*.json --out data/work/final`.

## Cost (measured)

An analyst packet on Sonnet costs about 3-7% of a 5-hour plan window; a synthesis with four reviewers per finding, a reconciler and two audits for one
episode is of the order of 8 million sub-agent tokens. The 5-hour window, not the weekly limit, is the binding constraint: check the plan usage before a run.
