# 当前主程序配套固件

Python英文版：项目根目录的 `启动英文版.command`，等同于 `scripts/run.command --config config.en.toml`。保留现有记忆、双声道定位及缩小后的眼部行程。

Arduino Uno：烧录本目录 `ThreePuppets_SerialPerformance`，编译时使用本目录 `PuppetEyes` 库。临时DogSequence、DogPitchCheck、DogYawSweep不是主程序固件。

2026-11-18展厅临时配置：狗左右舵机D7禁用；该库的 `ECR_DOG_YAW_ENABLED` 默认0，初始化及运行均不attach该轴。其余功能保留。维修后经用户确认再恢复为1并编译烧录。坏舵机的电源及信号线保持断开。

当前串口 `/dev/cu.usbmodem31201`，115200，继电器HIGH启用。使用前关闭Arduino IDE串口监视器；启动后应收到READY ECR2和OK CONFIG。声音页面为 http://127.0.0.1:8765 。

停止主程序用Ctrl-C：停止音频和身体动作；已启用的眼睛舵机会继续保持最后位置，不等于切断伺服电源。

行程权威记录：`docs/hardware/current-ranges.zh.md`。直向偏移收小约5%，斜向偏移总共收小约15%，狗右眼皮最大睁开2090μs。
