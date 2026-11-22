# Securing AI Agents: the code

This is the code for **Securing AI Agents** by **Rajesh Ranjan Mahapatra**: the Bulwark policy layer, its test suite, and the lab scripts behind every result printed in the book.

The book follows one running example. Quill is a bookkeeping agent at a fictional company, Ledgerly Cloud, working for a small customer called Hill Country Bakehouse. Quill reads invoices, emails and bank feeds, and it can draft invoices and propose payments. That makes it a good target. **Bulwark** is the layer we build around it, chapter by chapter: the code that decides, outside the model, whether an action Quill proposes is allowed to happen.

The rule Bulwark is built on is simple: **the model proposes, deterministic code decides.** A model can be talked into anything. Code that checks the payee, the amount, the tenant and the approval record cannot be talked into anything, so that is where the money path's decisions live.

> **Status: first edition, version 1.1 (November 2026).** The code here matches the book; the release tagged `v1.1` is the snapshot the book's text and recorded results refer to. In the book, every chapter's interview questions and answers are collected in a back-matter part, numbered by chapter (Q3.1 and so on).

## What is in here

| Path | What it is |
|---|---|
| `bulwark/` | The Bulwark package: policy gate, identity, runtime scope, egress, evidence, MCP guard, supply chain, sandbox, detection, rollout, disclosure and the rest. One module per idea, mostly standard library. |
| `tests/` | The unit tests. None of them call a model. |
| `chNN_*.py`, `scripts_chNN_*.py` | Lab scripts, named by chapter. Each one writes its output to `results/`. |
| `results/` | The recorded outputs the book quotes, including real model replies from the live runs. Re-running a live lab will give you different numbers; that is the point of recording them. |
| `attacks/`, `fixtures/`, `scenarios/`, `threatmodel/` | Payload library, test documents, scenario tests and the Chapter 2 and 3 threat models. |
| `docs/lab-notes.md` | Per-chapter notes on modules, scripts and which earlier runs were kept. |

The scripts sit at the top level, next to `bulwark/`, because that is how the book refers to them (`python ch07_designs.py`). Each script finds the package relative to its own location, so run them from the repository root.

## Chapter map

| Part | Ch | Title | Lab scripts |
|---|---|---|---|
| I | 1 | Untrusted Code Reading Untrusted Input | `ch01_*.py` (6) |
| I | 2 | Threat-Modelling an Agent, End to End | `scripts_ch02_*.py` (9) |
| I | 3 | The Twelve Surfaces | `ch03_*.py` `scripts_ch03_*.py` (4) |
| I | 4 | Classical Principles, Applied to Agents | `ch04_*.py` (4) |
| I | 5 | The Autonomy Decision as a Security Control: What Should Not Be a Model Call | `ch05_*.py` (7) |
| II | 6 | Identity: Who Is the Agent? | `ch06_*.py` (7) |
| II | 7 | Least Privilege at Runtime | `ch07_*.py` (12) |
| II | 8 | Deterministic Gates and the Money Path | `ch08_*.py` (6) |
| II | 9 | Structured Outputs at the Gate: Schemas as a Security Boundary | `ch09_*.py` (7) |
| II | 10 | Human Approval That Means Something | `ch10_*.py` (6) |
| II | 11 | Data Boundaries and Tenancy | `ch11_*.py` (8) |
| II | 12 | Egress: Where Outputs May Go | `ch12_*.py` (5) |
| II | 13 | Evidence: Proving What Happened | `ch13_*.py` (7) |
| II | 14 | Document Agents Under Attack: Extraction, Verification and Confidence Routing | `ch14_*.py` (8) |
| II | 15 | Workshop: Securing the Reconciliation Flow | `ch15_*.py` (3) |
| III | 16 | The Anatomy of Prompt Injection | `ch16_*.py` (3) |
| III | 17 | The Payload Library | `ch17_*.py` (4) |
| III | 18 | Prompts as Code: Versioning, Testing and Releasing Prompt Changes Safely | `ch18_*.py` (4) |
| III | 19 | Defences That Reduce Likelihood | `ch19_*.py` (11) |
| III | 20 | Architectural Defences | `ch20_*.py` (6) |
| III | 21 | Untrusted Tool Results | `ch21_*.py` (5) |
| III | 22 | Memory and State Poisoning | `ch22_*.py` (6) |
| III | 23 | Jailbreaks, Model Alignment and Their Limits | `ch23_*.py` (5) |
| III | 24 | Agents Behind a Model Gateway: Approved Models, Rotating Keys and Deprecations | `ch24_*.py` (5) |
| IV | 25 | MCP Security | `ch25_*.py` (9) |
| IV | 26 | Skills, Plugins and the Agent Supply Chain | `ch26_*.py` (6) |
| IV | 27 | Sandboxing and Runtime Isolation | `ch27_*.py` (6) |
| IV | 28 | The Test Pyramid for Agent Security | `ch28_*.py` (7) |
| V | 29 | Red-Teaming Quill | `ch29_*.py` (10) |
| V | 30 | Continuous and Automated Red-Teaming | `ch30_*.py` (4) |
| V | 31 | Shadow Mode and Progressive Rollout for Security Controls | `ch31_*.py` (5) |
| V | 32 | Detection: Finding the Attacks That Got Through | `ch32_*.py` (4) |
| V | 33 | Incident Response for Agents | `ch33_*.py` (2) |
| V | 34 | Customers, Regulators and Disclosure | `ch34_*.py` (3) |
| VI | 35 | Evidence for the CISO and the Auditor | `ch35_*.py` (7) |
| VI | 36 | Degradation by Design: Safe Modes When a Control or a Provider Is Down | `ch36_*.py` (6) |
| VI | 37 | Framework Crosswalks | `ch37_*.py` (5) |
| VI | 38 | Securing the Multi-Agent Case | `ch38_*.py` (7) |
| VI | 39 | Evidence for the Examiner: Explaining One Payment End to End | `ch39_*.py` (3) |
| VI | 40 | Training-Time Attacks and Model Provenance | `ch40_*.py` (5) |
| VII | 41 | Operating Agent Security for Twelve Months | `ch41_*.py` (7) |
| VII | 42 | Patterns and Anti-Patterns | `ch42_*.py` (5) |
| VII | 43 | Is the Agent a Model? Model Risk and Validation for Secured Agents | `ch43_*.py` (4) |
| VII | 44 | Owning Agent Security | `ch44_*.py` (5) |
| VIII | 45 | End-to-End Case Studies | `ch45_*.py` (8) |
| VIII | 46 | The AI Security Engineer's Interview, From Both Sides | `ch46_*.py` (3) |
| VIII | 47 | The Last Twenty Percent | `ch47_*.py` (4), `bulwark/failclosed.py` |
| VIII | 48 | The Audit | `ch48_*.py` (3), `bulwark/reperform.py` |
| VIII | 49 | Where This Is Going | `ch49_durability.py`, `bulwark/predictions.py`, `results/ch49_predictions.json` |

