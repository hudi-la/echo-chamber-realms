当前提示词与决策流程：[中文](docs/prompts-and-flow.zh.md) · [English](docs/prompts-and-flow.en.md)。
运行正文统一保存在 `prompts/zh.json`、`prompts/en.json`；修改后运行 `python -m echo.prompt_docs`，检查运行 `python -m echo.prompt_docs --check`。
英文启动：`python -m echo --config config.en.toml`，记忆使用独立的 `state-en/`。
旧版内心念头和反刍描述已由上述规范替代；历史人设目录不再由主程序载入。

# 回音室 · Echo Chamber Realms

三只木偶（Charlie 狗、Lucy 老鼠、Kaka 鸵鸟）在一个帐篷里；观众钻进去对着麦克风说话；程序直接选择接话角色，获选者生成可朗读台词。
它们的记忆整个展期累积、只因"有分量的事"而变；帐篷外的投影画它们怎么变。

```
.venv/bin/pytest -q                    # 全部测试，不调真模型
.venv/bin/python -m echo               # 跑起来；监控台 http://127.0.0.1:8765，页面上点「音频：开」
.venv/bin/python -m echo --fake        # 假脑子，看机制
.venv/bin/python -m echo --reset all --seed   # 改了人设之后：清记忆、装出厂信念
```

## 目录

| 目录 | 是什么 |
|---|---|
| `echo/` | **引擎**（现在在用的全部代码），模块见下 |
| `tests/` | 离线回归测试，使用假脑子 / 假时钟及本地 WebSocket |
| `config.toml` | 旋钮；对话/记忆配置热更新，音频/接话参数重启生效 |
| `charactor_setting/` | 人设。`v2/` 在用；根目录是原版；`v2/seeds.json` 是出厂信念。见里面的 README |
| `state/` | 运行时记忆（gitignore）：原话流水、每只的 json、变更日志、每场的星、天数 |
| `docs/` | `agent-architecture-and-prompts.md`（现在用什么）、`superpowers/specs/`（设计文档，含每次改动的来龙去脉）、`superpowers/plans/` |
| `voices/audition/` | 音色试听存档：三角色各三个候选、原版升调对照、Kaka 的 realtime 出声版 |
| `avatar/` | 头像（监控台以后可能用） |
| `legacy/` | **2024 年原版**，引擎不读。见里面的 README |

## `echo/` 模块（按数据流顺序）

```
输入            耳朵 ears.py ──────────┐          键盘 console.py ─┐
                （浏览器麦克风 audio_io.py）│                        │
                                        ▼                        ▼
房间            room.py（事件总线 · 现场记录 transcript.py · 发言锁 floor.py · 沉默计时 · 到访 session.py）
                                        │ 同一份现场记录
                                        ▼
木偶            puppet.py ×3（程序选人 → 台词 → 说；反思）
                  ├─ brain.py   模型调用（Claude / OpenAI），JSON 格式
                  ├─ prompts.py 所有喂给模型的固定文字
                  └─ memory.py  信念 / 关系 / 印象 / 念头，原子落盘，--reset
                                        │
输出            嘴 mouth.py（TTS → 升调 → 声道；浏览器播 audio_io.py）   动作 motors.py（阶段 4）
观察            monitor.py + monitor.html（作者监控台）
基础            events.py · clock.py · config.py · presence.py（"有没有人"的插口，未接硬件）
```

`__main__.py` 按上面的顺序把这些接起来。

## 还没做的

投影（三面墙）；Arduino 动作（阶段 4）；"有没有人"的硬件来源；木偶之间互相打断；realtime 直接出声那条路线（试听已存档，待定）。

## 自然语音群聊（2026-10-17）

主流程只请求获选角色 `compose`，不再请求三位角色各自 `decide`。人设和记忆保持独立。
同一事件循环内登记角色，明确的句首点名优先；否则随机选人，上一位在有其他角色时让位。
`room.turn_window = 0`，不额外等待候选窗口。获选者必须生成至少一句可朗读台词；空内容作为生成失败处理，不是角色选择沉默。
没有角色愿意说话时仍然保持沉默。人类开口会使旧候选失效，并取消尚未完成的台词准备或立即停止播放。

