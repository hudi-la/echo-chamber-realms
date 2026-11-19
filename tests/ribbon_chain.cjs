const assert=require('node:assert/strict');
const Chain=require('../echo/static/ribbon-chain.js');
const Flock=require('../echo/static/text-flock.js');
function head(){return {x:0,y:.5,z:0,vx:.25,vy:0,vz:0,phase:0};}
const h=head(),chain=new Chain(h,2,36);
for(let s=0;s<1800;s++){
 const t=s/60;h.x=Math.sin(t*.5)*.7;h.y=.5+Math.cos(t*.6)*.25;h.z=Math.cos(t*.5)*.5;h.vx=.35*Math.cos(t*.5);h.vz=-.25*Math.sin(t*.5);
 chain.step(1/60,t);
 const first=chain.nodes[0];assert.deepEqual([first.x,first.y,first.z],[h.x,h.y,h.z]);
 for(const p of chain.nodes)assert.ok([p.x,p.y,p.z].every(Number.isFinite));
}
let maxError=0;for(let i=1;i<chain.nodes.length;i++){const a=chain.nodes[i-1],b=chain.nodes[i];maxError=Math.max(maxError,Math.abs(Math.hypot(b.x-a.x,b.y-a.y,b.z-a.z)-chain.spacing)/chain.spacing);}
assert.ok(maxError<.25,'tail maintains finite segment lengths');
const a=head(),b=head(),gravity=new Chain(a,1.2,24),zero=new Chain(b,1.2,24);
for(let s=0;s<240;s++){a.x=b.x=s/60*.10;gravity.step(1/60,s/60,.12);zero.step(1/60,s/60,0);}
assert.ok(gravity.nodes.at(-1).y<zero.nodes.at(-1).y-.03,'gravity produces extra tail sag');
assert.ok(Math.hypot(chain.nodes.at(-1).x-h.x,chain.nodes.at(-1).z-h.z)>.2,'tail lags behind its leading head');
// In a symmetric four-head scene, role-based cohesion adds acceleration toward the same-color peer.
const base=[{x:-.45,y:0,z:0,vx:0,vy:0,vz:0,role:0},{x:.45,y:0,z:0,vx:0,vy:0,vz:0,role:0},{x:-.2,y:0,z:0,vx:0,vy:0,vz:0,role:1},{x:.2,y:0,z:0,vx:0,vy:0,vz:0,role:1}];
const plain=base.map(p=>({...p})),grouped=base.map(p=>({...p}));
new Flock(plain,{perception:1}).step(.025,0,0,0);
new Flock(grouped,{perception:1,sameRoleCohesion:.24,sameRoleAlignment:.65}).step(.025,0,0,0);
assert.ok(grouped[0].vx>plain[0].vx);assert.ok(grouped[1].vx<plain[1].vx);
console.log('Ribbon physics: pinned head, trailing inertia, gravity sag, constraints, 30s stability, stronger same-color attraction passed.');
const flying=Array.from({length:9},(_,i)=>({x:(i%3-1)*.6,y:Math.sin(i)*.1,z:Math.cos(i)*.3,vx:.1,vy:.03,vz:.1,role:i%3,phase:i}));
const flight=new Flock(flying,{perception:.7,maxSpeed:.55,minSpeed:.26,flight:true,flowGain:2,sameRoleCohesion:.24,sameRoleAlignment:.65});
const tails=flying.map(p=>new Chain(p,1.8,36));
for(let s=0;s<1800;s++){
 flight.step(1/60,s/60,.7,0);tails.forEach(t=>t.step(1/60,s/60));
 for(const p of flying){assert.ok([p.x,p.y,p.z,p.vx,p.vy,p.vz].every(Number.isFinite));assert.ok(Math.hypot(p.vx,p.vy,p.vz)>=.259);}
 for(const tail of tails)for(const p of tail.nodes)assert.ok([p.x,p.y,p.z].every(Number.isFinite));
}
console.log('Three flying flocks plus nine inertial tails: 30s coupled simulation passed.');
// Identical neighbor geometry: same-role neighbors exert stronger alignment than cross-role ones.
function localInfluence(role){
 const ps=[{x:0,y:0,z:0,vx:0,vy:0,vz:0,role:0},{x:.4,y:0,z:0,vx:.2,vy:.15,vz:0,role}];
 const f=new Flock(ps,{perception:1,sameRoleNeighborWeight:1.65,crossRoleNeighborWeight:.4});
 f.step(.01,0,0,0);return f.acceleration[1];
}
assert.ok(localInfluence(0)>localInfluence(1)*4,'same-color following is stronger than cross-color following');
console.log('Weighted local following: same-color influence >4x cross-color influence passed.');
// Emotional energy changes actual travel speed, including occasional smooth surges.
function emotionalSpeed(arousal){
 const ps=[{x:0,y:0,z:0,vx:.26,vy:0,vz:0,role:0,phase:1,arousal}];
 const f=new Flock(ps,{maxSpeed:.55,minSpeed:.26,speedVariation:.24,flight:true,flightSpan:1.9});
 let total=0,min=Infinity,max=0;
 for(let i=0;i<1800;i++){f.step(1/60,i/60,0,0);const v=Math.hypot(ps[0].vx,ps[0].vy,ps[0].vz);assert.ok(Number.isFinite(v));total+=v;min=Math.min(min,v);max=Math.max(max,v);}
 return {mean:total/1800,min,max};
}
const calmSpeed=emotionalSpeed(0),angrySpeed=emotionalSpeed(1);
assert.ok(angrySpeed.mean>calmSpeed.mean*1.25,'angry sentences travel faster than calm sentences');
assert.ok(angrySpeed.max>angrySpeed.min*1.4,'emotional sentences have varying pace');
console.log('Emotion speed:',JSON.stringify({calm:calmSpeed,angry:angrySpeed}));
