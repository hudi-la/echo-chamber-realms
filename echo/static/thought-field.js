/* One complete sentence = one moving text ribbon in a shared three-dimensional flock. */
(() => {
  'use strict';
  const names=['Charlie','Lucy','Kaka'],colors=['#ffbd78','#79e9ef','#d9aaff'];
  // Exhibition display compensation: tighter text bloom, clearer surf and stars.
  const display={textSize:.85,textGlow:7,textGlowAlpha:'88',starGain:1.55,waveGain:1.30,depthDensity:.30};
  const stage=document.getElementById('stage'),canvas=document.createElement('canvas');
  canvas.id='thought-field';canvas.setAttribute('aria-hidden','true');stage.prepend(canvas);
  const ctx=canvas.getContext('2d',{alpha:true});
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  const states=names.map(()=>({signature:'',notes:[]}));
  const spokenItems=[];let pendingSpeech=null,runId=null;
  // Keep the latest pending thought per role: frequent updates must not create an ever-growing queue.
  const thoughtCard=document.getElementById('inner-thought'),thoughtQueue=[];
  const shownThoughts=new Map();let thoughtTimer=null;
  function showNextThought(){
    if(!thoughtCard||!thoughtQueue.length){if(thoughtCard)thoughtCard.hidden=true;thoughtTimer=null;return;}
    const {name,note}=thoughtQueue.shift();
    thoughtCard.style.setProperty('--thought-color',colors[names.indexOf(name)]);
    thoughtCard.querySelector('h2').textContent=name+'’s thoughts';
    thoughtCard.querySelector('.feeling').textContent=note.feeling||'';
    thoughtCard.querySelector('.intent').textContent=note.intent||'';
    thoughtCard.hidden=false;thoughtCard.dataset.role=name;
    const length=((note.feeling||'')+' '+(note.intent||'')).length;
    thoughtTimer=setTimeout(()=>{thoughtCard.hidden=true;thoughtTimer=setTimeout(showNextThought,650);},Math.max(9000,Math.min(18000,length*55)));
  }
  function queueThought(name,note){
    if(!note||!(note.feeling||note.intent))return;
    const signature=JSON.stringify([note.feeling,note.intent]);
    if(shownThoughts.get(name)===signature)return;
    shownThoughts.set(name,signature);
    const existing=thoughtQueue.findIndex(item=>item.name===name);
    if(existing>=0)thoughtQueue[existing]={name,note};else thoughtQueue.push({name,note});
    if(thoughtTimer===null)showNextThought();
  }

  const particles=[],flock=new window.TextFlock3D(particles,{perception:.85,maxSpeed:.55,minSpeed:.26,speedVariation:.24,flight:true,flowGain:2.0,sameRoleCohesion:.02,sameRoleAlignment:.10,sameRoleAttraction:.06,crossRoleAttraction:.004,sameRoleFollowing:.30,crossRoleFollowing:.03,flowRelaxation:.65,boundaryGain:.12,separationDistance:.30,separationWeight:1.2,wander:1.05,guideStrength:.42,guideAlignment:.18,flightSpan:2.4});
  // One cached soft particle sprite per character; no per-frame shadow blur.
  const waveSprites=colors.map(color=>{
    const tile=document.createElement('canvas');tile.width=tile.height=24;
    const g=tile.getContext('2d'),glow=g.createRadialGradient(12,12,0,12,12,12);
    glow.addColorStop(0,'#ffffff');glow.addColorStop(.22,color);glow.addColorStop(.42,color+'70');glow.addColorStop(1,color+'00');
    g.fillStyle=glow;g.fillRect(0,0,24,24);return tile;
  });
  const distantWaveSprites=waveSprites.map(sprite=>{
    const tile=document.createElement('canvas');tile.width=tile.height=24;
    const g=tile.getContext('2d');g.drawImage(sprite,0,0);g.globalCompositeOperation='source-atop';g.globalAlpha=.72;g.fillStyle='#71839b';g.fillRect(0,0,24,24);return tile;
  });
  // Stable world-space stars on deep spherical shells, never a screen-space wallpaper.
  let skySeed=81973;
  const skyRandom=()=>{skySeed=(Math.imul(skySeed,1664525)+1013904223)>>>0;return skySeed/4294967296;};
  const stars=Array.from({length:2400},()=>{
    const azimuth=skyRandom()*Math.PI*2,v=skyRandom()*2-1,r=18+Math.pow(skyRandom(),.65)*100,ring=Math.sqrt(1-v*v);
    return {x:Math.cos(azimuth)*ring*r,y:v*r,z:Math.sin(azimuth)*ring*r,radius:r,brightness:.16+Math.pow(skyRandom(),3)*.84,phase:skyRandom()*Math.PI*2,tint:Math.floor(skyRandom()*3)};
  });
  const starSprites=['#c6dfff','#eeeaff','#ffe1b8'].map(color=>{
    const tile=document.createElement('canvas');tile.width=tile.height=24;
    const g=tile.getContext('2d'),halo=g.createRadialGradient(12,12,0,12,12,12);
    halo.addColorStop(0,'#ffffff');halo.addColorStop(.10,color);halo.addColorStop(.25,color+'88');halo.addColorStop(1,color+'00');
    g.fillStyle=halo;g.fillRect(0,0,24,24);return tile;
  });
  const camera={yaw:0,pitch:.22,zoom:1,drag:false,x:0,y:0};
  const turn={speaker:-1,target:-1,tone:.45,strength:0,goal:0,key:null};
  let analyser=null,bins=null,energy=0,last=0,time=0,accumulator=0,frames=0,measured=performance.now();
  let width=1,height=1,scale=1,nextId=0;
  let physicsMs=0,drawMs=0;
  const visualBudget=new window.VisualBudget();let quality=visualBudget.profile(),voiceActive=false,frameStalled=false,activeFrame=false;
  function moodLight(feeling,role){
    const text=String(feeling||'').toLowerCase();
    if(/afraid|fear|nervous|uncertain|uneasy|anxious|exposed|rejection|不安|害怕|紧张|不确定/.test(text))return {name:'uneasy',color:'#78a9ff',pulse:.10};
    if(/excited|proud|remarkable|exceptional|兴奋|激动|骄傲/.test(text))return {name:'excited',color:'#ff88d5',pulse:.20};
    if(/angry|frustrat|competition|disagree|生气|愤怒|委屈/.test(text))return {name:'tense',color:'#ff8e79',pulse:.13};
    if(/sad|lonely|disappear|悲伤|孤独|失落/.test(text))return {name:'sad',color:'#8e92ef',pulse:.05};
    if(/hope|care|close|belong|trust|help|希望|温暖|亲近/.test(text))return {name:'hopeful',color:'#ffd58c',pulse:.08};
    if(/reliev|safer|listen|wait|quiet|calm|松了|安心|平静|放松/.test(text))return {name:'calm',color:'#83edd2',pulse:.045};
    return {name:'neutral',color:colors[role],pulse:.06};
  }
  const glyphCache=new Map();
  function ribbonTexture(text,color,light){
    const tile=document.createElement('canvas'),probe=tile.getContext('2d');
    const font='56px Georgia,"Songti SC","Noto Serif CJK SC",serif';probe.font=font;
    const measuredWidth=probe.measureText(text).width;
    const ratio=Math.min(1,3600/(measuredWidth+24));
    tile.width=Math.ceil((measuredWidth+24)*ratio);tile.height=110;
    const c=tile.getContext('2d');c.scale(ratio,1);c.font=font;c.fillStyle=color;c.textBaseline='middle';c.shadowColor=light.color+display.textGlowAlpha;c.shadowBlur=display.textGlow;
    c.fillText(text,12,55);
    const chars=typeof Intl.Segmenter==='function'?[...new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(text)].map(s=>s.segment):Array.from(text);
    let prefix='';
    const glyphs=chars.map(char=>{
      const start=probe.measureText(prefix).width;prefix+=char;
      const end=probe.measureText(prefix).width,key=color+'|'+light.color+'|'+char;
      let sprite=glyphCache.get(key);
      if(!sprite){
        const advance=probe.measureText(char).width;
        const bitmap=document.createElement('canvas');bitmap.width=Math.ceil(advance+40);bitmap.height=110;
        const g=bitmap.getContext('2d');g.font=font;g.textBaseline='middle';g.fillStyle=color;g.shadowColor=light.color+display.textGlowAlpha;g.shadowBlur=display.textGlow;g.fillText(char,20,55);
        const distant=document.createElement('canvas');distant.width=bitmap.width;distant.height=bitmap.height;
        const fog=distant.getContext('2d');fog.drawImage(bitmap,0,0);fog.globalCompositeOperation='source-atop';fog.globalAlpha=.73;fog.fillStyle='#687991';fog.fillRect(0,0,distant.width,distant.height);
        sprite={bitmap,distant,advance};glyphCache.set(key,sprite);
      }
      return {sprite,u:(start+end)*.5/Math.max(1,measuredWidth),space:/^\s+$/.test(char)};
    });
    return {canvas:tile,aspect:(measuredWidth+24)/110,glyphs,measuredWidth};
  }

  function synchronize(){
    const desired=[];
    states.forEach((s,role)=>{
      const seen=new Set();
      for(const note of s.notes){for(const part of [note.feeling,note.intent])for(const text of window.TextSentences(part)){
        if(!seen.has(text)){seen.add(text);desired.push({text,role,light:moodLight(note.feeling||part,role),key:role+'\u0000'+text});}
      }}
    });
    // Bounded history, with each whole sentence appearing once rather than thousands of copies.
    const limit=Math.max(1,Math.min(60,Number(stage.dataset.sentenceLimit)||10));
    const streams=names.map((_,role)=>desired.filter(item=>item.role===role).slice(-limit));
    const keep=[];for(let i=0;i<Math.max(0,...streams.map(s=>s.length));i++)for(const stream of streams)if(stream[i])keep.push(stream[i]);
    keep.push(...spokenItems);
    const existing=new Map(particles.map(p=>[p.key,p]));
    const next=keep.map((item,i)=>{
      if(existing.has(item.key)){
        const head=existing.get(item.key);
        head.arousal=({uneasy:.8,tense:1,excited:.5,calm:0,sad:0,hopeful:.1})[item.light.name]||0;
        if(head.light.color!==item.light.color){head.light=item.light;head.texture=ribbonTexture(item.text,colors[item.role],item.light);}
        return head;
      }
      const theta=i*2.399963,texture=ribbonTexture(item.text,colors[item.role],item.light);
      const angle=item.role*Math.PI*2/3+.25;
      const head={...item,id:nextId++,texture,arousal:({uneasy:.8,tense:1,excited:.5,hopeful:.1})[item.light.name]||0,
        x:(item.role-1)*.58+.12*Math.sin(theta),y:.23*Math.sin(angle)+.09*Math.cos(theta),z:.35*Math.cos(angle)+.08*Math.sin(theta),
        vx:-Math.sin(angle)*.30,vy:.08*Math.sin(theta),vz:Math.cos(angle)*.30,phase:theta,emerge:0};
      const length=Math.max(1.4,Math.min(3.8,texture.canvas.width/650));
      head.ribbon=new window.RibbonChain3D(head,length,36);
      return head;
    });
    particles.splice(0,particles.length,...next);
    flock.acceleration=new Float32Array(particles.length*3);
    canvas.dataset.sentenceCount=String(particles.length);
    canvas.dataset.text=particles.map(p=>p.text).join('\n');
    canvas.dataset.moods=JSON.stringify(particles.reduce((out,p)=>(out[p.light.name]=(out[p.light.name]||0)+1,out),{}));
  }
  function releaseSpeech(speech){
    const role=names.indexOf(speech.who),field=document.getElementById('stage-text');
    if(role<0||!field||field.textContent!==speech.text)return;
    const key='spoken:'+nextId+':'+time;
    const light=moodLight(states[role].notes.at(-1)?.feeling,role);
    spokenItems.push({key,text:speech.text,role,light});if(spokenItems.length>9)spokenItems.shift();
    synchronize();
    const head=particles.find(p=>p.key===key);if(!head)return;head.emerge=1;
    const stageBounds=stage.getBoundingClientRect(),style=getComputedStyle(field),fontSize=parseFloat(style.fontSize)||20;
    const textNode=field.firstChild,origins=[];let offset=0;
    const sourceChars=typeof Intl.Segmenter==='function'?[...new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(speech.text)].map(s=>s.segment):Array.from(speech.text);
    for(const char of sourceChars){
      const range=document.createRange();range.setStart(textNode,offset);range.setEnd(textNode,offset+char.length);
      const r=range.getBoundingClientRect();origins.push({x:r.left-stageBounds.left+r.width*.5,y:r.top-stageBounds.top+r.height*.5});offset+=char.length;
    }
    // Invert the current camera on its center-depth plane: the head starts at the subtitle.
    const yaw=camera.yaw+(reduced.matches?0:time*.014),pitch=camera.pitch+(reduced.matches?0:Math.sin(time*.045)*.065);
    const first=origins[0],sx=(first.x-width*.5)/scale,sy=(height*.43-first.y)/scale;
    const zRot=sy*Math.sin(pitch);
    head.x=sx*Math.cos(yaw)-zRot*Math.sin(yaw);head.y=sy*Math.cos(pitch);head.z=(sx*Math.sin(yaw)+zRot*Math.cos(yaw))/1.6;
    const peers=particles.filter(p=>p.role===role&&p!==head);
    const target=peers.reduce((v,p)=>({x:v.x+p.x/peers.length,y:v.y+p.y/peers.length,z:v.z+p.z/peers.length}),{x:0,y:0,z:0});
    const dx=target.x-head.x,dy=target.y-head.y,dz=target.z-head.z,d=Math.hypot(dx,dy,dz)||1;
    head.vx=dx/d*.9;head.vy=dy/d*.9;head.vz=dz/d*.9;
    // Start the physical tail along the subtitle baseline; each letter is handed
    // from its exact wrapped subtitle position into this moving tail in sequence.
    const n=head.ribbon.nodes.length;
    for(let i=0;i<n;i++){
      const distance=i/(n-1)*head.ribbon.length;
      const x=head.x+distance*Math.cos(yaw),y=head.y,z=head.z+distance*Math.sin(yaw)/1.6;
      Object.assign(head.ribbon.nodes[i],{x,y,z,px:x,py:y,pz:z});
    }
    head.entry={at:time,origins,fontSize};
    field.style.opacity='0';document.getElementById('stage-who').style.opacity='0';
    canvas.dataset.latestSpeech=speech.text;
  }
  function start(who,target,tone,key){
    if(key&&turn.key===key)return;turn.key=key;turn.speaker=names.indexOf(who);turn.target=names.indexOf(target);
    turn.tone=({neutral:.45,curious:.55,hesitant:.23,emphatic:.9,excited:1})[tone]??.45;turn.goal=turn.speaker>=0?1:0;
    const label=document.getElementById('interaction-label');if(label)label.textContent=names.includes(target)?who+' · '+target:'';
  }
  function advance(dt){
    accumulator=Math.min(accumulator+dt,(visualBudget.level>=3?1:2)/60);
    const focus=turn.target>=0?(turn.speaker+turn.target-2)*.36:0;
    while(accumulator>=1/60){flock.step(1/60,time,turn.strength*turn.tone+energy,focus);for(const head of particles)head.ribbon.step(1/60,time);accumulator-=1/60;}
  }
  function render(dt){
    const rect=stage.getBoundingClientRect(),dpr=Math.min(devicePixelRatio||1,quality.dpr);
    width=Math.max(1,rect.width);height=Math.max(1,rect.height);
    flock.options.horizontalSpan=Math.max(1.0,Math.min(2.1,width/height*1.12));
    const w=Math.round(width*dpr),h=Math.round(height*dpr);
    if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}
    ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,width,height);
    const yaw=camera.yaw+(reduced.matches?0:time*.014),pitch=camera.pitch+(reduced.matches?0:Math.sin(time*.045)*.065);
    const cy=Math.cos(yaw),sy=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch);
    // The same camera rotation projects the far sky and the foreground flock.
    // Its orbit around the foreground adds stronger parallax to nearer star shells.
    const skyFocal=Math.max(width,height)*.72;
    let visibleStars=0;
    ctx.save();ctx.globalCompositeOperation='screen';
    for(let starIndex=0;starIndex<stars.length;starIndex+=quality.starStride){
      const star=stars[starIndex];
      const x=star.x*cy+star.z*sy,z=-star.x*sy+star.z*cy,y=star.y*cp+z*sp;
      const depth=6-(-star.y*sp+z*cp);if(depth<5)continue;
      const sx=width*.5+x/depth*skyFocal,syScreen=height*.43-y/depth*skyFocal;
      if(sx<-12||sx>width+12||syScreen<-12||syScreen>height+12)continue;
      const size=Math.min(2.6,.35+star.brightness*.75+10/depth);
      const twinkle=reduced.matches?1:.86+.14*Math.sin(time*.65+star.phase);
      ctx.globalAlpha=Math.min(.95,(.20+star.brightness*.65)*display.starGain)*twinkle;
      ctx.drawImage(starSprites[star.tint],sx-size*3,syScreen-size*3,size*6,size*6);
      visibleStars++;
    }
    ctx.restore();canvas.dataset.visibleStars=String(visibleStars);
    canvas.dataset.cameraOrbit=yaw.toFixed(3);
    // Broad pools of scattered light give the black space a quiet atmosphere.
    ctx.save();ctx.globalCompositeOperation='screen';
    const lamps=[{x:-1.6,y:1.5,z:.9,color:'255,180,108'},{x:1.7,y:.6,z:-.8,color:'105,170,255'}];
    for(const lamp of lamps){
      const lx=lamp.x*cy+lamp.z*sy,lz=-lamp.x*sy+lamp.z*cy,ly=lamp.y*cp+lz*sp;
      const x=width*.5+lx*width*.13,y=height*.44-ly*height*.18,r=Math.max(width,height)*.65;
      const fog=ctx.createRadialGradient(x,y,0,x,y,r);
      fog.addColorStop(0,'rgba('+lamp.color+',.075)');fog.addColorStop(.38,'rgba('+lamp.color+',.025)');fog.addColorStop(1,'rgba('+lamp.color+',0)');
      ctx.fillStyle=fog;ctx.fillRect(0,0,width,height);
    }
    ctx.restore();
    const project=p=>{
      const x=p.x*cy+p.z*1.6*sy,z=-p.x*sy+p.z*1.6*cy,y=p.y*cp+z*sp;
      const depth=Math.max(2.5,6-(-p.y*sp+z*cp)),perspective=6/depth;
      return {x,y,depth,perspective};
    };
    // The spine bends physically; each glyph is a rigid sprite placed along it.
    // Only translation, in-plane rotation and UNIFORM scaling are allowed per glyph.
    const desired=Math.min(width/5.8,height/4.1)*camera.zoom;
    scale=scale===1?desired:scale+(desired-scale)*Math.min(1,dt*1.3);
    const glyphs=[];
    const roleCounts=names.map((_,role)=>particles.filter(p=>p.role===role).length);
    const roleIndices=[0,0,0];let waveCount=0;
    for(const head of particles){
      head.emerge=Math.min(1,head.emerge+dt*.8);
      if(head.entry&&time-head.entry.at>2.3)delete head.entry;
      const nodes=head.ribbon.nodes;
      const sample=u=>{
        const f=Math.max(0,Math.min(nodes.length-1,u*(nodes.length-1))),i=Math.min(nodes.length-2,Math.floor(f)),t=f-i;
        const a=nodes[i],b=nodes[i+1];return project({x:a.x+(b.x-a.x)*t,y:a.y+(b.y-a.y)*t,z:a.z+(b.z-a.z)*t});
      };
      // Sample a bounded set of real sentence spines per color. The particle surf
      // inherits their physical motion, so it surrounds the text rather than a fixed orb.
      const roleIndex=roleIndices[head.role]++;
      const stride=Math.max(1,Math.ceil(roleCounts[head.role]/Math.max(1,quality.waveHeads)));
      if(quality.waveHeads&&roleIndex%stride===0){
        const count=quality.waveSamples,lanes=quality.waveLanes,phase=head.role*2.094;
        for(let k=0;k<count;k++){
          const u=((k/count+time*(.035+head.arousal*.02)+head.id*.071)%1);
          const f=u*(nodes.length-1),j=Math.min(nodes.length-2,Math.floor(f)),mix=f-j;
          const a=nodes[j],b=nodes[j+1],tx=b.x-a.x,ty=b.y-a.y,tz=b.z-a.z,len=Math.hypot(tx,ty,tz)||1;
          const tangent={x:tx/len,y:ty/len,z:tz/len};
          let nx=-tangent.z,ny=0,nz=tangent.x;
          if(Math.hypot(nx,nz)<.05){nx=1;nz=0;}
          const nl=Math.hypot(nx,nz);nx/=nl;nz/=nl;
          const bx=tangent.y*nz,by=tangent.z*nx-tangent.x*nz,bz=-tangent.y*nx;
          const wave=u*11-time*(1.15+head.arousal*.7)+phase;
          const crest=Math.pow(.5+.5*Math.sin(wave),3);
          const envelope=Math.sin(Math.PI*u)**.5;
          for(let lane=0;lane<lanes;lane++){
            const theta=lane/lanes*Math.PI*2+.35*Math.sin(wave*.65)+head.phase*.12;
            const radius=(.13+.34*crest+.035*Math.sin(u*23+lane+time))*envelope;
            const lateral=Math.cos(theta)*radius,vertical=Math.sin(theta)*radius;
            const p=project({x:a.x+(b.x-a.x)*mix+nx*lateral+bx*vertical,y:a.y+(b.y-a.y)*mix+ny*lateral+by*vertical,z:a.z+(b.z-a.z)*mix+nz*lateral+bz*vertical});
            glyphs.push({head,p,wave:true,opacity:Math.min(.90,(.20+.48*crest)*display.waveGain)*envelope,size:(.50+crest*.75)*p.perspective});waveCount++;
          }
        }
      }
      let glyphIndex=0;
      for(const glyph of head.texture.glyphs){
        const sourceIndex=glyphIndex++;
        if(glyph.space)continue;
        const p=sample(glyph.u),before=sample(glyph.u-.008),after=sample(glyph.u+.008);
        const dx=after.x*after.perspective-before.x*before.perspective,dy=-(after.y*after.perspective-before.y*before.perspective);
        glyphs.push({head,glyph,p,angle:Math.atan2(dy,dx),size:head.ribbon.length/head.texture.measuredWidth*scale*p.perspective,origin:head.entry?.origins[sourceIndex]});
      }
    }
    canvas.dataset.waveParticles=String(waveCount);
    canvas.dataset.joiningSpeech=String(particles.some(p=>p.entry));
    glyphs.sort((a,b)=>b.p.depth-a.p.depth);
    for(const item of glyphs){
      const {head,glyph,p,angle,size}=item;
      if(item.wave){
        const radius=Math.max(.5,size*Math.min(1.8,scale/110)*Math.pow(p.perspective,.6));
        ctx.globalAlpha=head.emerge*item.opacity*Math.exp(-Math.max(0,p.depth-3.5)*.33);
        ctx.drawImage((p.depth>6.8?distantWaveSprites:waveSprites)[head.role],width*.5+p.x*p.perspective*scale-radius*3,height*.43-p.y*p.perspective*scale-radius*3,radius*6,radius*6);
        continue;
      }
      const {advance}=glyph.sprite,bitmap=p.depth>6.8?glyph.sprite.distant:glyph.sprite.bitmap;
      ctx.globalAlpha=head.emerge*Math.max(.18,Math.min(1,Math.exp(-Math.max(0,p.depth-3.8)*display.depthDensity)));
      let x=width*.5+p.x*p.perspective*scale,y=height*.43-p.y*p.perspective*scale,rotation=angle,glyphScale=size*display.textSize;
      if(head.entry&&item.origin){
        const t=reduced.matches?1:Math.max(0,Math.min(1,(time-head.entry.at-glyph.u*.85)/1.35));
        const ease=t*t*(3-2*t);
        x=item.origin.x+(x-item.origin.x)*ease;y=item.origin.y+(y-item.origin.y)*ease;
        glyphScale=head.entry.fontSize/56+(size*display.textSize-head.entry.fontSize/56)*ease;
        rotation=angle*ease;ctx.globalAlpha=1;
      }
      ctx.save();ctx.translate(x,y);ctx.rotate(rotation);ctx.scale(glyphScale,glyphScale);
      ctx.drawImage(bitmap,-advance*.5-20,-55);ctx.restore();
    }

    ctx.globalAlpha=1;
  }
  function frame(now){
    requestAnimationFrame(frame);
    if(!document.body.classList.contains('exhibition')||document.hidden){last=now;frames=0;measured=now;activeFrame=false;return;}
    const audioBusy=voiceActive||turn.goal>0||energy>.03;
    quality=visualBudget.profile(audioBusy);
    if(!activeFrame){last=now;measured=now;activeFrame=true;return;}
    const elapsed=now-last;
    if(elapsed<1000/quality.fps-.8)return;
    frameStalled=frameStalled||elapsed>150;
    const dt=Math.min(elapsed/1000,.065);last=now;
    turn.strength+=(turn.goal-turn.strength)*Math.min(1,dt*1.3);
    energy*=.9;if(analyser&&bins){analyser.getByteTimeDomainData(bins);let sum=0;for(const b of bins)sum+=((b-128)/128)**2;energy=Math.min(1,Math.sqrt(sum/bins.length)*5);}
    if(pendingSpeech&&time>=pendingSpeech.ready){releaseSpeech(pendingSpeech);pendingSpeech=null;}
    const t0=performance.now();if(!reduced.matches){time+=dt;advance(dt);}const t1=performance.now();render(dt);
    physicsMs=physicsMs*.9+(t1-t0)*.1;drawMs=drawMs*.9+(performance.now()-t1)*.1;
    frames++;if(now-measured>1500){
      const fps=frames*1000/(now-measured);
      visualBudget.observe({fps,costMs:physicsMs+drawMs,audio:audioBusy,seconds:(now-measured)/1000,now,stalled:frameStalled});
      frameStalled=false;canvas.dataset.visualQuality=String(visualBudget.level);canvas.dataset.visualTargetFps=String(quality.fps);canvas.dataset.audioPriority=String(audioBusy);
      canvas.dataset.fps=String(Math.round(frames*1000/(now-measured)));canvas.dataset.physicsMs=physicsMs.toFixed(2);canvas.dataset.drawMs=drawMs.toFixed(2);
      const speeds=particles.map(p=>Math.hypot(p.vx,p.vy,p.vz));
      canvas.dataset.speedRange=JSON.stringify([Math.min(...speeds),Math.max(...speeds)]);
      canvas.dataset.emotionalHeads=String(particles.filter(p=>p.arousal>=.8).length);frames=0;measured=now;}
  }
  canvas.style.pointerEvents='auto';canvas.style.touchAction='none';canvas.style.cursor='grab';
  canvas.addEventListener('pointerdown',e=>{camera.drag=true;camera.x=e.clientX;camera.y=e.clientY;canvas.setPointerCapture(e.pointerId);canvas.style.cursor='grabbing';});
  canvas.addEventListener('pointermove',e=>{if(!camera.drag)return;camera.yaw+=(e.clientX-camera.x)*.006;camera.pitch=Math.max(-1.2,Math.min(1.2,camera.pitch+(e.clientY-camera.y)*.005));camera.x=e.clientX;camera.y=e.clientY;canvas.dataset.view=camera.yaw.toFixed(2)+','+camera.pitch.toFixed(2);});
  const release=()=>{camera.drag=false;canvas.style.cursor='grab';};canvas.addEventListener('pointerup',release);canvas.addEventListener('pointercancel',release);
  canvas.addEventListener('wheel',e=>{e.preventDefault();camera.zoom=Math.max(.65,Math.min(1.5,camera.zoom*Math.exp(-e.deltaY*.001)));},{passive:false});
  canvas.addEventListener('dblclick',()=>{camera.yaw=0;camera.pitch=.22;camera.zoom=1;});
  canvas.dataset.displayProfile='exhibition-monitor';canvas.dataset.lighting='depth-haze desaturated-distance bright-near';canvas.dataset.dimensions='3';canvas.dataset.renderer='physical-trails-rigid-glyphs';canvas.dataset.groups='3';canvas.dataset.waves='three-role-particle-surf';canvas.dataset.sky='world-space-depth-stars';canvas.dataset.viewportBoundary='open';canvas.dataset.groupCohesion='same-role stronger';
  requestAnimationFrame(frame);
  window.thoughtField={
    audioPriority(active){voiceActive=Boolean(active);},
    tune(values){
      const o=flock.options;
      if(Number.isFinite(values.spacing))o.separationDistance=Math.max(.10,Math.min(.45,values.spacing));
      for(const key of ['sameRoleAttraction','crossRoleAttraction','sameRoleFollowing','crossRoleFollowing']){
        if(Number.isFinite(values[key]))o[key]=Math.max(0,Math.min(1,values[key]));
      }
      if(Number.isFinite(values.wander))o.wander=Math.max(0,Math.min(1.8,values.wander));
      canvas.dataset.spacing=String(o.separationDistance);canvas.dataset.attraction=JSON.stringify({same:o.sameRoleAttraction,cross:o.crossRoleAttraction});canvas.dataset.following=JSON.stringify({same:o.sameRoleFollowing,cross:o.crossRoleFollowing});canvas.dataset.wander=String(o.wander);
    },
    event(message){
      if(message.type==='started'){
        const p=message.performance||{};start(message.who,p.target,p.tone,message.id||null);
        if(message.text&&names.includes(message.who))pendingSpeech={who:message.who,text:message.text,ready:Infinity};
      }
      if(message.type==='said'&&message.text&&names.includes(message.who))pendingSpeech={who:message.who,text:message.text,ready:time+(reduced.matches?0:.5)};
      if(['cut','human_started'].includes(message.type))pendingSpeech=null;
      if(['said','cut','human_started'].includes(message.type)){turn.goal=0;const label=document.getElementById('interaction-label');if(label)label.textContent='';}
    },
    update(snapshot){
      if(snapshot.run_id && snapshot.run_id!==runId){
        runId=snapshot.run_id;canvas.dataset.runId=runId;pendingSpeech=null;
        clearTimeout(thoughtTimer);thoughtTimer=null;thoughtQueue.length=0;shownThoughts.clear();
        if(thoughtCard)thoughtCard.hidden=true;
        states.forEach(state=>{state.signature='';state.notes=[];});
        particles.length=0;spokenItems.length=0;
        for(const item of snapshot.exhibition_speech||[]){
          const role=names.indexOf(item.who);
          if(role>=0)spokenItems.push({key:'restored:'+item.id,text:item.text,role,light:moodLight('',role)});
        }
        synchronize();
      }
      if(snapshot.interaction){const p=snapshot.interaction;start(p.who,p.target,p.tone,p.who+':'+p.at);}else if(!snapshot.speaker)turn.goal=0;
      let changed=false;
      names.forEach((name,i)=>{
        const notes=snapshot.puppets[name]?.exhibition_thoughts??snapshot.puppets[name]?.private_thoughts??[],signature=JSON.stringify(notes);
        const state=states[i];
        if(state.signature===signature)return;
        queueThought(name,notes.at(-1));changed=true;state.signature=signature;state.notes=notes;
        const actor=document.querySelector('.actor[data-name="'+name+'"]');
        if(actor){actor.dataset.material=notes.length?'formed':'waiting';actor.querySelector('.thought-excerpt').textContent=notes.at(-1)?.feeling||'';}
      });
      if(changed)synchronize();
    },
    connectAudio(audioContext,source){if(!analyser||analyser.context!==audioContext){analyser=audioContext.createAnalyser();analyser.fftSize=256;bins=new Uint8Array(analyser.fftSize);}source.connect(analyser);}
  };
})();
