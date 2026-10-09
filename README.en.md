[简体中文](README.md) | **English**

# BTC Decision Map

Use real public market data to compare **Laya, Laya with an offline teacher-designed method, and Jev**. Run a local dashboard to inspect decisions, verify outcomes, and track two paper accounts.

## Copy this into ChatGPT to get started

**Recommended: an Apple silicon Mac and a ChatGPT / Codex environment with access to your local files and terminal.** A local Codex task can perform the installation. You must authorize the required access. First-time setup requires internet access and about 2 GB of free space. Use macOS 14 or later and Python 3.12–3.13; Python 3.12 is recommended.

Copy this complete prompt to start the installation task:

```text
Install and start BTC Decision Map on my computer:
https://github.com/Carolyn-ai/btc-decision-map

First confirm that you can access my local files and terminal. Clone the repository into a new writable directory, check out v0.1.1, and read README.en.md, AGENTS.md, AGENTS.en.md, and BOOTSTRAP.en.md. Follow the guide to install dependencies, download and verify Laya, connect to real public market data, and start the dashboard.
If a Jev API key is needed, open the local configuration page so I can enter it myself. Do not ask me to send secrets in chat. If I do not have a key, start the two Laya routes first. Preserve existing configuration and records. Keep real errors and fix their actual causes. Finally, open the dashboard and report which checks passed, what is still pending, and how to start and stop it later.
```

If your current chat cannot operate your computer, switch to an environment with local file and terminal access. Running something in a cloud chat container does not install it on your Mac. You still need to approve local permissions and enter your own API key when applicable.

## What you need

| Feature | Required configuration |
|---|---|
| Kraken public BTC/USD market data | No exchange API key |
| Blue: ask Laya directly | The installer downloads the local model; no API key |
| Green: teacher-designed method | The same local Laya with structured inputs and preset rules; no GPT API key |
| Purple: Jev cloud decisions, optional | Your own Vercel AI Gateway key, model access, and available credits |

**Jev is disabled by default.** Enabling it uses your own cloud credits. The default cumulative request limit is 60. The blue and green routes and the map work without Jev. Late responses, API failures, and pending results remain visible.

## Manual setup

```sh
git clone https://github.com/Carolyn-ai/btc-decision-map.git
cd btc-decision-map
git checkout v0.1.1
./setup.command
./start.command
```

The dashboard opens at `http://127.0.0.1:8780/` by default. Allow about 60 seconds to collect an initial window of real market data before expecting new decisions and results. Statistics remain empty until there are samples.

Optional: run `./configure.command`, enter your own Jev key and request limit in the local page, save, then run `./stop.command` and `./start.command` to apply the settings.

For later sessions, double-click `start.command` to start and `stop.command` to stop. Your records are stored in `data/`; personal configuration is stored in `.env`. Both are excluded from Git.

The dashboard and local configuration page currently use Chinese labels. This release provides English documentation and installation instructions. The [replication guide](docs/replicate.en.md) explains the stages and their meaning.

## Understand the three routes

- **Blue:** local Laya predicts whether BTC/USD will rise or fall over the next five seconds.
- **Green:** an offline teacher-designed method. Laya first answers a question based on structured market features; a preset rule overrides the direction when strong 15-second momentum reaches its threshold. This is not a separately fine-tuned set of model weights, and GPT is not called during live execution.
- **Purple:** Jev answers a direction question using the same frozen public market information through Vercel AI Gateway. It records decisions and has no third paper account.

Strict three-way scores include only shared questions with answers saved before the deadline and eligible real outcome labels. Blue and green have separate paper accounts. Fees, slippage, and risk limits are research assumptions. Directional accuracy does not establish profitability after costs.

This is a research and paper-trading project using public market data. It does not connect to real trading accounts or submit real orders.

## Learn more

- [Local installation guide for ChatGPT / Codex](BOOTSTRAP.en.md)
- [Replication and customization guide](docs/replicate.en.md)
- [Data, models, and scoring](docs/architecture.en.md)
- [Troubleshooting](docs/troubleshooting.en.md)
- [What was actually validated](VALIDATION.en.md)
- [Model and dependency sources](THIRD_PARTY.en.md)

Developed and shared by 灵姐说 AI / Ling Talk AI. Model weights retain their source licenses and are downloaded from the specified repository during setup.
