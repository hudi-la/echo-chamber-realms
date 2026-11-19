const assert=require('node:assert/strict');
const Flock=require('../echo/static/text-flock.js');
const base=[{x:0,y:0,z:0,vx:0,vy:0,vz:0,role:0},{x:.5,y:0,z:0,vx:.1,vy:0,vz:0,role:0},{x:0,y:.5,z:0,vx:0,vy:.1,vz:0,role:1}];
function acceleration(extra){const ps=base.map(p=>({...p}));const f=new Flock(ps,{perception:1,sameRoleAttraction:0,crossRoleAttraction:0,sameRoleFollowing:0,crossRoleFollowing:0,...extra});f.step(.01,0,0,0);return [...f.acceleration.slice(0,3)];}
const zero=acceleration({});
for(const [key,axis,expected]of [['sameRoleAttraction',0,.1],['crossRoleAttraction',1,.1],['sameRoleFollowing',0,.02],['crossRoleFollowing',1,.02]]){
 const a=acceleration({[key]:.2});for(let i=0;i<3;i++)assert.ok(Math.abs(a[i]-zero[i]-(i===axis?expected:0))<1e-6,key+' must affect only its own neighbor group');
}
const old={perception:.85,maxSpeed:.55,minSpeed:.26,speedVariation:.24,flight:true,flowGain:2,sameRoleCohesion:.10,sameRoleAlignment:.32,sameRoleNeighborWeight:1.65,crossRoleNeighborWeight:.40,localCohesion:.045,localAlignment:.24,separationDistance:.30,separationWeight:1.2,wander:1.05,guideStrength:.30,guideAlignment:.18,flightSpan:2.4,horizontalSpan:1.7};
const revised={...old,sameRoleCohesion:.02,sameRoleAlignment:.10,sameRoleAttraction:.06,crossRoleAttraction:.004,sameRoleFollowing:.30,crossRoleFollowing:.03,flowRelaxation:.65,boundaryGain:.12,guideStrength:.42};
function spread(options){
 const ps=Array.from({length:60},(_,i)=>{const phase=i*2.399963,role=i%3;return {role,phase,arousal:i%7===0?.8:0,x:(role-1)*.58+.12*Math.sin(phase),y:.1*Math.cos(phase),z:.35*Math.cos(role*2.094),vx:.2,vy:.03,vz:.1};});
 const f=new Flock(ps,options);let total=0,samples=0;
 for(let s=0;s<3600;s++){f.step(1/60,s/60,.4,0);for(const p of ps)assert.ok([p.x,p.y,p.z].every(Number.isFinite));if(s>2400&&s%60===0){for(const p of ps)total+=Math.hypot(p.x,p.y,p.z);samples+=ps.length;}}
 return total/samples;
}
const before=spread(old),after=spread(revised);
assert.ok(after>before*1.15,'revised forces should spend more time away from the shared origin');
console.log(JSON.stringify({independentGroupControls:'passed',durationSeconds:60,oldMeanRadius:before,newMeanRadius:after,ratio:after/before}));
