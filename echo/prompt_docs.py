"""Generate reviewable bilingual prompt specifications from the runtime catalog.

python -m echo.prompt_docs          # update docs
python -m echo.prompt_docs --check  # fail if documentation has drifted
"""
import argparse
from pathlib import Path
from .prompts import ROOT, catalog, persona


def render(language):
    d = catalog(language)
    zh = language == 'zh'
    lines = []
    def add(value): lines.append(value)
    def block(value): add('```text\n' + value + '\n```')
    add('# 回音室提示词与决策流程' if zh else '# Echo Chamber Realms prompts and decision flow')
    add('运行规范，2026-10-18。提示词正文直接来自程序读取的同一份语言目录。个人历史按当前角色设定载入。' if zh else 'Runtime specification, 2026-10-18. Prompt text comes from the same language catalog read by the application. Personal histories are loaded from the current character settings.')
    add('台词和反刍均使用通过独立订阅授权调用的 `gpt-6-luna`，思考量为 `low`；两种请求均已实测。脑子失败不会切换到收费 API。' if zh else 'Dialogue and reflection both use `gpt-6-luna` through separate subscription authorization, with reasoning effort `low`; both request types have been tested. Brain failures never fall back to the paid API.')
    add('## 流程与信息拼接' if zh else '## Flow and request assembly')
    add('每次开机先注入一次预设开场问题，作为对话输入；音频重连不会重复注入。' if zh else 'Each startup injects the preset opening question once as dialogue input; audio reconnection does not repeat it.')
    block(d['opening'])
    add('角色背景＋当前信念＋最近 N 条现场记录 → 程序直接选人 → 选中的角色写台词 → TTS 播放。人类开口优先。选中的角色必须生成至少一句可朗读台词，不再决定是否开口。' if zh else 'Character background + current beliefs + the latest N events → code selects one character directly → that character writes dialogue → TTS plays it. Human speech takes priority. The selected character must produce at least one spoken sentence and does not decide whether to speak again.')
    add('不请求模型判断 speak。事件同轮登记可接话角色，单一明确的句首点名（含常用名字别称）优先；否则随机选择，上一位在有其他人时让位。多人点名或无法确定时使用随机规则。当前 turn_window=0，无定时候选等待。非空字符串由 schema 约束；空白、纯标点或只有动作描述会被本地校验判为生成失败，不当作角色选择沉默。失败不生成假台词，等待下一次事件或安静重试。' if zh else 'Do not request a model speak decision. Register available characters in the same event-loop turn. An unambiguous opening name or supported alias takes priority; otherwise choose randomly, with the last speaker yielding when others are available. Multiple names or uncertain addresses use the random rule. Current turn_window=0 adds no timed candidate wait. The schema requires a nonempty string; local validation rejects whitespace, punctuation-only output, and stage directions without speech as generation failures, not chosen silence. Failures create no fabricated dialogue and wait for the next event or quiet retry.')
    add('### 新版每种用途的信息' if zh else '### Information used in the new requests')
    add(('''| 用途 | 角色背景部分 | 本次任务部分 | 输出 |
| --- | --- | --- | --- |
| 程序选人 | 无模型请求 | 事件、点名、上次发言者 | 获选角色 |
| 写台词 | 身份＋个人历史＋策略＋环境＋当前信念 | 获选时的现场快照＋写台词要求 | text |
| 反刍 | 同上 | 自上次成功反刍以来未消化的实际对话＋反刍场景＋反刍要求 | 信念变化 |
| 初始化 | 语言目录中审定的初始信念 | 仅为空白信念安装预设，无模型请求 | 初始信念存盘 |
| 配音 | 对应角色的声音要求 | 已生成的台词；音色、移调和声道由配置指定 | 音频 |''' if zh else '''| Use | Character background | Task input | Output |
| --- | --- | --- | --- |
| Select speaker in code | No model request | Event, opening address and last speaker | Selected character |
| Compose dialogue | Identity + history + strategies + environment + current beliefs | The situation snapshot at selection + composition task | text |
| Reflect | Same background | Unprocessed actual dialogue since the last successful reflection + review context + reflection task | Belief changes |
| Initialize | Reviewed initial beliefs in the language catalog | Install presets for blank beliefs only; no model request | Saved initial beliefs |
| Synthesize speech | Character voice instructions | Generated dialogue; voice, pitch and channel settings come from configuration | Audio |'''))
    add('短期窗口 N 由 room.window 配置，当前为 24。每条现场记录包含说话者和说出的内容；被打断时只记实际说出的部分，并标记打断。不是只取人类的话。' if zh else 'The short-term window N is room.window, currently 24. Events include the speaker and spoken content; interruptions include only the estimated spoken prefix and an interruption marker. The window includes puppet dialogue as well as human speech.')
    add('### 旧版对照 仅用于理解迁移' if zh else '### Previous design for migration reference only')
    add(('''| 用途 | 角色背景部分 | 本次任务部分 |
| --- | --- | --- |
| 判断要不要开口 | 人设＋当前记忆＋通用规则 | 现场记录 |
| 写台词 | 同上，仍包含通用规则 | 现场记录＋刚才的感受、意图＋台词要求 |
| 反刍 | 同上，仍包含通用规则 | 现场记录＋积累的念头、未说出口的话＋反刍要求 |
| 生成初始信念 | 人设＋通用规则 | 初始信念要求 |''' if zh else '''| Use | Previous character background | Previous task input |
| --- | --- | --- |
| Decide | Persona + saved memory + shared rules | Recent events |
| Compose | Same, including shared rules | Recent events + generated feelings and intentions + composition task |
| Reflect | Same, including shared rules | Recent events + private thoughts and unspoken intentions + reflection task |
| Generate initial beliefs | Persona + shared rules | Belief generation task |'''))
    add('当前停声检测为 600ms；停声后的续说宽限为 1.2 秒，待本轮转写齐全后提交。程序选人及写台词的实际耗时进入调试日志；模型与语音合成耗时仍会波动。' if zh else 'Current end-of-speech detection is 600ms, followed by a 1.2-second continuation grace period; submit once turn transcripts are complete. Selection and composition timings appear in debug logs. Model and speech synthesis latency can still vary.')
    add('访客在场时，安静重试间隔为 3 秒（独处时仍为 120 秒）。仅在没有角色发言或生成失败后重试；获选者不再有正常选择空台词的出口。安静提醒不会重启进行中的选人或写台词；访客开口取消旧准备。' if zh else 'While a visitor is present, retry after 3 seconds of silence (120 seconds when alone). Retry when no character is speaking or generation failed; selected characters no longer have a normal empty-dialogue option. Quiet reminders do not restart selection or composition; visitor speech cancels old preparation.')
    add('浏览器 TTS 模式先启动网页，等唯一声音页面确认音频已就绪后才发布开机事件并开始生成台词。声音页面断开后重新就绪，空闲时立即恢复接话，不等待独处的 120 秒安静周期。网页会显示等待声音页面的启动状态。' if zh else 'Browser TTS mode serves the page first and waits for the unique audio owner to confirm readiness before publishing wake and generating dialogue. After audio reconnects, resume a free room immediately rather than waiting for the 120-second alone interval. The page shows when startup is waiting for audio.')
    add('### 收音确认' if zh else '### Microphone confirmation')
    add('角色播放期间开始的收音，至少累积四个非标点字符且不像角色原话，才触发打断并提交访客发言；停、等等、等一下、别说了、stop、wait 是短指令例外。该规则在打断后保留到本轮结束。短碎片不进入对话或记忆；安静时保留原有短回应。这是针对误识别的保守过滤，不能保证消除所有噪音转写。' if zh else 'For microphone turns starting during character playback, require at least four non-punctuation characters that do not resemble recent character dialogue before interrupting or submitting visitor speech. Explicit short commands 停, 等等, 等一下, 别说了, stop and wait are exceptions. Keep this rule until the turn ends, including after an interruption. Short fragments do not enter dialogue or memory; retain existing short replies during silence. This conservative filter mitigates false transcripts but cannot eliminate them.')
    add('## 一 三个角色的背景' if zh else '## One Character backgrounds')
    for name, p in d['personas'].items():
        add('### ' + name)
        block(persona(name, language))
        add('初始信念，仅初始化时使用：' if zh else 'Initial beliefs, used only at initialization:')
        block('\n'.join('- ' + b for b in p['initial_beliefs']))
    add('## 二 每次调用共用的背景' if zh else '## Two Shared background for brain requests')
    block(d['persona_template'] + '\n\n' + d['belief_heading'] + '\n{current_beliefs}')
    add('history 为空时保持空白，不生成历史。当前信念来自角色保存的 beliefs；初始信念不会重复附在背景里。没有所有角色共用的心理规则，也不发送旧版 NEUTRAL。' if zh else 'Keep history blank when unset; do not generate a biography. Current beliefs come from the saved beliefs field. Do not append the initial beliefs again. There are no shared psychological rules and the previous NEUTRAL instructions are not sent.')
    add('## 三 程序选人，无模型开口判断' if zh else '## Three Speaker selection without model decisions')
    add('主流程不调用 decide，也不发送目录内兼容保留的 decide 提示词。不生成 speak、feeling 或 intent；只有获选角色收到写台词请求。' if zh else 'The main loop does not call decide or send the legacy decide catalog text retained for compatibility. Generate no speak, feeling or intent fields; only the selected character receives a composition request.')
    add('## 四 写台词' if zh else '## Four Compose dialogue')
    add('System：创作说明＋人物背景与当前信念。User：仅现场记录。performance 字段说明和 JSON schema 通过独立接口参数传入。' if zh else 'System: creative brief + character background and current beliefs. User: scene only. Performance field descriptions and JSON schema are passed separately as API parameters.')
    block(d['compose_system'] + '\n\n' + d['persona_template'] + '\n\n' + d['belief_heading'] + '\n{current_beliefs}')
    block(d['recent_heading'] + '\n{recent_events_and_status}')
    add('使用选中时的背景和现场快照；人类插话会取消准备。未入选者不生成台词，也不制造“未说出口”的内容。' if zh else 'Use the background and situation snapshot at selection. Human interruption cancels preparation. Unselected characters generate neither dialogue nor hypothetical unspoken content.')
    add('## 五 反刍' if zh else '## Five Reflect and record')
    add('当前已暂停模型反刍，禁止自动修改信念；下列保留提示词暂不调用。' if zh else 'Model reflection is currently disabled and automatic belief changes are blocked. The retained prompts below are inactive.')
    block(d['experience_heading'] + '\n{pending_experiences}\n\n' + d['context_heading'] + '{context}\n\n' + d['ruminate'])
    add('同伴看法与访客印象暂不生成或保存；旧记录保留。' if zh else 'Companion views and visitor impressions are disabled for generation and storage; existing records are retained.')
    add('context：' + ' / '.join(d[k] for k in ('daily','end','bedtime')))
    add('capacity 来自 memory.belief_capacity，当前为 6。当前反刍仅返回 changes 中的信念修改。' if zh else 'capacity is memory.belief_capacity, currently 6. Reflection currently returns only belief changes in changes.')
    add(('''| 结果 | 保存方式 | 下次请求是否读取 |
| --- | --- | --- |
| 信念变化 | 更新 beliefs 并保存理由日志 | 是 |
| 同伴看法 | companion_observations 按次追加；保留旧 relations 兼容字段 | 否，包括后续反刍 |
| 访客印象 | impressions 按次追加 | 否，包括后续反刍 |''' if zh else '''| Result | Storage | Read by future requests? |
| --- | --- | --- |
| Belief changes | Update beliefs and append reasons to the change log | Yes |
| Companion observations | Append companion_observations; retain legacy relations for compatibility | No, including future reflection |
| Visitor impressions | Append impressions | No, including future reflection |'''))
    add('实际对话按角色存入 pending_experiences，重启后继续保留。成功反刍只消费请求快照中的材料，期间新来的对话留下；失败时材料和计数保留。旧的 thoughts、unspoken 保留兼容，但不再生成或传给模型。现有旧记忆没有这些待处理对话时，无法补回当时遗漏的材料。' if zh else 'Persist actual dialogue per character in pending_experiences across restarts. Successful reflection consumes only its snapshot; new dialogue arriving during the request remains pending. Failures retain material and counts. Legacy thoughts and unspoken fields remain compatible but are no longer generated or sent. Missing pending experiences from old memories cannot be reconstructed automatically.')
    add('触发：累计听到 memory.ruminate_every 条，当前 30；访客离开；关机前有待处理记录且计数达到 bedtime_min_heard，当前 8。反刍计数与短期窗口相互独立。' if zh else 'Triggers: memory.ruminate_every heard lines, currently 30; a visitor leaving; or shutdown with pending experiences and at least bedtime_min_heard lines, currently 8. Reflection material is independent of the short-term window.')
    add('## 六 初始化' if zh else '## Six Initialization')
    add('无生成提示词。启动时为空白信念写入本语言审定的初始信念。已有信念不覆盖，不自动重置。个人历史始终空白，等作者补充。' if zh else 'No generation prompt. At startup, install reviewed initial beliefs in the selected language only for blank beliefs. Never overwrite existing beliefs or reset automatically. Histories stay blank until the author supplies them.')
    add('## 七 嘴巴的声音提示词' if zh else '## Seven Voice prompts')
    for name, voice in d['voices'].items(): add('### ' + name); block(voice)
    add('### 调试用量与配音版本' if zh else '### Debug usage and voice versions')
    add('调试页显示本次进程的脑子实际用量回报：输入（含缓存）、输出（含推理）、角色累计及最近请求。不把缓存或推理再次加入总数；缺失字段显示未知。不含耳朵和嘴，不是订阅余额，也不推算费用。刷新不重置，进程重启清零。旧声音配置与目录保存在 backups/2026-10-18-before-cartoon-voices-and-usage。角色身体能力与环境未修改。新版配音使用 nova/+3 半音（Charlie）、echo/+3（Kaka）、shimmer/+2（Lucy，卡通版），分别配合甜腻发嗲、跳脱卡通鸟和纤细温柔的声音要求。' if zh else 'The debug view displays reported brain usage for this process: input including cached tokens, output including reasoning, per-character totals and latest requests. Do not add cached or reasoning tokens again; missing fields are unknown. Excludes ears and speech synthesis, is not subscription balance, and estimates no costs. Refresh retains totals; process restart clears them. Previous voice settings and catalogs are saved in backups/2026-10-18-before-cartoon-voices-and-usage. Physical abilities and environments remain unchanged. New voices are nova/+3 semitones (Charlie), echo/+3 (Kaka), and shimmer/+2 (Lucy, cartoon delivery), paired with sugary coy, springy cartoon bird, and slender gentle delivery respectively.')
    add('当前三位均选用卡通版。三位均以 mouth.playback_speed=1.15 直接提高播放采样时钟，速度提高 15%、时长缩短约 13%，同时保留约 +2.42 半音的升高；不是保音高的时间拉伸。此项在角色原有移调之后应用，播放时长与打断进度均按新的采样率计算。原版和首版卡通配置、试听音频均保留。' if zh else 'Selected delivery: cartoon Charlie, Kaka and Lucy. All use mouth.playback_speed=1.15, increasing the playback sample clock: 15% faster, approximately 13% shorter, retaining the approximately +2.42-semitone rise. This is not pitch-preserving time stretching. It applies after character pitch processing; playback duration and interruption progress use the new sample rate. Original and first cartoon configurations and preview audio are preserved.')
    add('## 使用和维护' if zh else '## Running and maintaining')
    add('中文：`python -m echo --config config.toml`。英文：`python -m echo --config config.en.toml`，使用独立的 state-en 记忆目录。切换语言或修改提示词需重启。英语版的背景、任务、现场状态、反刍和配音要求均为英语；不会翻译旧记忆或现场原话。' if zh else 'Chinese: `python -m echo --config config.toml`. English: `python -m echo --config config.en.toml`, with a separate state-en memory directory. Restart after language or prompt changes. English backgrounds, tasks, scene status, reflection and voice instructions are adapted to English. Existing memories and quoted dialogue are not translated automatically.')
    add('所有运行提示词正文统一在根目录 prompts.txt；旧 charactor_setting 作为历史资料，不再由主程序载入。文档修改应同步更新目录和必要代码，再运行 `python -m echo.prompt_docs`。`python -m echo.prompt_docs --check` 和测试检查正文是否同步。' if zh else 'All runtime prompt text lives in the root prompts.txt file. Legacy charactor_setting files are historical and no longer loaded by the main application. When editing this specification, update the catalogs and required code together, then run `python -m echo.prompt_docs`. `python -m echo.prompt_docs --check` and tests detect text drift.')
    add('参数总表是 parameters.toml，规则总表是 rules.toml；config.toml 和 config.en.toml 只选择配置。启动时统一读取并校验总表与启动覆盖，生成深层只读的运行快照。运行期间不重读源文件，修改后重启生效；记忆和状态照常变化，不会回写总表。状态目录 runs 子目录的记录来自实际加载的快照。' if zh else 'Numeric settings live in parameters.toml and behavior choices in rules.toml; config.toml and config.en.toml only select a profile. Startup reads and validates the tables and launch overrides once, then binds one deeply immutable snapshot to the run. Runtime never reloads source files; edits take effect after restart. Memory and state remain mutable and never write back to control tables. Records under the state directory runs folder come from the exact loaded snapshot.')
    add('现有中文信念保留，因此新增的 Charlie 和 Kaka 信念不会被强行写入已有记忆。需要采用完整新初始信念时，由作者明确选择重置并备份；仅修改人设不会自动重置记忆。' if zh else 'Existing Chinese beliefs are preserved, so the added Charlie and Kaka beliefs are not forced into existing memories. Adopting the complete new initial beliefs requires an explicit author-chosen backed-up reset. Persona edits do not automatically reset memory.')
    return '\n\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    for language in ('zh', 'en'):
        path = ROOT / 'docs' / f'prompts-and-flow.{language}.md'
        content = render(language)
        if args.check:
            if not path.exists() or path.read_text(encoding='utf-8') != content:
                raise SystemExit(f'Documentation drift: {path.name}; run python -m echo.prompt_docs')
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')

if __name__ == '__main__':
    main()
