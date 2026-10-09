[简体中文](architecture.md) | **English**

# Reading the real evidence


Kraken's public REST API provides BTC/USD trades, bid/ask quotes, candles, and trading-pair rules. A local cache coordinates the request cadence. For each question, the system first freezes the available market information, runs the models and saves their answers, then reveals the outcome using subsequent real trade prices.

The **blue route** gives the historical price path directly to Laya. The **green route** gives structured features from the same market information to Laya, records its raw prediction, then routes the final direction using a preset 15-second momentum threshold of 1.5 basis points (bps). Green represents an offline teacher-designed method combining structured inputs and a rule. It does not fine-tune Laya's weights or call GPT online. Its score reflects the combined method and rule; it cannot be attributed to stronger model weights.

The **purple route** calls `typesafe-ai/jev` through `https://ai-gateway.vercel.sh/v1/evaluate`. It sends only frozen public features. The requested model alias can be recorded, but this system has not verified the provider's internal weight version. An answer enters strict shared-round scoring only if it arrives on time and is written to the ledger. Late answers, missing responses, errors, and ties are counted separately.

Jev is optional and disabled by default. Users enter their own key directly in the local configuration page, never in chat. Enabling it makes real cloud requests and consumes their own quota; its default finite request limit is 60 calls.

Blue and green each start with **10,000 USD in virtual funds**. The system makes a direction judgment every 5 seconds and checks simulated trading intent every 30 seconds, then checks fresh quotes, fees, and risk controls. Its research assumptions are 80 bps in fees per transaction and an additional 2 bps of slippage. These are research settings, not the user's actual trading fees. **Purple has no third account.**

`apps/btc/engine.py` enforces causal timing and ledger constraints; `paper_engine.py` computes simulated execution; `jev_comparison.py` saves cloud responses; and `dashboard_state.py` uses a separate read-only connection for page refreshes. The browser displays ledger evidence; it does not generate judgment records.

Installation pins the model repository and revision, verifies downloaded files, and loads the model offline afterward. Each ledger records the method and source-code hashes. Historical scores from different versions or methods must not be mixed. The SQLite records live in the user's own `data/` directory.

The supported local platform is an Apple silicon Mac running macOS 14 or later with Python 3.12–3.13; Python 3.12 is recommended. Installation through ChatGPT / Codex requires local file and terminal access. A cloud chat session is not evidence of installation on the user's Mac. See [the installation guide](../BOOTSTRAP.en.md).

This application demonstrates collaboration among **a small model, program rules, offline teacher design, and auditable records**. It does not establish an effective investment strategy.
