# Security policy

This repository is the companion code for the book *Securing AI Agents*. It is teaching code, written to show how each control works and tested to the level the book describes. It has not been audited for production use, and it comes with no warranty (see LICENSE).

## Reporting a vulnerability

If you find a security problem in Bulwark, for example a way past a gate that the book says should hold, please report it privately through GitHub's **Report a vulnerability** button on the Security tab of this repository, rather than opening a public issue. Include the script or test that shows the problem and the commit you tested against.

A bypass of a control the book describes as deterministic is the most useful kind of report. Results from the live labs that differ from the book's recorded numbers are expected, because model outputs vary; those are not vulnerabilities, though issues about them are welcome.

## Things to know before you run anything

- **API keys.** The live labs read `ANTHROPIC_API_KEY` from the environment or from a `.env` file at the repository root. Never commit `.env`; it is in `.gitignore`. If you fork this repository, keep it that way.
- **Malicious model files.** `ch40_weights.py` builds deliberately malicious pickle and PyTorch checkpoints to demonstrate code execution on load. They are created in a temporary directory and never committed. Run that script in a disposable environment.
- **Model-written code.** The Chapter 27 and 28 labs execute code a model wrote. They use `bwrap` sandboxing where it is available; on machines without it, read the script before running it.
- **Spend.** The live labs bill your Anthropic account. Set a spending limit first.
