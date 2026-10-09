[简体中文](BOOTSTRAP.md) | **English**

# Local installation guide for ChatGPT / Codex


Follow these steps in order. Use actual results as evidence at every step. When an action requires permission, the user grants it in the application.

Supported platform: **Apple silicon Mac, macOS 14 or later, Python 3.12–3.13 (3.12 recommended).** Installation requires access to the user's local files and terminal. An ordinary cloud chat cannot establish that anything has been installed on the user's Mac.

1. **Confirm local execution.** Check writable directories, terminal access, Darwin/arm64, and macOS 14 or later. If local access is unavailable, explain how to enter a local task in the Codex desktop app. A cloud container is not the user's Mac.
2. **Choose a new directory and clone the repository.** This public repository does not require a GitHub token. Run `git clone https://github.com/Carolyn-ai/btc-decision-map.git`, then check out `v0.1.1`. If the directory already exists, inspect its origin and version first. Do not overwrite files or clear records.
3. **Read this guide and [AGENTS.en.md](AGENTS.en.md).** The task is to run the released version. Use its installation tools first; do not rewrite the decision engine during installation.
4. **Prepare Python.** Use Python 3.12–3.13; 3.12 is recommended. If Git or Python is missing, explain what is needed and what installing it changes, then use official sources. Respect local permission settings; do not disable the sandbox or system protections.
5. **Run `./setup.command`.** It creates an independent `.venv` in the repository, installs pinned dependencies, downloads pinned Laya weights, verifies the files against Hub metadata, and checks the local model and public market data. Do not link another project's environment. Preserve actual network errors. After connectivity is restored, rerunning setup can reuse downloaded files.
6. **Start with the routes that need no API key.** Run `./start.command` and open the local URL it actually returns. The initial fresh market window takes about 60 seconds. Inspect `health`, `signal.rounds`, and `jev_comparison` in `/api/btc/state`. HTTP 200 alone does not prove that a model answered. Wait for at least one locked or settled round, or report why it is still waiting.
7. **Ask whether the user wants to enable Jev.** Jev is optional and disabled by default; complete the blue and green routes even if it remains disabled. To enable it, run `./configure.command` and have the user enter their own key directly in the local configuration page, with a finite request limit. The default limit is 60 calls. Never ask them to paste the key into chat, a terminal command, or public material. The configuration page does not return the key, and inspecting the password field is unnecessary. After saving, stop and restart the workbench in this directory. Explain that enabling Jev sends real cloud requests and consumes the user's own quota.
8. **Verify real operation.** Run `.venv/bin/python scripts/doctor.py --model --market --live`; compare the page with an actual round record. Check real Jev request records only after the user chooses to enable it. Show authentication, quota, permission, and rate-limit errors honestly. Do not fabricate answers, submit retrospective answers to expired rounds, or merge someone else's historical statistics.
9. **Hand over the result.** Open the workbench and report its local directory, access URL, verified items, and pending items. Explain the purposes of `start.command`, `stop.command`, and `configure.command`. Preserve the user's own ledger.

## Recovery and updates

- Before a later launch, run `.venv/bin/python service.py status` to avoid duplicate processes.
- Stop and restart after changing configuration. If another service occupies the port, change this project's port.
- Before upgrading, stop the service and preserve `.env` and `data/`. Read the migration notes before switching to a specific release tag. Do not automatically delete history.
- `data/doctor-last.json` is the actual diagnostic receipt; `data/workbench.log` is the local runtime log. Hide keys and unnecessary personal paths when summarizing them.
- This project does not automatically install a service that runs at startup. If the user separately requests persistent background operation, explain how to start and stop it first.

## Model roles to preserve

The blue route uses Laya directly. The green route uses an offline teacher-designed method with structured inputs and a preset rule; it does not fine-tune Laya's weights or call GPT online. The optional purple route uses Jev. There are two virtual accounts, for blue and green; Jev has no third account. See [the architecture guide](docs/architecture.en.md).
