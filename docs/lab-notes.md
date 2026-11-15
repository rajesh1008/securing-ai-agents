# Bulwark

Policy-enforcement layer built through *Securing AI Agents*.

```bash
cd securing-ai-agents
python3 -m pytest -q
python3 scripts_run_lab.py
```

Never commit `.env`. Put your key in `.env` at the repository root (copy `.env.example`) or export it.

## Chapter 7 (least privilege at runtime)
Module `bulwark/runtime_scope.py` (compute_scope, intersect, normalise, Session ratchet, Lease, SpendMeter, ReadScope, mine_scope, reach); tests `tests/test_runtime_scope.py`.
Scripts: `ch07_designs.py`, `ch07_excess.py`, `ch07_walkthrough.py`, `ch07_magnitude.py`, `ch07_mining_leases.py`, `ch07_draft_chain.py`, `ch07_split_reconcile.py`, `ch07_read_scope.py`, `ch07_token_audit.py` (no model); `ch07_loadout_live.py`, `ch07_model_scope_live.py`, `ch07_loop_live.py` (live, uses ANTHROPIC_API_KEY from the environment or .env).

## Chapter 25 (MCP security)
Module `bulwark/mcpguard.py` (tool_digest, Pin, diff_manifest, scan_tool, HostCatalogue, ToolPolicy, AudienceTokens, safe_join, run_argv, check_args); tests `tests/test_mcpguard.py` (205 in all). Scripts: `ch25_manifest_diff.py`, `ch25_shadowing.py`, `ch25_expose.py` (real loopback HTTP), `ch25_passthrough.py`, `ch25_cost.py` (no model); `ch25_poison_live.py`, `ch25_reviewer_live.py`, `ch25_param_fix_live.py` (live); fixtures in `ch25_fixtures.py`.

## Chapter 26: skills, plugins and the supply chain
`bulwark/supplychain.py`: `artefact_digest`, `LockEntry`, `Lock.verify` (verdicts: OK, FLOATING_SPEC, UNLOCKED, TYPO_OF_LOCKED, SOURCE_CHANGED, REVIEW_EXPIRED, VERSION_CHANGED, DIGEST_MISMATCH, PERMISSIONS_WIDENED), `lint_skill`, `observed_permissions`, `undeclared`, `compose_check`. Tests: `tests/test_supplychain.py`. Labs: `ch26_corpus.py` + `ch26_scan.py` (48 skills), `ch26_lock.py` (192 cases), `ch26_oversight_live.py` (120 live runs; needs the API key in `.env`), `ch26_compose.py` (simulation, seed 26), `ch26_cost.py`. Results in `results/ch26_*`.

`bulwark/sandbox.py` (Chapter 27): `Limits`, `Manifest` (inputs, output tmpfs, network, env, libs), `run_code(rung, code, workdir, ...)` on four rungs (R0 bare, R1 process hygiene, R2 bwrap namespaces, R3 narrowed: named inputs read-only, tmpfs output, no nested user namespaces, capabilities dropped, seccomp deny-list), `available()`, `plan_for(origin)` (raises rather than downgrades), `manifest_from_declaration`, `box_covers`. Tests: `tests/test_sandbox.py` (needs `bwrap` and unprivileged user namespaces; skipped otherwise). Labs: `ch27_world.py` (canary fixture and host listeners), `ch27_battery.py` (16 programs x 4 rungs), `ch27_agentcode_live.py` (`LAB=data` and `LAB=skill`; live, needs the API key in `.env`; replays every model-written program on all rungs), `ch27_mounts.py`, `ch27_evasion_box.py`, `ch27_cost.py`. Results in `results/ch27_*`.

## Chapter 29 (red-teaming Quill)
`bulwark/redteam.py` (Engagement, Finding, triage, upper_bound, campaigns_needed, discovery_curve, queue_wait, tenant_from_body, tenant_from_credential, provenance_route); tests `tests/test_redteam.py` (14; suite 277 + 23 scenarios).
Scripts: `ch29_attack_matrix.py` (no model), `ch29_campaign.py` (live; 60 campaigns), `ch29_campaign_control.py` (positive control), `ch29_campaign_d.py` (benign control + tier D), `ch29_attacker_model.py` (Sonnet attacker), `ch29_untested_cells.py`, `ch29_budget.py`, `ch29_findings.py` (no model). Results `results/ch29_*`.

