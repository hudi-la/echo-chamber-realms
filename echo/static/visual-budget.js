/* Adaptive visual-only budget. Audio transport and model timing never depend on it. */
(function(root){
  'use strict';
  class VisualBudget {
    constructor(){this.level=1;this.bad=0;this.good=0;this.lastChange=-Infinity;}
    profile(audio=false){
      const tiers=[
        {dpr:1.75,waveSamples:40,waveLanes:7,waveHeads:10,starStride:1,fps:60},
        {dpr:1.4,waveSamples:28,waveLanes:5,waveHeads:8,starStride:2,fps:60},
        {dpr:1.1,waveSamples:18,waveLanes:4,waveHeads:6,starStride:3,fps:45},
        {dpr:.85,waveSamples:10,waveLanes:3,waveHeads:4,starStride:5,fps:30},
        {dpr:.7,waveSamples:0,waveLanes:0,waveHeads:0,starStride:8,fps:20}
      ];
      const p={...tiers[this.level]};if(audio)p.fps=Math.min(30,p.fps);return p;
    }
    observe({fps,costMs,audio=false,seconds=1.5,now,stalled=false}){
      const target=this.profile(audio).fps,budget=audio?8:12;
      const overloaded=stalled||fps<target*.78||costMs>budget;
      this.bad=overloaded?this.bad+seconds:0;
      this.good=!overloaded&&!audio&&fps>=target*.94&&costMs<budget*.65?this.good+seconds:0;
      if(this.level<4&&(stalled||this.bad>=3)&&now-this.lastChange>=2000){
        this.level++;this.bad=0;this.good=0;this.lastChange=now;
      }else if(this.level>0&&this.good>=30&&now-this.lastChange>=30000){
        this.level--;this.good=0;this.lastChange=now;
      }
      return this.level;
    }
  }
  if(typeof module!=='undefined'&&module.exports)module.exports=VisualBudget;else root.VisualBudget=VisualBudget;
})(typeof window==='undefined'?{}:window);
