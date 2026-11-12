# 台词表演试验 2026-10-21

改动前源码已独立备份到 backup/before-performance-20261021。该快照不继承包含旧密钥的历史，包含当前 Python、校准库和随机演示；运行记忆及凭据不上传。

试验分支：feature/puppet-performance-20261021。默认只打印动作日志，不打开串口。
模型同时返回 text 和 performance（target、tone、body）。表演意图目前覆盖整段回复；逐句播放时重复建立主要注视，身体强调只在第一句触发。长于7秒的犹豫句允许移开再回看。尚未实现逐词时间标记或听者的内容情绪推断。
浏览器确认 play_started 后才开始动作。句子结束、失败、打断均清掉后续动作并停止身体。听者延迟约0.4秒关注说话者，人类开口转向观众。忙碌的眼睛动作被丢弃，不排队，已经开始的动作自行完成。

## 使用

安装项目原有运行依赖，额外安装 `pip install -e '.[hardware]'`，或单独 `pip install pyserial`。

- `python -m echo.performance`：16秒固定台词动作预览，仅日志、不生成声音、不调用模型。
- `ECR_SERIAL_PORT=/dev/cu.usbmodem1401 python -m echo.performance`：固定动作实物预览，身体默认禁用。
- 正常 `python -m echo`：日志预览与真实语音同步。
- 加 `ECR_SERIAL_PORT=实际端口`：使用串口固件连接眼睛。
- 只有确认触发电平后再设置 `ECR_RELAY_ACTIVE=HIGH` 或 `LOW` 启用身体。

固件：hardware/current-20261021/ThreePuppets_SerialPerformance。必须使用同目录的 PuppetEyes 库编译，不能误用旧库；旧随机演示和已安装库保留。新增库仅增加老鼠头部控制并把继电器初始化交给固件，校准数值未改。
Arduino Uno 115200；READY ECR1 握手；LOOK 角色(鸟0/鼠1/狗2) 方向(与Gaze枚举相同) 眨眼(0/1) 缓动(0/1)。BODY 角色 毫秒(0..1200)；CONFIG HIGH/LOW；STOP；PING。
D12鸟，D13狗。2026-10-21已从旧程序puppet_gpt_project确认HIGH启动、LOW停止；固件setup先将D12/D13输出LOW，运行时仍需CONFIG启用身体。没有位置反馈，不保证直流机构停在固定位置。身体最长1.2秒，失联1.8秒关闭；Python每0.5秒发心跳。老鼠点头只在1500–1650微秒的小范围往返，尚待实物确认。

继电器电平已按旧程序确认；不自动启动真实付费语音会话。实际串口端口可能改变，固定演示可以Ctrl-C停止。

## 有声固定台词演示

`python -m echo.performance_preview --prepare` 使用当前三角色音色、移调和播放速度，调用TTS生成三句缓存音频到work/performance-audio，不启动房间或修改角色记忆。
准备完成后：`python -m echo.performance_preview --countdown 10`，先10秒倒数，再通过电脑默认音频输出播放并同步串口动作。默认使用已确认的HIGH继电器和/dev/cu.usbmodem1401，可用参数修改。狗短暂起伏、老鼠只做眼神、鸟抖动一秒。该演示使用本机pygame播放，无浏览器播放确认；动作以本机播放开始为基准，不代表逐词精确同步。
需要pygame、soundfile及现有TTS依赖。Ctrl-C或异常会停止声音和身体，缓存可反复试听而无需再次合成。

## 2026-10-21 观看反馈调整

当前规则以本节为准：仅说话者移动，取消听者自动转眼和人类开口时全体转眼。每句实际播放开始时，说话者获得一次150–1000毫秒身体提示，不再依赖body标记；鸟/狗短时通电，老鼠小幅点头后归位。语气继续影响说话者眼神。已在进行中的眼睛动作仍按驱动自然完成。接线排查期间不自动重播或启用继电器。

## 2026-10-22 待胶水干后测试的新规则（覆盖上文旧规则）

- 模型仅生成text和performance.target/tone；中英文运行提示词与严格JSON schema均已移除body。
- 只有声音实际开始播放才启动当前说话者的身体。Python每0.4秒续发1200毫秒BODY租期；播放结束、失败、插话或句间TTS等待时STOP。断开通信后即使心跳逻辑异常，未续约的身体也在最多1.2秒内停止。
- 鸟D12、狗D13仍为已确认的直流继电器（HIGH启动）。老鼠D10为点头舵机，以1500→1550→1500微秒连续三角缓动，单程650毫秒，续约不重置运动相位。停止时回1500。不使用最大行程。用户提到狗使用点头舵机与现有接线不一致，未擅自交换角色或接线；待实物测试前确认。
- 眼睛在整次发言开头先看交流对象，之后约每3.2–4.8秒安排一次移开/回看；随机眨眼、犹豫缓动。眼神在不同音频句段之间保持进度，等待语音时冻结计时。结束整次发言后清除计划，已开始的眼睛动作自然结束。
- 新固件完成眼睛动作后反馈IDLE角色编号；Python等待忙碌结束再发下一条，3秒为保守超时回退，无旧动作队列。只安排说话者动作。
- 固件握手升级为READY ECR2。旧ECR1不启用，需新Python与新固件一起测试。本轮仅离线测试和编译，未连接串口、未上传、未运动。

## 2026-11-11 实物连接

环境修复后，主程序使用 parameters.toml 的 system.serial：端口 /dev/cu.usbmodem31401，relay_active="HIGH"。同一配置供中英文启动使用；接线保持鸟D12灰线、狗D13紫线，老鼠点头D10。当前眼睛参数已同步为11月11日缩窄后的版本。

已给UNO编译上传 ThreePuppets_SerialPerformance（配套 current-20261021/PuppetEyes，含head接口）。上传后等待电脑指令，不运行随机演示。串口协议为READY ECR2、CONFIG HIGH、LOOK、BODY、STOP、PING；原随机演示的G/P/T不适用于本固件。使用主程序时关闭Arduino IDE串口监视器，避免占用端口。

Python等待READY才发送眼睛动作，等待OK CONFIG才发送身体动作；未收到配置确认时按心跳间隔重试配置。实际播放时仅说话者动作；结束或打断后STOP。主程序的声音禁用/文字模式不触发语音身体同步。目标目前根据角色舞台顺序映射为左/右/中，并未完成每只木偶看具体角色/观众的独立位置标定。尚未增加翻白眼或新的情绪动作库。

固定有声预览：`.venv/bin/python -m echo.performance_preview --countdown 5`。复用work/performance-audio中已有三句缓存，不调用模型或TTS、不修改角色记忆；缓存缺失时不会自动生成。macOS使用内置afplay播放，无需pygame；以本地播放进程启动为时间基准，没有浏览器的play_started回执。正式主程序仍使用浏览器确认播放开始后再动作。可使用--port、--relay-active覆盖配置。

回退到独立眼睛演示时，使用stable-2026-11-11-before-dialogue-motion快照内草图与库重新烧录；如仅想关闭主程序硬件，设system.serial.port=""、relay_active=""后重启。
