[简体中文](THIRD_PARTY.md) | **English** | [Project home](README.en.md)

# Models, APIs, and sources


This application was assembled from the BTC-SENTINEL handoff workbench and the subsequent development of the three-route comparison. The public version adds independent configuration, installation, model download verification, and operating guides. The interface and application are intended for research, explanation, and paper trading.

- Original Laya model and code: Convai Innovations and contributors, [original project](https://github.com/NandhaKishorM/laya).
- MLX model used in this version: [aac6fef/laya-multilingual-mlx](https://huggingface.co/aac6fef/laya-multilingual-mlx), revision `f2b4faf51023039425946074e2cf1361d2db11d5`. The model card identifies its license as Apache-2.0; the download retains the source LICENSE, NOTICE, and export information. This application has not trained or modified the model weights.
- MLX runtime: [laya-mlx](https://github.com/mizorewww/laya-mlx), pinned package version 0.2.0; [MLX](https://github.com/ml-explore/mlx), pinned version 0.32.2. Each dependency remains subject to its own license.
- Public market data: [Kraken Public REST](https://docs.kraken.com/api/docs/rest-api/get-recent-trades/). API availability and terms of use are determined by the provider.
- Optional Jev: [Vercel AI Gateway Evaluation](https://vercel.com/docs/ai-gateway/modalities/evaluation), alias `typesafe-ai/jev`. Users configure their own key, access permissions, and allowance; this repository provides neither credentials nor allowance.

The repository license covers the application code and documentation. The rights and terms of use of external models, dependencies, and APIs remain in effect.