耳朵将 VAD 人声分段、转写完成、人类话轮结束分开：默认 600ms 停声只分段，再等 1.2 秒；期间继续说话则合并。
按 `item_id` 的开口顺序拼接转写，防止完成事件乱序。停声后最多等转写 8 秒；没有语音活动证据 12 秒则释放失联话轮。
持续有语音活动的长句没有总时长上限。活动证据使用麦克风响度，噪声/回声仍可能影响它，需要现场测试。
“嗯、好、对、不、是、停、啊”保留为有效短回答；单字“停”可在流式转写时打断。
相同于木偶台词的短插话仍可能被回声过滤误判。`confirm` 需要转写证据，达不到零延迟打断；隔离扬声器或戴耳机时可试 `immediate`。

浏览器只允许一个页面占用音频；其他页面仍能看监控。PCM 每段带 ID，页面报告 Web Audio 开始、自然结束或失败。
关闭音频/取消播放不计作说完。没有开始确认 3 秒、开始后超过音频时长加 3 秒没有结束确认，均判为失败并释放资源。
这是浏览器播放生命周期确认，不能证明扬声器确实可听见或精确到哪个汉字；打断前缀仍按确认开始后的进度估计。
麦克风输入最多积压 1 秒，转写上传队列也有界；断开清空旧帧，避免网络恢复后播放旧人声。下一句 TTS 预合成保持最多一段。
写台词 15 秒、单句 TTS 20 秒超时；异常或取消都会清理发言锁和动作状态。反刍只消费请求前的记忆快照。
音频和接话参数在启动时读取，修改后需重启。

声音现为三套基础音色、角色表演指令和不同小幅移调：Charlie 明亮俏皮（nova，+2），Lucy 轻细犹豫（shimmer，+4），Kaka 圆润自得（onyx，−1）。
这些是待试听的初稿，尚未验证实际模型输出、中文清晰度、角色辨识度或现场回声。
指令依据 [OpenAI 官方 TTS 文档](https://developers.openai.com/api/docs/guides/text-to-speech)，转写事件依据 [官方实时转写文档](https://developers.openai.com/api/docs/guides/realtime-transcription)。

单独试听（不会启动房间或改记忆；会调用收费 TTS；在本机配置 `OPENAI_API_KEY`，不要发到聊天）：

```sh
python -m echo.voice_preview --output /tmp/echo-voice-preview
```

打开输出的 `index.html`，先比较三角色读相同文本，再听角色台词。
现场依次验证：一句“好”、单字“停”、思考停顿后续说、连续说话 60 秒、播放中插话、断网/关闭音频、开两个监控页面。
检查没抢话、没卡锁、没有重复声、失败播放没写入已说完记录，再评价声音辨识度。

离线验证：`python -m pytest -q`；`node tests/browser_audio.cjs` 检查浏览器脚本及开始/结束/取消确认。
`--fake` 只替换脑子，离线演示还需临时配置 `ears.mode="console"`、`mouth.mode="off"` 并把顶层 `state_dir` 指向临时目录。
原有 `.venv` 若迁移后失效，请使用有效的 Python 3.12 环境运行，不要清理真实 `state/` 来排错。


脑子使用 ChatGPT 订阅：`config.toml` 的 `[model]` 已设置 `auth="subscription"`，角色与反刍模型为订阅账户支持的 `gpt-6.1-sol`。
先在有效的 Python 3.12 环境补齐授权依赖，再完成官方浏览器登录：

```sh
python -m pip install 'PyJWT[crypto]>=2.10,<3' 'httpx>=0.28,<1'
python -m echo.subscription login
python -m echo.subscription status
python -m echo.subscription models
```

登录使用独立的 Continue with ChatGPT 授权，不读取 Codex 或浏览器的现有 token。
凭据保存在 `~/.config/echo-chamber/subscription/`，目录权限 700、文件权限 600，不进入项目或 Git。
三个角色共享并串行刷新授权；不同账户用 `--profile NAME`，并设置 `subscription_profile`。
启动会先确认账户支持配置中的模型；授权失败、额度不足或模型不可用时不会自动切回收费 API。
订阅仍受套餐额度限制；耳朵转写与嘴巴 TTS 继续使用 `OPENAI_API_KEY` 和 API 余额。
退出运行 `python -m echo.subscription logout`。
依据 [官方订阅授权文档](https://developers.openai.com/siwc/token-sharing-open-source/sign-in) 和
[接口限制](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)。
角色人设和记忆保留；当前主流程已简化为程序选人后直接 compose。
