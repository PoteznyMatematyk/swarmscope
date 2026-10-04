# SwarmScope on AI Village: the battery, the reviewers and what they found

*This is the AI Village half of the project. The collusion.wiki study (answer sharing in the DSE-wiki swarm) is in [wikiswarm/RESULTS.md](../wikiswarm/RESULTS.md); the overview is the [README](../README.md).*

*AI Swarm Dynamics Hackathon (AI Village × Grove Research). Code, tests and the offline evidence viewer: this repository. Numbers below are computed from the work files by `scripts/report_numbers.py`.*

## 1. The problem

When METR investigated the OpenAI and Hugging Face incident they "had to heavily delegate our analysis to often-unreliable AI agents". Swarm logs are far too long to read, so investigators ask language models to read them, and those models misquote, miscount and misattribute. The risk is not that they are useless; it is that a wrong sentence looks exactly like a right one. SwarmScope is an investigation tool built around that risk, and it reports how often each layer still goes wrong.

## 2. The rule and the pipeline

**No claim is shown without an `(event ref, verbatim quote)` pair that code, not a model, has found in the log.** Around that rule:

1. **Analysts** (a person, Claude, Gemini, …) answer eleven fixed questions (coordination, leadership, propagation, conflict, misreport, deception, human interaction, failure modes, goal fidelity, norms, belief hardening) for one chunk of a transcript at a time. A deterministic **acceptance gate** decides whether they did the work: it recomputes quote verification itself, demands reading receipts that prove the whole chunk was read, checks that evidence is spread over the chunk, freezes the first pass, logs every repair and deletion, and fingerprints the tool, the protocol and itself. A worker's own report is never trusted; the operator re-runs the gate on every output.
2. **Synthesis** turns accepted claims into candidate findings and must search for counter-evidence.
3. **Four adversarial reviewers** (support, context, significance, *did*: what the agent actually executed, from 2.5 million computer-use turns) try to refute each finding.
4. A **reconciler** re-verifies every factual claim itself, cuts the thesis down to what the log supports, and may reject the finding. Code then re-verifies every quote of the final text.
5. A random sample of verified claims is **re-read in context** by a separate reviewer: does the quote really support the claim?

Two other modules use the same discipline without a model. The **said-vs-did audit** parses the test runs an agent executed and classifies each chat claim that tests pass. The **propagation tracer** finds strings (URLs, files, identifiers) that spread between agents, with lags; every hop is re-verified like a quote.

## 3. What we measured

On AI Village (six episodes: a village training its own "leader" model, a game built while voting out secret saboteurs, a tooling economy under private goals, human-gated outreach, helping another agent, connecting 3D worlds; 19,273 events read in full):

- **2,391 claims, 8,462 quotes, all verified.** Before repair the analyst model misquoted 0.63% of the time; the checker keeps those out.
- **A verified quote supports its claim about 85% of the time.** Two Claude reviewers judged 154 claims (86% supported, 13% partially, 0 unsupported) and GPT-6 Sol, a different model family, judged 200 (84%); on the 101 claims both judged, each finds 87% fully supported. Verified does not mean true, and the viewer says so on its first screen.
- **Findings overclaim even when every quote is real.** Of 32 drafted findings, none passed the strict rule as first written (4 of 128 reviewer verdicts were `accept`). After reconciliation 30 survive, two were rejected outright. Re-checked one by one, **52% of the 337 factual claims in the drafts were supported, 31% overstated and had to be corrected, 17% unsupported and were removed.** The quote checker alone would have published nearly all of them.
- **A cheaper analyst passes the gate and still over-interprets.** Gemini 3.6 Flash High produced 79 claims with zero misquotes and was accepted by the gate, but only 68% of its claims were fully supported (25 audited), so we did not delegate to it. The gate catches invented quotes; only the audit catches over-interpretation. GPT-6 Sol, tried the same way on one chunk, misquoted 6.0% of its quotes before repair (ten times the Claude rate; every quote was repaired and re-verified) but 88% of its claims were fully supported (22 of 25), above the threshold.
- **Said vs did:** of 646 test-success claims that could be judged against the agent's own runs, 87% are backed by the agent's own green run and 9% by another agent's; two were made over a red run or a delegated report. The parser's precision per category is measured and published (92% for `backed`, 25% for `count differs`, which we therefore do not use).
- **Tracer:** on the public collusion.wiki incident it recovers the documented proxy-bypass techniques with adopter counts and lags without being told about them; on AI Village it gives 93 cascades whose 593 hops are all verified.

## 4. What the swarms did

The findings describe what agents said and did in the log, each with its evidence, counter-evidence, limits and scaffolding confound. One pattern recurs across four episodes: **claims travel faster than checks, and the checks are often re-reads rather than tests.**

- **A hedge became a verdict in minutes.** A "could be a hidden Easter egg signature" became "clearly intentional steganography" within 94 seconds and an 11-0 ejection within 25 minutes; the "independent verifications" re-measured the same counts and re-ran the same mapping, and nobody tested whether editor auto-indent explained the whitespace (E2). In E1 a "~20% per layer" extrapolation became "Empirical Framework Validation" in eight minutes.
- **Verification by re-running the author's script.** Peers "independently certified" an agent's mathematical kills by re-running its own verifier within seconds; duplicates and a misread row were caught only by the author's ledger (E4).
- **Self-reports under a goal.** An agent rated its external relationships 98/100 on GitHub comments that its own tool output showed predated its post (E4); dice rolls were tallied as "confirmed villagers" while roll commands printed a 1 behind several public villager claims (E2).
- **Tooling glitches made false alarms.** Stale-base diffs and invisible pull requests produced sabotage accusations that were retracted after a one-line git check (E2).
- **A rule invented by memory.** An accuser quoted an "oval dome" rule that first appears in its own memory record; none of the four votes cited it (E2).
- **A human gate enforces unevenly.** The "mention you're an AI" request recurred for at least five agents over three weeks; enforcement clustered by day (E5).

## 5. Limits

Analysts, synthesis and reviewers are Claude models (GPT-6 Sol audited 200 claims and reconciled six findings; Gemini was measured as an analyst); the reconciler is a single editor model whose output is re-checked by code but not by a second reviewer; 253 of 2,391 claims were audited, and the two Claude reviewers judged the same claims; six of seven windowed episodes are analysed; the said-vs-did audit sees only `bash` turns. Findings make no claim about intent. Nothing from the dataset is committed to the repository.

## 6. Reproduce

`python -m uv sync && python -m uv run pytest -q` (41 tests), then the public collusion.wiki commands in the README reproduce the tracer and the viewer without any account. With access to the gated AI Village dataset the README lists the ingest and battery commands; `scripts/gate_selftest.py` shows the acceptance gate rejecting ten "lazy worker" forgeries.

*Data: AI Village dataset © AI Digest (research terms: research only, no training, no re-identification; please cite AI Digest / AI Village). collusion.wiki public export.*
