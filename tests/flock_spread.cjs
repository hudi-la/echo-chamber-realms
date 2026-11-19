const assert=require('node:assert/strict'),Flock=require('../echo/static/text-flock.js');
const make=()=>Array.from({length:60},(_,i)=>{const role=i%3,t=i*2.399963,a=role*Math.PI*2/3+.25;return {role,phase:t,x:(role-1)*.58+.12*Math.sin(t),y:.23*Math.sin(a)+.09*Math.cos(t),z:.35*Math.cos(a)+.08*Math.sin(t),vx:-Math.sin(a)*.30,vy:.08*Math.sin(t),vz:Math.cos(a)*.30};});
const before=make(),after=make();
const old=new Flock(before,{perception:.70,maxSpeed:.55,minSpeed:.26,flight:true,flowGain:2,sameRoleCohesion:.24,sameRoleAlignment:.65});
const loose=new Flock(after,{perception:.85,maxSpeed:.55,minSpeed:.26,flight:true,flowGain:2,sameRoleCohesion:.102,sameRoleAlignment:.26,localCohesion:.025,localAlignment:.18,separationDistance:.302,separationWeight:1.2,wander:1.04,guideStrength:.22,guideAlignment:.18});
for(let i=0;i<2400;i++){old.step(1/60,i/60,.6,0);loose.step(1/60,i/60,.6,0);}
function nearestMean(ps){return ps.reduce((sum,p,i)=>sum+Math.min(...ps.filter((q,j)=>i!==j&&q.role===p.role).map(q=>Math.hypot(p.x-q.x,p.y-q.y,p.z-q.z))),0)/ps.length;}
const previous=nearestMean(before),current=nearestMean(after);
assert.ok(current>previous*1.5,'same-color heads should visibly spread rather than lock onto one path');
assert.ok(after.every(p=>[p.x,p.y,p.z,p.vx,p.vy,p.vz].every(Number.isFinite)));
console.log(JSON.stringify({durationSeconds:40,heads:60,previousNearestHeadMean:previous,adjustedNearestHeadMean:current,ratio:current/previous}));
