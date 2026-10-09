**简体中文** | [English](THIRD_PARTY.en.md)

# 模型、接口与来源

本应用整理自 BTC-SENTINEL 交接工作台及后续三路比较开发，公开版增加独立配置、安装、模型下载校验和操作指南。界面与程序用于研究、讲解及虚拟交易。

- Laya 原始模型和代码：Convai Innovations 与贡献者，[原始项目](https://github.com/NandhaKishorM/laya)。
- 本版 MLX 模型：[aac6fef/laya-multilingual-mlx](https://huggingface.co/aac6fef/laya-multilingual-mlx)，revision `f2b4faf51023039425946074e2cf1361d2db11d5`。模型卡标注 Apache-2.0；下载时保留来源的 LICENSE、NOTICE 和导出信息。本应用未训练或修改模型权重。
- MLX 运行库：[laya-mlx](https://github.com/mizorewww/laya-mlx)，固定包版本 0.2.0；[MLX](https://github.com/ml-explore/mlx) 固定 0.32.2。各依赖以自身许可证为准。
- 公开行情：[Kraken Public REST](https://docs.kraken.com/api/docs/rest-api/get-recent-trades/)。接口可用性和使用条件以提供方为准。
- 可选 Jev：[Vercel AI Gateway Evaluation](https://vercel.com/docs/ai-gateway/modalities/evaluation)，别名 `typesafe-ai/jev`。Key、访问权限、额度均由使用者自行配置；本仓库不提供凭证或额度。

仓库许可证覆盖应用代码与文档；外部模型、依赖与接口的权利和使用条件保留。
