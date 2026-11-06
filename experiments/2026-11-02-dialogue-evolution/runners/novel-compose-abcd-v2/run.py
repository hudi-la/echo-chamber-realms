import asyncio,json,sys,time,hashlib
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path('/Users/hudi/Library/Mobile Documents/com~apple~CloudDocs/Documents/remake echo chamber realm/echo-chamber-realms')
sys.path.insert(0,str(ROOT))
from echo.settings import runtime_configuration,plain
from echo.prompts import catalog
from echo.brain import make_brain,Decision
from echo.subscription import SubscriptionSession
from echo.transcript import Transcript
W=Path(__file__).resolve().parent
OUT=W.parent.parent/'outputs'/'小说框架-ABCD-第二轮'
ARCHIVE=Path('/Users/hudi/Documents/Codex/2026-10-31/referenced-chatgpt-conversation-this-is-an/outputs')
async def run():
 with runtime_configuration(W/'config.toml',prompt_file=W/'prompts.txt') as snap:
  cfg=snap.config;data=catalog('zh')
  assert cfg.mouth=='off' and cfg.ears=='console' and cfg.motors=='off'
  assert cfg.brain_auth=='subscription' and cfg.model=='gpt-6-luna' and cfg.puppet_effort=='low'
  OUT.mkdir(exist_ok=True)
  if (OUT/'raw.jsonl').exists():raise RuntimeError('Refusing to overwrite existing results')
  (OUT/'prompts.txt').write_text(snap.sources['prompts.txt']['content'])
  (OUT/'configuration.json').write_text(json.dumps({'config':plain(cfg),'sources':plain(snap.sources),'conditions':'Only production brain.compose and Transcript.render. Original per-case speaker order replayed. Initial beliefs; no audio, transcription, motors, reflection, impression, or exhibition state writes. Synthetic ten-second turn intervals.'},ensure_ascii=False,indent=2,default=str))
  brain=make_brain(cfg.provider,cfg.model,cfg.puppet_effort,cfg.ruminate_model,auth=cfg.brain_auth,subscription_session=SubscriptionSession(profile=cfg.subscription_profile))
  brain.language='zh'
  for case in 'ABCD':
   source=ARCHIVE/('2026-11-02-两种开场对话' if case in 'AB' else '2026-11-02-CD具体事件对话')/case
   old=[json.loads(l) for l in (source/'transcript.jsonl').read_text().splitlines() if l]
   said=[x for x in old if x['kind']=='said'];opening=said[0]['text'];schedule=[x['who'] for x in said[1:]]
   assert len(schedule)==10
   dest=OUT/case;dest.mkdir(exist_ok=True)
   transcript=Transcript(dest/'transcript.jsonl');transcript.add(0,'','said','新朋友',opening)
   last={};lines=[('新朋友',opening)]
   for i,name in enumerate(schedule):
    now=(i+1)*10.0;p=plain(data['personas'][name]);system=data['persona_template'].format(**p)+'\n\n'+data['belief_heading']+'\n'+'\n'.join('- '+b for b in p['initial_beliefs'])
    situation=data['recent_heading']+'\n'+transcript.render(now=now,me=name,speaker=None,last_spoke_at=last.get(name),quiet_for=0,window=cfg.window,show_presence=False,language='zh')
    started=time.time();text=await brain.compose(system,situation,Decision(True))
    row={'case':case,'turn':i+1,'who':name,'text':str(text),'performance':plain(getattr(text,'performance',{})),'system':system,'situation':situation,'seconds':time.time()-started,'utc':datetime.now(timezone.utc).isoformat()}
    with (OUT/'raw.jsonl').open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    if not str(text).strip():raise RuntimeError(f'{case} turn {i+1} generation failed; no replacement generated')
    transcript.add(now+1,'','said',name,str(text));last[name]=now+1;lines.append((name,str(text)))
    (dest/'对话记录.txt').write_text(case+'\n\n'+'\n\n'.join(n+'：'+t for n,t in lines)+'\n')
    (OUT/'progress.json').write_text(json.dumps({'case':case,'turn':i+1,'total':('ABCD'.index(case)*10)+i+1}))
    print(case,i+1,name,str(text),flush=True)
  if hasattr(brain,'token_usage'):(OUT/'usage.json').write_text(json.dumps(brain.token_usage.snapshot(),ensure_ascii=False,indent=2,default=str))
  (OUT/'complete').write_text(datetime.now(timezone.utc).isoformat())
asyncio.run(run())
