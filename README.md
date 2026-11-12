## 本机启动（已修复）

双击根目录的 `启动中文版.command` 或 `启动英文版.command`。也可以在终端运行 `./scripts/run.command` 或 `./scripts/run.command --config config.en.toml`。停止时按 Ctrl-C。

运行环境固定保存在 `~/.cache/echo-chamber/venv/`，不受 iCloud 按需下载影响。启动脚本会检查依赖清单，首次启动或清单变化时自动安装依赖；Python 需为 3.12 或更新版本，也可用 `ECR_PYTHON` 指定解释器。依赖以 `requirements.txt` 为准，包含实时转写所需的 `openai[realtime]`。

中文版使用 `state/`，英文版使用 `state-en/`，默认启动保留记忆。仅在明确需要清空时使用 `--reset all --seed`。

本机 `.venv` 链接到上述本地环境；原有失效环境保存在 `work/venv-before-startup-fix-20261111/`，用于回溯，程序不再读取它。不要复制虚拟环境到其他电脑；在新电脑用启动脚本重新建立。

当前已连接 UNO 的眼睛与身体动作：启动前关闭 Arduino IDE 串口监视器，双击中／英文启动入口，并在声音页面启用音频。实际播放时驱动说话角色，播放结束或打断后停止身体。端口和触发电平在 `parameters.toml` 的 `[system.serial]`，目前为 `/dev/cu.usbmodem31401`、`HIGH`。Arduino 已使用串口表演固件，旧随机演示的 G/P/T 不适用；退出主程序用 Ctrl-C。固定缓存台词测试与回退说明见 [硬件说明](docs/hardware/performance-trial.zh.md)。

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
