# legacy —— 2024 年原版（2026-02-06 提交的基线）

新引擎（`echo/`）**不读这里的任何文件**。留着是为了：查当年的做法、串口协议、日志。

| 文件 | 当年是什么 | 新引擎里对应的东西 |
|---|---|---|
| `tools.py` | 人设读取、头像、OpenAI TTS（tts-1）+ librosa 升调 + pygame 分声道、串口 1~6 | `echo/mouth.py`（沿用音色/升调/声道）、`echo/motors.py`（阶段 4 沿用串口协议：1/2/3 开始动、4/5/6 停） |
| `chat_agents.py` | ChatAgent：一个 system + 固定轮流、gpt-3.5-turbo | `echo/puppet.py` + `echo/brain.py` |
| `gallery_scene.py` | 展厅现场版 Streamlit：模块级 `while True`，三只无限轮流，出声 | `echo/__main__.py` + 监控台 |
| `multi_agent_1.py` | 同上，不出声 | 同上 |
| `multiple_agent_conversation.py` | 终端版无限轮流 | 同上 |
| `playground.py` | 试验草稿（含注释掉的串口测试） | —— |
| `sound_tool.py` | 空文件 | —— |
| `history` / `history_may` | 2024 年现场运行日志（`history_may` 是 5 月那版的） | `state/transcript.jsonl` |
| `ConversationSample.txt` | 早期对话样本 | —— |
| `invalid/` | 更早的试验（_elisa、_simple_chatbot…） | —— |

注意：`tools.py` 里有一个写死的 OpenAI key，已作废（2026-09-25 验证 401），但它跟着 git 历史公开过。