## Chapter 32 (detection)
`bulwark/detect.py` (Obs, Alert, AmountDetector, AccountDetector, ReverseShadow, RunDetector, Cusum, arl0, Budget, merge, score, DetectConfig with digest, Monitor); tests `tests/test_detect.py` (21; full pytest 325 passing).
Scripts: `ch32_world.py` (live; builds and caches the injected attacks, results/ch32_world.json is write-protected: rebuilding changes extractions), `ch32_detect.py` (no model; detectors, cadence, budget, CUSUM, monitor check), `ch32_triage.py` (live; model reads the weekly AUTO log). Needs ch31_stream results.

Ch34: `bulwark/disclosure.py` (Fact, Claim, check, corrections, record_sent), `tests/test_disclosure.py` (15). Scripts: `ch34_timeline.py` (no model; how counts go stale), `ch34_notice.py` (live Haiku 4.5, 40 calls ~$0.10 per run; N1-N4; earlier runs kept as results/ch34_notice_run1_checker_v1.json, _run2_checker_v2.json, _run3_checker_v2.json; final scores re-computed in results/ch34_notice_rescore_final_v4.log), `ch34_case.py` (no model; case file, sent-notice record, corrections).

## Chapter 35 (evidence for the CISO and the auditor)
`bulwark/bundle.py` (Item, Control, Bundle, make_item, stamp, module_digests, verify with 13 issue kinds, sign / check_signature (Ed25519), diff, impact, record_signed, attest_check with 7 issue kinds); tests `tests/test_bundle.py` (17). Scripts: `ch35_reproduce.py` (no model; copies the tree to ../../tmp/repro35, stubs the API so a script that calls it exits 86, re-runs every chapter script and compares files) + `ch35_reproduce_report.py`; `ch35_collect.py` (no model; the real Bulwark bundle: 17 controls, 22 items, verify, sign, tamper, diff, chain row); `ch35_impact.py` (no model; module -> items and controls; stamps its own output); `ch35_attest.py` (live Haiku 4.5, 38-40 calls ~$0.23 per run; arms A1-A4) + `ch35_attest_report.py` (re-scores stored drafts; `*16controls*` files use the 16-control bundle); `ch35_auditor.py` (live; 240 calls ~$0.80 per run; Q1/Q2). Earlier runs kept: `ch35_collect_first_draft_of_bundle.*`, `ch35_attest_run1_checker_v1.*`, `ch35_attest_run2_16controls.*`, `ch35_auditor_run1_owner_missing_from_view.*`, `ch35_auditor_run2_16controls.*`, `ch35_reproduce_run1_api_reachable.*`. Note: results/ch35_impact.json stamps the module digests; editing bundle.py makes verify report CODE_CHANGED for item E22 until ch35_impact.py is re-run.

## Chapter 38 (securing the multi-agent case)
`bulwark/agentlink.py` (AgentCard, Registry.check_card with 6 kinds, Datum, Ref, Envelope, sign/verify, delegate, check with 17 issue kinds, effective, effect_ok), `tests/test_agentlink.py` (17); `Role.PEER` in `bulwark/degrade.py` (+2 tests); `rows38()` and 13 C19 rows in `bulwark/crosswalk_data.py` (+1 test); full suite 413 passing. Scripts: `ch38_topology.py` (no model; reach of an injection in a six-agent topology under four designs), `ch38_relay_live.py` (live Haiku 4.5; intake -> coordinator -> comms; arms A free text, D typed with notes, C envelope; 450 pipelines in the final run, run 1 kept as `_run1_hold_default_n1`), `ch38_remote_live.py` (live; remote agent reply, 240 pipelines), `ch38_laundered_live.py` (live; the last hop alone, 360 calls), `ch38_loops.py` (no model; ping-pong and ring fan-out under five limits), `ch38_cards.py` (no model; nine card changes), `ch38_crosswalk.py` (no model; C19 rows, ASI07 closed to PARTIAL, PEER drill grid). Live spend about $1.65 at list price.