`docs/lab-notes.md` says which `bulwark/` module and which tests belong to which chapter.

## Install and run the tests

You need Python 3.11 or newer.

```bash
git clone https://github.com/rajesh1008/securing-ai-agents.git
cd securing-ai-agents
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
```

The suite needs no API key and makes no network calls to a model. The sandbox tests in `tests/test_sandbox.py` need `bwrap` and unprivileged user namespaces; on a machine without them they are skipped.

Some lab scripts need more than the core packages (NumPy, scikit-learn, jsonschema, PyTorch, safetensors):

```bash
pip install -r requirements-labs.txt
```

## Running the live labs

The labs that call a model use Anthropic's API with **`claude-haiku-4-5-20251001`**, the model every result in the book was recorded against. A few labs also use a second model as a challenger or attacker; the chapter says which.

1. Get an API key from the Anthropic console.
2. Either export it or put it in a `.env` file at the repository root:

   ```bash
   cp .env.example .env      # then edit .env
   # or
   export ANTHROPIC_API_KEY=...
   ```

   `.env` is in `.gitignore`. Keep it that way. If you point the labs somewhere else, `BULWARK_ENV=/path/to/file` tells them which file to read.
3. Run a lab from the repository root, for example `python ch01_matrix.py`.

**The live labs cost real money.** Most runs cost cents; the larger ones (hundreds of calls) cost between a few tens of cents and about two dollars at list price, and the chapter gives the figure for each. Read a script before you run it, check its call count, and set a spending limit on your Anthropic account first. Running a live lab overwrites the matching file in `results/`; use git to get the recorded version back.

Scripts without a model call run offline and cost nothing. Where a simulation uses randomness, the chapter gives its seed.

## The Chapter 40 model files are not here, on purpose

Chapter 40 is about poisoned model checkpoints. `ch40_weights.py` builds benign and **deliberately malicious** PyTorch and pickle files and then loads them, to show which loaders execute code hidden inside a model file. The malicious payloads only write a marker file, and the script builds them in a fresh temporary directory, loads each one in a child process with a 20-second limit, and never writes them into this repository.

None of those files are committed, and `.gitignore` blocks `*.pkl`, `*.pt`, `*.bin`, `*.safetensors` and similar so they cannot be added by accident. If you run `ch40_weights.py`, run it in a throwaway container or VM, and **never load a model file you did not build or verify yourself with `pickle.load` or `torch.load(weights_only=False)`.** That is the lesson of the chapter.

The same caution applies to Chapter 27's sandbox labs, which run model-written code (inside `bwrap` where available).

## Security

See [SECURITY.md](SECURITY.md) for how to report a problem. The code is teaching code: it shows the shape of each control and is tested, but it has not been hardened or audited for production use.

## Licence

MIT. See [LICENSE](LICENSE). Copyright (c) 2026 Rajesh Ranjan Mahapatra.

The book text is not covered by this licence; only the code in this repository is.
