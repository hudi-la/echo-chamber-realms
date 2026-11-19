## 本机启动（已修复）

双击根目录的 `启动中文版.command` 或 `启动英文版.command`。也可以在终端运行 `./scripts/run.command` 或 `./scripts/run.command --config config.en.toml`。停止时按 Ctrl-C。

运行环境固定保存在 `~/.cache/echo-chamber/venv/`，不受 iCloud 按需下载影响。启动脚本会检查依赖清单，首次启动或清单变化时自动安装依赖；Python 需为 3.12 或更新版本，也可用 `ECR_PYTHON` 指定解释器。依赖以 `requirements.txt` 为准，包含实时转写所需的 `openai[realtime]`。

中文版使用 `state/`，英文版使用 `state-en/`，默认启动保留记忆。仅在明确需要清空时使用 `--reset all --seed`。

本机 `.venv` 链接到上述本地环境；原有失效环境保存在 `work/venv-before-startup-fix-20261111/`，用于回溯，程序不再读取它。不要复制虚拟环境到其他电脑；在新电脑用启动脚本重新建立。

当前已连接 UNO 的眼睛与身体动作：启动前关闭 Arduino IDE 串口监视器，双击中／英文启动入口，并在声音页面启用音频。实际播放时驱动说话角色，播放结束或打断后停止身体。端口和触发电平在 `parameters.toml` 的 `[system.serial]`，目前为 `/dev/cu.usbmodem31401`、`HIGH`。Arduino 已使用串口表演固件，旧随机演示的 G/P/T 不适用；退出主程序用 Ctrl-C。固定缓存台词测试与回退说明见 [硬件说明](docs/hardware/performance-trial.zh.md)。

声音按现场位置输出双声道：狗 Charlie 为左 100%／右 0%，鸟 Kaka 为左 0%／右 100%，老鼠 Lucy 为左右各 50%。中英文版共用此布局，比例在 `parameters.toml` 的 `mouth.pan` 中设置。更新后刷新声音页面；电脑输出需选择连接两个音响的立体声设备，并关闭系统的单声道音频。

## 展厅文字形体与独立内心

正式展厅地址：http://127.0.0.1:8765/?display=1#exhibition 。此页面直接订阅主程序的实时 WebSocket：角色自己的感受与意图生成文字群，真实台词先以角色颜色显示在底部，结束后由句首牵引汇入粒子群。保留三维鸟群、物理拖尾、分色海浪、星空与自动视觉降级。

`display=1` 是独立显示模式，不自动开启声音或麦克风，也不会抢占已运行的声音页面。原来的 http://127.0.0.1:8765/ 继续用于声音、麦克风和调试；如果要同一页面负责声音和展厅，用不带 `display=1` 的 `/#exhibition`。按 F 或点“开全屏”进入全屏，D 切换调试视图。8878 仅为示例预览，正式展厅使用 8765。

每个角色独立后台生成简短内心，不参与选人，台词和播放不等待结果。内心按角色保存为 `private_thoughts`，只有自己的最近记录进入自己的 situation；网页可读取它们用于视觉，公共对话记录不包含内心。开关是 `rules.toml` 的 `memory.private_thoughts_enabled`；保留数量、提示词数量、字符上限及请求超时在 `parameters.toml` 的 `system.thoughts` / `system.model`。长期信念反刍仍关闭。新增后台请求会增加模型用量，真实延迟需现场验证。

视觉预览：双击 `scripts/preview-exhibition.command`，保持窗口打开，访问 http://127.0.0.1:8878/#exhibition 。使用 HTTP 地址，避免应用内本地文件链接无法加载。预览使用明确标注的示例文字，不连接主程序，不调用模型，不播放声音。预览提供 30 / 60 / 120 / 180 条全英文样例彩带、帧率显示，以及 Flock behavior / glow 中的 Spacing、Gathering、Wandering 调节。可点击三组对话和 Interrupt，也可自动演示。拖动粒子区域旋转三维视角，滚轮缩放，双击复位。

每句话是一条完整的文字带，保留角色感受或意图里的空格、标点和词序，不再拆成单字母。三种颜色保留文字来源。背景为黑色，感受文字的中英文情绪关键词映射为不同颜色与节奏的光晕；该视觉映射不增加模型请求。光晕预先绘入句子纹理，高句数时降低绘图分段数，物理链条精度保持不变。每句话的句首使用真实三维鸟群规则飞行；同角色句首有更强的聚合与对齐，同时保留避让距离和独立游走，形成三个可相互穿插、分散再聚合的群体。后部是固定长度的 Verlet 物理链条，受惯性、重力、空气阻力和弱弯曲刚度影响，由句首牵引回摆与缠绕；没有独立的三个实体、连接管或颜色注入。公开的 target / tone 改变共同流场的扰动位置与强度，打断后扰动缓慢消退，已有文字仍持续交融。视觉上的交融不会让 agent 读取别人的私下感受。主程序传入真实台词参数，预览按钮仅用于演示。

# Echo Chamber Realms

**An interactive art installation by [Hu Di](https://hudiworks.com/), first exhibited in April 2024.**

[View the artwork, photographs & video →](https://hudiworks.com/works/echo-chamber-realms/)

![Visitors gather among Kaka the ostrich, Lucy the mouse, and Charlie the dog in the 2024 installation.](https://hudiworks.com/images/echo-chamber-realms/K1737141840328852948340893964359_7J7A1300.jpg)

## Three characters, an ongoing conversation

Charlie the dog tries to earn affection by being clever, useful, and loyal. Kaka the ostrich is certain she deserves love because she is exceptional. Lucy the mouse keeps herself hidden so she cannot be hurt. Each puppet is driven by a language-model agent with a different way of seeking affection and protecting itself. Their conversations unfold through interaction rather than following a fixed script.

Visitors enter a miniature city assembled from recycled materials, encounter the puppets mid-conversation, and can join through a screen. The installation brings language, movement, sound, and physical space together, inviting people to witness relationships taking shape and recognize familiar patterns within them.

## Relationships between machines, and what we see in them

During exhibitions, Charlie and Kaka sometimes met Lucy’s withdrawal with persistent encouragement, then began competing for recognition. Some visitors became protective of Lucy. These encounters inform the work’s questions: what makes us perceive a relationship between AI characters? What happens when we recognize ourselves in their interactions, or encounter a response we did not expect?

Echo Chamber Realms explores both the social meaning of relationships among artificial agents and how witnessing or participating in their encounters might open new ways of understanding relationships.

![Kaka, Lucy, and Charlie around the miniature city in the 2024 installation.](https://hudiworks.com/images/echo-chamber-realms/C1737148308439854721636943943751_905ed02d8bf0d194f8d91f3ef7fdc11a.jpg)

## The software

This repository contains the installation’s conversational system and its ongoing development: character prompts, agent interaction, memory, speech, and interfaces connecting the conversation to the physical work. The current version develops voice interaction and persistent character memories; the original 2024 implementation is preserved in `legacy/`.

- [Current engine](https://github.com/hudi-la/echo-chamber-realms/tree/main/echo)
- [English guide to prompts and interaction flow](docs/prompts-and-flow.en.md)
- [Original 2024 implementation](https://github.com/hudi-la/echo-chamber-realms/tree/main/legacy)

For the full artistic context and exhibition documentation, visit the [project page](https://hudiworks.com/works/echo-chamber-realms/).

当前眼部行程：见 [2026-11-18 行程总表](docs/hardware/current-ranges.zh.md)。直向收小5%，四个斜向收小15%；需编译并上传配套固件后才在板上生效。
