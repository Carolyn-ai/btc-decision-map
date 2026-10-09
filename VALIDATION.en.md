[简体中文](VALIDATION.md) | **English** | [Project home](README.en.md)

# Release validation


## Original runtime validation (v0.1.0)

Validation date: 2026-10-09. Environment: Apple silicon Mac, Python 3.12.13.

The results below describe the original v0.1.0 validation. This documentation update does not repeat model or market tests. The counts of 29 tests and 39 published files refer to that original validation, not to the current bilingual documentation release.

| Check | Observed result |
|---|---|
| Independent installation | `setup.command` completed successfully, using an independent virtual environment and pinned dependencies |
| Model download and verification | Laya revision `f2b4faf51023039425946074e2cf1361d2db11d5`; all 12 files passed verification against Hub metadata |
| Real local inference | `laya-mlx 0.2.0` / `mlx 0.32.2` loaded successfully and returned an actual choice |
| Public market data | Kraken BTC/USD trades, quotes, order book, and candles were connected; actual frozen snapshots were produced |
| Decisions and outcome checks | Both routes obtained real Laya answers, locked them before the outcome, and subsequently settled them using labels from real trades; waiting, ties, missing data, and invalid questions were retained |
| Paper accounts | Two independent ledgers produced simulated trades and fees; the ledgers persisted after stopping and restarting |
| Jev | Disabled by default in the open-source version, with no personal key configured; this installation validation sent no paid Jev requests |
| Offline tests | 29 tests covering causal scoring, storage, HTTP same-origin restrictions, and configuration confidentiality passed |
| Public files and history | The 39 release files and public commit history passed scanning; they contained no personal configuration, model caches, old ledgers, or private directory paths |
| GitHub automated checks | Offline tests, scanning, and compilation checks actually passed on Ubuntu / Python 3.12 |
| Anonymous remote clone | The public GitHub URL was cloned into another empty directory; an independent environment was recreated, and installation, model verification, public market data, and workbench checks passed |
| Live workflow in the cloned copy | Actual `locked` and `settled` records were generated; the two accounts started from records created by that copy, and the Jev call count was 0 |

The model downloader can reuse an existing cache. This validation was not a test on a new machine with an empty cache. Other Macs, network environments, and Python minor versions still require validation on the user's own machine. These runtime results establish that installation and the research workflow can run; they do not establish predictive effectiveness or profitability.

The remote-clone validation used the repository's actual files. It did not copy the development directory's environment, model files, or historical ledgers. The package manager and Hub can reuse machine caches, so this validated installation in an independent directory, without testing every operating system or download speed with an empty cache.

During the initial collection of market data, the live check returned “The workbench has not yet completed checks of real market data, model answers, and records.” After an actual answer arrived, the check was run again and passed. No preset answers were used to fill this waiting period.

The default offline tests do not send Jev requests. Jev protocol and scoring tests use explicit test fixtures; these fixtures do not appear on the runtime page and are not evidence of real market data, model results, or profitability.
