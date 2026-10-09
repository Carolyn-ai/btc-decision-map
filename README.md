# BTC 决策地图

用真实公开行情，对比 **Laya、教师方法改进后的 Laya、Jev**，在本机展示判断过程、结果核对与虚拟账户。

## 复制到 ChatGPT，开始安装

**推荐：Apple 芯片 Mac → ChatGPT 桌面端 → Codex → 本地任务。** 需要允许访问安装目录和终端；首次安装需要联网和约 2 GB 可用空间。Python 3.12–3.13，推荐 3.12。

复制下面这一段即可启动整个安装任务：

```text
请在我的本机安装并启动 BTC 决策地图：
https://github.com/Carolyn-ai/btc-decision-map

先确认你能访问我的本机文件和终端。在新的可写目录克隆仓库，检出 v0.1.0，阅读 README.md、AGENTS.md 和 BOOTSTRAP.md，然后按指南安装依赖、下载并验证 Laya、接入真实公开行情、启动工作台。
需要 Jev Key 时，打开本机配置页让我填写，不要让我把密钥发到聊天中。没有 Key 就先启动 Laya 两路。保留已有配置与记录，遇到错误按真实原因修复。最后打开网页，报告通过的检查、等待中的步骤及以后如何启动和停止。
```

如果当前聊天不能操作本机，先切换到具有本机文件和终端权限的环境。普通网页聊天的云端运行结果不代表已安装到你的电脑。首次权限授权和填写个人 Key 仍需要你完成。

## 你需要准备什么

| 功能 | 需要的配置 |
|---|---|
| Kraken BTC/USD 公开行情 | 无需交易所 Key |
| 蓝色：直接问 Laya | 安装程序下载本机模型，无需 API Key |
| 绿色：教师方法改进 | 同一个本机 Laya＋结构化输入＋预设规则，无需 GPT API Key |
| 紫色：Jev 云端判断（可选） | 自己的 Vercel AI Gateway Key、可用权限及额度 |

**Jev 默认关闭。** 启用后会消耗你的云端额度，默认累计请求上限 60 次。关闭或未配置时，蓝绿两路和地图仍可运行。页面保留真实的迟到、接口错误与等待状态。

## 也可以自己启动

```sh
git clone https://github.com/Carolyn-ai/btc-decision-map.git
cd btc-decision-map
git checkout v0.1.0
./setup.command
./start.command
```

工作台默认打开 `http://127.0.0.1:8780/`。首次启动约需 60 秒积累真实行情，再产生新的判断和结果。没有样本时，统计为空。

可选：运行 `./configure.command`，在本机网页填写 Jev Key 和调用上限，保存后运行 `./stop.command`、`./start.command`。

以后双击 `start.command` 启动，双击 `stop.command` 停止。文件夹内的 `data/` 保存你自己的记录；`.env` 保存个人配置。二者均不提交 Git。

## 三路比较怎样理解

- **蓝色**：Laya 在本机回答未来五秒涨跌。
- **绿色**：离线教师设计的判断方法。Laya 先回答结构化特征题；强 15 秒动量达到预设门槛时，固定规则覆盖方向。它不是另一个训练后的模型权重，也没有在线 GPT 调用。
- **紫色**：Jev 经 Vercel AI Gateway 回答相同冻结行情中的方向题。当前只记录决策，不设第三个虚拟账户。

三路严格同题成绩仅包含事前保存、按时作答且真实标签合格的共同题。蓝绿分别使用独立虚拟账户；费用、滑点与风控是研究假设。判断胜率不等于扣费后盈利。

这是研究与虚拟交易项目，只接入公开行情。程序不连接真实交易账户，也不提交真实订单。

## 继续了解

- [ChatGPT 安装执行指南](BOOTSTRAP.md)
- [观众复刻与修改手册](docs/replicate.md)
- [数据、模型与计分说明](docs/architecture.md)
- [常见问题](docs/troubleshooting.md)
- [实际验证范围](VALIDATION.md)
- [模型与依赖来源](THIRD_PARTY.md)

开发与分享：灵姐说 AI / Ling Talk AI。模型权重按来源许可证使用，安装时从指定仓库获取。
