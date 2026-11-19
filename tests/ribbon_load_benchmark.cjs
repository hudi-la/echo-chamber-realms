/* Offline simulation benchmark; no model, memory, audio or browser is accessed. */
const assert=require('node:assert/strict');
const {performance}=require('node:perf_hooks');
const fs=require('node:fs');
const Flock=require('../echo/static/text-flock.js'),Chain=require('../echo/static/ribbon-chain.js');
const results=[];
for(const count of [30,60,120,180]){
 const heads=Array.from({length:count},(_,i)=>{
  const role=i%3,theta=i*2.399963,angle=role*Math.PI*2/3+.25;
  return {role,phase:theta,x:(role-1)*.58+.12*Math.sin(theta),y:.23*Math.sin(angle)+.09*Math.cos(theta),z:.35*Math.cos(angle)+.08*Math.sin(theta),vx:-Math.sin(angle)*.3,vy:.08*Math.sin(theta),vz:Math.cos(angle)*.3};
 });
 const flock=new Flock(heads,{perception:.7,maxSpeed:.55,minSpeed:.26,flight:true,flowGain:2,sameRoleCohesion:.24,sameRoleAlignment:.65});
 const tails=heads.map((p,i)=>new Chain(p,1.6+i%12/10,36)),samples=[];
 for(let step=0;step<240;step++){
  const begin=performance.now();flock.step(1/60,step/60,.7,0);for(const chain of tails)chain.step(1/60,step/60);
  if(step>=60)samples.push(performance.now()-begin);
 }
 for(const chain of tails)for(const p of chain.nodes)assert.ok([p.x,p.y,p.z].every(Number.isFinite));
 samples.sort((a,b)=>a-b);
 const result={sentences:count,heads:count,tailNodes:count*37,physicsMeanMs:+(samples.reduce((a,b)=>a+b,0)/samples.length).toFixed(2),physicsP95Ms:+samples[Math.floor(samples.length*.95)].toFixed(2),stable:true};
 results.push(result);console.log(JSON.stringify(result));
}
fs.writeFileSync('artifacts/thought-field-preview/physics-load-results.json',JSON.stringify({note:'CPU physics only; browser drawing measured separately.',results},null,2));
