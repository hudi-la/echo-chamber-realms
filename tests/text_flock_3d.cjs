const assert=require('node:assert/strict');
const TextFlock3D=require('../echo/static/text-flock.js');
const particle=(x,y,z,role=0)=>({x,y,z,vx:0,vy:0,vz:0,role});
// Local separation must prevent coincident text from collapsing into one point.
const close=[particle(-.01,0,0),particle(.01,0,0,1)];
new TextFlock3D(close).step(.025,0,0,0);
assert.ok(close[1].x-close[0].x>.02);
// Roles/color labels must not create different physics or independent containers.
const originals=Array.from({length:72},(_,i)=>particle(Math.sin(i*2.3)*1.2,Math.cos(i*1.7)*.4,Math.sin(i*1.1)*.5,i%3));
const recolored=originals.map(p=>({...p,role:(p.role+1)%3}));
const a=new TextFlock3D(originals),b=new TextFlock3D(recolored);
for(let step=0;step<1200;step++){a.step(.025,step*.025,.7,.2);b.step(.025,step*.025,.7,.2);}
let depthMotion=0;
originals.forEach((p,i)=>{
  assert.deepEqual([p.x,p.y,p.z],[recolored[i].x,recolored[i].y,recolored[i].z]);
  assert.ok([p.x,p.y,p.z,p.vx,p.vy,p.vz].every(Number.isFinite));
  assert.ok(Math.abs(p.x)<2.5&&Math.abs(p.y)<1.5&&Math.abs(p.z)<1.5);
  assert.equal(p.role,i%3);
  depthMotion+=Math.abs(p.z-Math.sin(i*1.1)*.5);
});
assert.ok(depthMotion/originals.length>.03,'actual depth motion, not a flat projection');
// Alignment brings initially opposing neighbors toward a common local heading.
const neighbors=[{...particle(-.07,0,0),vx:.1},{...particle(.07,0,0,2),vx:-.1}];
new TextFlock3D(neighbors).step(.025,0,0,0);
assert.ok(Math.abs(neighbors[0].vx-neighbors[1].vx)<.2);
console.log('3D flock: separation, alignment, role-independent mixing, depth motion, 30s stability passed.');
