"""Build a self-contained preview of the production renderer with explicit sample dialogue.

Run from repository root. No model, microphone, serial port or live state is accessed.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
notes = {
    'Charlie': ('I wanted to help, but I think I was trying to prove that they still need me.',
                'I want to leave room for Lucy to answer in her own way.'),
    'Lucy': ('I feel relieved when they wait, but I am still unsure how much I can say.',
             'I want to ask one question instead of hiding my words again.'),
    'Kaka': ('They noticed his answer first. I wish that did not matter so much to me.',
             'I want to say something that belongs to me, without making it a competition.'),
}
snapshot = dict(type='status', day=1, speaker='Charlie', visitor=False, quiet_for=0,
                puppets={name: dict(private_thoughts=[dict(at='sample', context_at='sample',
                    feeling=feeling, intent=intent)], beliefs=[], relations={}, last_spoke_ago=None)
                    for name, (feeling, intent) in notes.items()})
page = (ROOT / 'echo/monitor.html').read_text()
for asset in ('text-flock.js', 'text-sentences.js', 'ribbon-chain.js', 'visual-budget.js', 'thought-field.js'):
    page = page.replace(f'<script src="/static/{asset}"></script>',
                        '<script>' + (ROOT / 'echo/static' / asset).read_text() + '</script>')
page = page.replace('  connect();', '  // Standalone sample: no live engine connection.')
page = page.replace('  defaultSound();', '  // Sample does not request audio or microphone access.')
demo = r'''
  setView('exhibition');
  document.querySelector('.stage-label').textContent='THREE FLOCKS / ALL-ENGLISH LOAD TEST';
  $('conn').textContent='Sample data';
  for(const id of ['sound','audio','send','interrupt'])$(id).disabled=true;
  $('say').disabled=true;$('say').placeholder='此页为交互视觉示例；真实对话请使用主程序。';
  const previewState=SNAPSHOT;
  const scenes=[
    {who:'Charlie',target:'Lucy',tone:'curious',text:'Lucy, would you rather answer yourself, or have us stay with you?'},
    {who:'Lucy',target:'Kaka',tone:'hesitant',text:'Kaka, I want to finish my thought. Could you wait a moment?'},
    {who:'Kaka',target:'Charlie',tone:'emphatic',text:'You keep answering for her, then tell us you are only trying to help.'}
  ];
  let sceneIndex=0,auto=true;
  const dock=document.createElement('section');dock.className='preview-debug-tools';document.querySelector('header').after(dock);
  const controls=document.createElement('nav');controls.className='preview-controls';
  controls.setAttribute('aria-label','对话交互预览');
  scenes.forEach((scene,i)=>{
    const button=document.createElement('button');button.textContent=scene.who+' → '+scene.target;
    button.onclick=()=>{auto=false;showScene(i);};controls.appendChild(button);
  });
  const cut=document.createElement('button');cut.textContent='Interrupt';
  cut.onclick=()=>{auto=false;onMessage({type:'human_started'});previewState.speaker=null;renderStatus(previewState);$('stage-who').textContent='Interrupted';$('stage-text').textContent='The heads settle, while the ribbons keep moving with their own inertia.';};
  controls.appendChild(cut);
  const resume=document.createElement('button');resume.textContent='Auto dialogue';
  resume.onclick=()=>{auto=true;showScene((sceneIndex+1)%3);};controls.appendChild(resume);
  dock.appendChild(controls);
  function showScene(i){
    sceneIndex=i;const scene=scenes[i];
    previewState.speaker=scene.who;renderStatus(previewState);
    onMessage({type:'started',who:scene.who,text:scene.text,performance:{target:scene.target,tone:scene.tone}});
    const speechVersion=(window.previewSpeechVersion||0)+1;window.previewSpeechVersion=speechVersion;
    setTimeout(()=>{if(window.previewSpeechVersion===speechVersion)onMessage({type:'said',who:scene.who,text:scene.text});},3800);
    controls.querySelectorAll('button').forEach((b,j)=>b.setAttribute('aria-pressed',String(j===i)));
  }

  const loadPanel=document.createElement('div');loadPanel.className='load-panel';
  const loadTitle=document.createElement('span');loadTitle.textContent='English sentences';loadPanel.appendChild(loadTitle);
  const meter=document.createElement('span');meter.className='load-meter';
  const contexts=['Right now,','When the room grows quiet,','After hearing the last reply,','As we wait for one another,','When the conversation changes direction,','Before I answer again,'];
  const samples={
    Charlie:[
      'I want to help without deciding what everyone else needs',
      'I am trying to listen before I offer another solution',
      'I feel useful when someone trusts me with a small question',
      'I wish I could admit that I do not know the answer',
      'I want to stay close without taking up all the space',
      'I notice how quickly I turn uncertainty into advice',
      'I am learning that waiting can also be a way to care',
      'I want my next words to leave room for someone else',
      'I feel nervous when I cannot make the situation better',
      'I hope they will still want me here when I stop performing'
    ],
    Lucy:[
      'I want to finish one thought without being hurried',
      'I feel safer when a pause does not have to mean rejection',
      'I am not sure whether I need an answer or a little company',
      'I want to ask for more time without apologizing for it',
      'I notice the small space between wanting to speak and speaking',
      'I wish I could trust that my quietness is still being heard',
      'I am trying to stay present instead of disappearing',
      'I feel a little braver when nobody finishes my sentence',
      'I want my uncertainty to be allowed in this conversation',
      'I hope I can say something small and let it be enough'
    ],
    Kaka:[
      'I want to be noticed without making this a competition',
      'I feel proud of my answer and uneasy about needing praise',
      'I am trying to listen without preparing an impressive reply',
      'I wish their attention did not matter so much to me',
      'I want to disagree without making someone feel smaller',
      'I notice how quickly I mistake silence for indifference',
      'I am learning to leave a question open for a little longer',
      'I feel exposed when I cannot hide behind being certain',
      'I want to say something honest even if it is not remarkable',
      'I hope I can belong here without having to be exceptional'
    ]
  };
  function setLoad(total){
    const each=total/3;$('stage').dataset.sentenceLimit=String(each);
    for(const name of ['Charlie','Lucy','Kaka']){
      previewState.puppets[name].private_thoughts=Array.from({length:each},(_,i)=>({
        at:'sample-'+i,context_at:'sample',feeling:contexts[Math.floor(i/10)]+' '+samples[name][i%10]+'.',intent:''
      }));
    }
    renderStatus(previewState);
    loadPanel.querySelectorAll('button').forEach(button=>button.setAttribute('aria-pressed',String(Number(button.textContent)===total)));
    loadPanel.dataset.total=String(total);
  }
  for(const total of [30,60,120,180]){const b=document.createElement('button');b.textContent=String(total);b.onclick=()=>setLoad(total);loadPanel.appendChild(b);}
  loadPanel.appendChild(meter);dock.appendChild(loadPanel);
  setInterval(()=>{const field=$('thought-field');meter.textContent=(field.dataset.sentenceCount||'0')+' ribbons · '+(field.dataset.fps||'…')+' fps';},1000);

  const tuning=document.createElement('details');tuning.className='flock-tuning';
  const summary=document.createElement('summary');summary.textContent='Flock behavior / glow';tuning.appendChild(summary);
  const sliders=[['Spacing',65,v=>({spacing:.12+v*.0028})],['Same-color attraction',40,v=>({sameRoleAttraction:v*.0015})],['Cross-color attraction',10,v=>({crossRoleAttraction:v*.0004})],['Same-color following',60,v=>({sameRoleFollowing:v*.005})],['Cross-color following',15,v=>({crossRoleFollowing:v*.002})],['Wandering',70,v=>({wander:.2+v*.012})]];
  for(const [name,value,map]of sliders){
    const label=document.createElement('label');label.textContent=name;
    const input=document.createElement('input');input.type='range';input.min='0';input.max='100';input.value=String(value);input.setAttribute('aria-label',name);
    const output=document.createElement('output');output.textContent=String(value);
    input.oninput=()=>{output.textContent=input.value;window.thoughtField.tune(map(Number(input.value)));};
    label.appendChild(input);label.appendChild(output);tuning.appendChild(label);
    window.thoughtField.tune(map(value));
  }
  const glowKey=document.createElement('p');glowKey.textContent='Text color: character. Glow: feeling — blue uneasy, gold hopeful, mint calm, pink excited.';tuning.appendChild(glowKey);
  dock.appendChild(tuning);
  setLoad(60);
  showScene(0);
  setInterval(()=>{if(auto)showScene((sceneIndex+1)%3);},8500);
'''.replace('SNAPSHOT', json.dumps(snapshot, ensure_ascii=False))
page = page.replace('  function send() {', demo + '\n  function send() {')
style = '''
.load-panel { position:absolute;left:50%;top:14%;transform:translateX(-50%);display:flex;align-items:center;gap:8px;font:10px system-ui;color:#7c7066;z-index:5;white-space:nowrap }
.load-panel button { border:1px solid #d1c7bd;background:transparent;color:#65574e;border-radius:14px;padding:5px 10px;cursor:pointer }.load-panel button[aria-pressed="true"] { background:#4c4037;color:#fff }.load-meter { margin-left:8px;font-variant-numeric:tabular-nums }
.preview-controls { position:absolute;left:50%;top:8%;transform:translateX(-50%);display:flex;gap:7px;z-index:5;white-space:nowrap }
.preview-controls button { background:#f4f1ebc9;border:1px solid #d1c7bd;color:#65574e;padding:8px 12px;font:10px system-ui;cursor:pointer;border-radius:20px }
.preview-controls button[aria-pressed="true"] { background:#4c4037;color:#fff;border-color:#4c4037 }
@media(max-width:700px){.preview-controls{max-width:94%;overflow:auto;top:9%}.preview-controls button{padding:7px;font-size:9px}.load-panel{top:20%;gap:4px;font-size:8px}.load-panel button{padding:5px 7px}.load-meter{margin-left:2px}#interaction-label{top:5%}.stage-label{top:1.7%;font-size:7px}}
'''
style += """
.preview-controls button,.load-panel button { background:#0c101bcc;color:#b8bed0;border-color:#343b50 }
.preview-controls button[aria-pressed="true"],.load-panel button[aria-pressed="true"] { background:#c8cddd;color:#10131b;border-color:#c8cddd }
.load-panel { color:#949caf }
.flock-tuning { position:absolute;top:19%;left:50%;transform:translateX(-50%);z-index:6;width:310px;background:#0c111cde;border:1px solid #30394a;border-radius:9px;padding:8px 12px;color:#b8c1d0;font:10px system-ui }
.flock-tuning summary { cursor:pointer;letter-spacing:.05em;text-align:center }
.flock-tuning label { display:flex;align-items:center;gap:9px;margin-top:9px }.flock-tuning input { width:165px;margin-left:auto;accent-color:#a0befa }.flock-tuning output { width:22px;text-align:right }.flock-tuning p { color:#858fa3;line-height:1.5;margin-bottom:2px }
@media(max-width:700px){.flock-tuning{top:25%;width:270px}}
"""
style += """
.preview-debug-tools { display:flex;flex-wrap:wrap;gap:16px;padding:18px;background:#0c101b;color:#b8bed0 }
.preview-debug-tools .preview-controls,.preview-debug-tools .load-panel,.preview-debug-tools .flock-tuning { position:static;transform:none;margin:0;max-width:100%;overflow:auto }
body.exhibition .preview-debug-tools { display:none!important }
"""
page = page.replace('</style>', style + '</style>')
dest = ROOT / 'artifacts/thought-field-preview/index.html'
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(page)
print(dest)