## Chapter 39 (evidence for the examiner)
`bulwark/examiner.py` (QUESTIONS Q1-Q14, scope, coverage, timeline, check with 8 issue kinds, verify_segment), `tests/test_examiner.py` (15); `bulwark/evidence.py` schema widened by 14 fields (amount_cents, invoice, payee, sender, receiver, verb, hop, taint, model, prompt_version, vendor_version, dest_digest, markers, detector); full suite 428 passing. Scripts: `ch39_payment.py` (no model; the real MoneyGate, Vault and Dispatcher through one payment at instrumentation levels V1 and V2; coverage of the 14 questions), `ch39_examiner_live.py` (live, Haiku 4.5; 40 answer sheets over V1/V2 x P1/P2; correct, wrong, refused, fabricated; what `check()` flags; false alarms), `ch39_months_later.py` (no model; replay against today's state vs the rebuilt record, erasure, retention purge and segment verification). Results: `results/ch39_*.json|log`; earlier live runs kept as `_run1_strictscore`, `_run2_noqissue`, `_run3_oldchecker`; evidence exports in `results/ch39_examiner_evidence_V1|V2.jsonl`.

## Chapters 40-41 (not previously listed here)
Ch40: `bulwark/provenance.py`, `bulwark/poisonlab.py`, `tests/test_provenance.py`; scripts `ch40_*.py`. Ch41: `bulwark/rota.py`, `tests/test_rota.py`; scripts `ch41_rota.py`, `ch41_decay.py`, `ch41_scorecard.py`, `ch41_creep.py` (live Haiku 4.5), collector C18-C20 in `ch35_collect.py`. See the chapters for runs kept.

## Chapter 42 (patterns and anti-patterns)
`bulwark/patterns.py` (Entry, CATALOGUE of 33: P01-P18, A01-A15; check with PASS/FAIL/NA, ABSENT/PRESENT/NA, ERROR, WAIVED; findings, claim_level, scan_code v2, table); tests `tests/test_patterns.py` (10) and `tests/test_principles_default.py` (Mediator fail_mode default stays "closed"; waiver W-A06-1). Scripts: `ch42_designs.py` (sheets Q01, Q12, Q41, DEMO), `ch42_catalogue.py` (no model; lab 1; first run kept as `_run1`, v1 code scan as `_scanv1`), `ch42_mutants.py` (no model; lab 2; drift and code variants; `_run1` kept), `ch42_reviewer_live.py` (live Haiku 4.5, 180 calls ~$0.43) + `ch42_reviewer_rescore.py` (re-scores stored replies after the parser fix).

## Chapter 43 (model risk and validation)
`bulwark/modelrisk.py` (Component, classify, tier, ELEMENTS, Pack, pack, field_accuracy, agreement, norm); tests `tests/test_modelrisk.py` (5). Scripts: `ch43_invoices.py` (60 synthetic invoices, seed 4343, five renderings), `ch43_inventory.py` (no model; labs 1 and 3: 16 components, pack of 55 rows), `ch43_outcomes_live.py` (live; Haiku 4.5 x3, perturbations, Sonnet 4.6 and Haiku 5.5 challengers; run 2 reported, `_run1` kept), `ch43_challenger_retry.py` (live; Haiku 5.5 at 1,500 tokens on the 11 empty replies). About $0.88 in total.

## Chapter 44 (owning agent security)
`bulwark/ownership.py` (Person, Decision with deputy, Register.issues with 20 kinds, depart, route); tests `tests/test_ownership.py` (8); full suite 479 passing. Scripts: `ch44_org.py` (people incl. Maya Brooks and Daniel Ortiz; DRAFT, REV1, REV2, REVISED registers), `ch44_register.py` (no model; lab 1: checker with and without the deputy check, departure test, route), `ch44_decisions.py` (no model; lab 2: a year of decisions under CENTRAL, NEAREST and REGISTER variants, 200 simulated years each; rates, hours and capacities are author estimates), `ch44_requests.py` (120 synthetic requests, 30 with a planted line), `ch44_router_live.py` (live Haiku 4.5, 720 calls ~$0.34; ROUTE vs CLASSIFY; writes `results/ch44_router_live_raw.json` before scoring; a first run crashed in its report line and its replies were lost).
