[简体中文](troubleshooting.md) | **English**

# Troubleshooting


Supported platform: Apple silicon Mac, macOS 14 or later, and Python 3.12–3.13 (3.12 recommended). Follow the [local installation guide](../BOOTSTRAP.en.md) for a full check.

| Symptom | What to check and do |
|---|---|
| ChatGPT provides commands but cannot execute them | Enter a local task in the Codex desktop app and confirm local file and terminal permissions. A cloud chat session alone does not prove local installation. |
| Python cannot be found | Install official Python 3.12. Python 3.14 is not supported by this release. |
| Hugging Face or PyPI downloads fail | Preserve the connection error, check the network, and rerun `setup.command`. Existing downloaded files can be reused. |
| Model verification fails | Rerun the downloader. Do not skip verification and report a complete installation. |
| The port is occupied | Change the port with `configure.command`; run `stop.command` before `start.command`. |
| The page initially has no statistics | Wait about 60 seconds for a fresh market window, then inspect the actual records. |
| There are still no model predictions | Run `.venv/bin/python scripts/doctor.py --model --market --live` and inspect the actual model or market error. |
| Jev is not configured | Continue with blue and green. Jev is optional and disabled by default. To use purple, enter your own key directly in the local configuration page. Never paste it into chat. |
| Jev returns HTTP 401, 403, or 402 | Check authentication, model permissions, and quota as appropriate. Free quota is not guaranteed to support the request; inspect the provider account's actual status. |
| Jev reaches its request limit | Review your own usage, then increase the finite limit in the configuration page and restart. Preserve old records. The default is 60 calls; enabled requests consume your own quota. |
| A network response arrives late | Record it as late and exclude it from strict shared-round scores. Do not submit a replacement answer afterward. |

Diagnostic receipts and logs are stored in local `data/`. When sharing a failure, provide only the necessary error summary and hide keys and personal paths. Do not submit the entire ledger or configuration file.

If the routes or accounts seem confusing, see [the architecture guide](architecture.en.md): green uses an offline teacher-designed method and a preset rule, not fine-tuned weights or online GPT answers; Jev does not have a third virtual account.
