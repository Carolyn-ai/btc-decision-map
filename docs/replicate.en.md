[简体中文](replicate.md) | **English**

# A viewer's guide to rebuilding and adapting the project


Start with the copyable instruction on the [English project homepage](../README.en.md), then follow the [local installation guide](../BOOTSTRAP.en.md). This release supports an Apple silicon Mac with macOS 14 or later and Python 3.12–3.13; Python 3.12 is recommended. ChatGPT / Codex needs access to your local files and terminal to perform the installation. A cloud chat session alone does not prove that the system is running on your computer.

1. **Get the model working.** Install using the homepage instruction and inspect the actual local model diagnostic receipt. The small model accepts a clearly defined question and a limited set of choices; it is not a long-form conversational text generator.
2. **Get public data working.** Check the market source, receipt time, and freshness. Show disconnections, stale data, and clock discrepancies; do not insert fictional prices.
3. **Freeze the question.** Define the prediction target, time horizon, and information cutoff. Save the question before submitting answers so inputs cannot be changed after the outcome is known.
4. **Compare parallel routes.** Blue uses Laya directly, green improves the method, and optional purple uses Jev. All use the frozen information from the same round. Keep the green route's raw model answer and its final rule-based answer separately. Its offline teacher-designed method uses structured inputs and a preset rule; it does not fine-tune model weights or call GPT online.
5. **Build outcome records.** Label outcomes after real prices arrive. Track accuracy, coverage, on-time response rate, and errors separately. Comparisons between methods need a denominator made up of the same eligible rounds.
6. **Simulate execution.** Beyond the prediction, check fees, risk, quotes, and execution conditions. Start the virtual accounts with your own empty records. A correct direction prediction does not establish profitable trading. There are blue and green accounts; Jev has no third account.
7. **Make the map understandable.** Let viewers open each step to inspect its real input, decision, latency, and outcome. Label historical playback as such. Drive animation from ledger events.
8. **Try your own use case.** Replace the decision question with, for example, “Is there enough information?”, “Which department should receive this ticket?”, or “Should this process be paused?” Define a correct answer or a human review process first, then test on future samples.

## Optional Jev configuration

Jev is disabled by default. The blue and green routes can run without its API key. To add the purple route, open `configure.command` and enter your own key directly in the local configuration page. Do not paste it into chat or commit it to GitHub. Enabling Jev makes real cloud requests and consumes your own quota; the default request limit is 60 calls. Change the limit deliberately and restart the workbench after saving.

## Reading the current Chinese interface

The dashboard and configuration page currently use Chinese labels. These are the main controls:

| Visible label | Meaning |
|---|---|
| 暂停画面 | Pause the display; this does not stop model requests |
| 看上一轮 | View the previous round |
| 放大这一段 | Focus and enlarge this part of the map |
| 下载原始记录 | Download the saved records |
| 启用 Jev | Enable Jev using your own cloud credits |
| Jev 累计请求上限 | Cumulative Jev request limit |
| 工作台端口 | Local dashboard port |
| 保存本机配置 | Save local configuration, then stop and restart the dashboard |

## Working with ChatGPT / Codex

You can ask:

> Explain why the three routes disagreed in this round. Cite the saved inputs, raw answers, rule-based route, and actual outcome. Do not call a model again to fill in historical answers.

> Try changing the green route's inputs in a new version. Preserve the old version and freeze the new method. Design a comparison on future shared rounds; do not mix the new method's scores into the original ledger.

> Investigate why the workbench has no new records. Check the model, market freshness, permissions, quota, and ledger writes in turn. Preserve the actual errors.

Model installation and data interfaces provide the foundation. Organizing the questions, rules, evidence, and feedback turns them into a reusable decision application.

For implementation details, read [the architecture guide](architecture.en.md). For failures, see [troubleshooting](troubleshooting.en.md).
