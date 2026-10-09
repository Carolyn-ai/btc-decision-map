[简体中文](AGENTS.md) | **English** | [Project home](README.en.md)

# BTC Decision Map: execution conventions


- For the first installation, read README.en.md and BOOTSTRAP.en.md; use the project's programs to perform the defined operations.
- Use an independent directory, environment, model location, and ledger. Preserve existing files and user configuration.
- Connect only to public market data and paper accounts. Do not add live-trading credentials, transaction signing, or order-placement APIs.
- Users enter their keys through the local configuration interface. Do not read or output actual keys, echo password fields, or commit `.env`, ledgers, logs, or caches.
- Enabling Jev must be the user's choice, using their own allowance and an explicit limit. Installation, model downloads, unit tests, and the default doctor do not call paid models.
- Preserve real network errors, late results, missing labels, ties, and waiting states separately. Do not fabricate a successful display.
- Record the original Laya output and the output after the green route's rules separately. Do not describe this as fine-tuned weights or an online GPT answer.
- Upgrades or reinstallation must not clear the ledgers. Do not automatically increase the call allowance.
- After fixes, run tests appropriate to the changes. Before publication, run `python3 scripts/public_scan.py`.
- This project does not require subagents. Follow the current user task and local execution permissions.
