/* Three-dimensional local flocking + an analytic curl field. Color/role never partitions neighbors. */
(function(root){
  'use strict';
  class TextFlock3D {
    constructor(particles,options={}){this.options=options;this.particles=particles;this.cell=options.perception||.16;this.grid=new Map();this.acceleration=new Float32Array(particles.length*3);}
    key(x,y,z){return ((x+64)*128+y+64)*128+z+64;}
    step(dt,time,activity,focus){
      const ps=this.particles,g=this.grid,cell=this.cell,a=this.acceleration,o=this.options;g.clear();
      const centers=new Map();
      if(o.sameRoleCohesion)for(const p of ps){let c=centers.get(p.role);if(!c)centers.set(p.role,c={x:0,y:0,z:0,vx:0,vy:0,vz:0,n:0});c.x+=p.x;c.y+=p.y;c.z+=p.z;c.vx+=p.vx;c.vy+=p.vy;c.vz+=p.vz;c.n++;}
      for(let i=0;i<ps.length;i++){const p=ps[i],key=this.key(Math.floor(p.x/cell),Math.floor(p.y/cell),Math.floor(p.z/cell));let bucket=g.get(key);if(!bucket)g.set(key,bucket=[]);bucket.push(i);}
      for(let i=0;i<ps.length;i++){
        const p=ps[i],gx=Math.floor(p.x/cell),gy=Math.floor(p.y/cell),gz=Math.floor(p.z/cell);
        let sx=0,sy=0,sz=0,ax=0,ay=0,az=0,cx=0,cy=0,cz=0,n=0,weightSum=0;
        const local=[{x:0,y:0,z:0,vx:0,vy:0,vz:0,n:0},{x:0,y:0,z:0,vx:0,vy:0,vz:0,n:0}];
        // Bounded local perception, with all three colors in the same neighborhood.
        search:for(let dz=-1;dz<=1;dz++)for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++){
          const bucket=g.get(this.key(gx+dx,gy+dy,gz+dz));if(!bucket)continue;
          for(const j of bucket){if(j===i)continue;const q=ps[j],x=p.x-q.x,y=p.y-q.y,z=p.z-q.z,d2=x*x+y*y+z*z;if(d2>cell*cell||d2<1e-8)continue;
            // Role affects attraction and alignment, while separation stays color-blind.
            const weight=p.role===q.role?(o.sameRoleNeighborWeight??1):(o.crossRoleNeighborWeight??1);
            ax+=q.vx*weight;ay+=q.vy*weight;az+=q.vz*weight;cx+=q.x*weight;cy+=q.y*weight;cz+=q.z*weight;weightSum+=weight;n++;
            const group=local[p.role===q.role?0:1];
            group.x+=q.x-p.x;group.y+=q.y-p.y;group.z+=q.z-p.z;
            group.vx+=q.vx-p.vx;group.vy+=q.vy-p.vy;group.vz+=q.vz-p.vz;group.n++;
            const comfort=o.separationDistance||.08;
            if(d2<comfort*comfort){const d=Math.sqrt(d2),push=(comfort-d)/(comfort*d);sx+=x*push;sy+=y*push;sz+=z*push;}
            if(n>=16)break search;
          }
        }
        const separation=o.separationWeight||.30;
        let fx=sx*separation,fy=sy*separation,fz=sz*separation;
        const independent=o.sameRoleAttraction!==undefined||o.crossRoleAttraction!==undefined;
        if(independent){
          for(let groupIndex=0;groupIndex<2;groupIndex++){
            const group=local[groupIndex];if(!group.n)continue;
            const attraction=groupIndex===0?(o.sameRoleAttraction??0):(o.crossRoleAttraction??0);
            const following=groupIndex===0?(o.sameRoleFollowing??0):(o.crossRoleFollowing??0);
            fx+=(group.x*attraction+group.vx*following)/group.n;
            fy+=(group.y*attraction+group.vy*following)/group.n;
            fz+=(group.z*attraction+group.vz*following)/group.n;
          }
        }
        if(!independent&&weightSum){const strength=weightSum/n,alignment=(o.localAlignment??.4)*strength,cohesion=(o.localCohesion??.08)*strength;fx+=(ax/weightSum-p.vx)*alignment+(cx/weightSum-p.x)*cohesion;fy+=(ay/weightSum-p.vy)*alignment+(cy/weightSum-p.y)*cohesion;fz+=(az/weightSum-p.vz)*alignment+(cz/weightSum-p.z)*cohesion;}
        const t=time*.16,x=p.x,y=p.y,z=p.z;
        // Curl of A=(sin(1.4y+t)cos(1.6z), sin(1.5z+t)cos(1.7x), sin(1.4x+t)cos(1.8y)).
        const curlX=-1.8*Math.sin(1.4*x+t)*Math.sin(1.8*y)-1.5*Math.cos(1.5*z+t)*Math.cos(1.7*x);
        const curlY=-1.6*Math.sin(1.4*y+t)*Math.sin(1.6*z)-1.4*Math.cos(1.4*x+t)*Math.cos(1.8*y);
        const curlZ=-1.7*Math.sin(1.5*z+t)*Math.sin(1.7*x)-1.4*Math.cos(1.4*y+t)*Math.cos(1.6*z);
        const influence=(o.flowGain||1)*(.026+activity*.024*Math.exp(-((x-focus)**2+y*y+z*z)*1.4));
        const flowRelaxation=o.flowRelaxation??1.6;
        fx+=(curlX*influence+z*.045-p.vx)*flowRelaxation;fy+=(curlY*influence-p.vy)*flowRelaxation;fz+=(curlZ*influence-x*.035-p.vz)*flowRelaxation;
        // One soft 3D envelope, not separate cages for individual characters.
        const span=o.flightSpan||1,horizontal=o.horizontalSpan||1;
        const r=Math.sqrt(x*x/(2.25*span*span*horizontal*horizontal)+y*y/(.49*span*span)+z*z/(.64*span*span)),edge=Math.max(0,r-.85)*(o.boundaryGain??.35);
        fx-=x*edge/2.25;fy-=y*edge/.49;fz-=z*edge/.64;
        if(o.sameRoleCohesion){const c=centers.get(p.role);if(c&&c.n>1){const k=o.sameRoleCohesion;fx+=(c.x/c.n-x)*k;fy+=(c.y/c.n-y)*k;fz+=(c.z/c.n-z)*k;const align=o.sameRoleAlignment||0;fx+=(c.vx/c.n-p.vx)*align;fy+=(c.vy/c.n-p.vy)*align;fz+=(c.vz/c.n-p.vz)*align;}}
        if(o.flight){
          const phase=p.role*Math.PI*2/3;
          const wander=o.wander||0,individual=(p.phase||0);
          const offset=wander*(.65*Math.sin(individual)+.18*Math.sin(time*.37+individual));
          const orbit=o.flightSpan ? .24 : .50,vertical=o.flightSpan ? .31 : .67;
          const t0=time*orbit+phase+offset;
          const tx=.95*span*horizontal*Math.sin(t0),ty=span*(.42*Math.sin(time*vertical+phase*1.3+offset)+wander*.16*Math.sin(time*.81+individual*1.7)),tz=.65*span*Math.cos(t0);
          const steer=o.guideStrength??.48,matching=o.guideAlignment??.32;
          fx+=(tx-x)*steer+(.95*span*horizontal*orbit*Math.cos(t0)-p.vx)*matching;
          fy+=(ty-y)*steer+(.42*span*vertical*Math.cos(time*vertical+phase*1.3+offset)-p.vy)*matching;
          fz+=(tz-z)*steer+(-.65*span*orbit*Math.sin(t0)-p.vz)*matching;
        }
        a[i*3]=fx;a[i*3+1]=fy;a[i*3+2]=fz;
      }
      const damping=Math.exp(-dt*.35);
      for(let i=0;i<ps.length;i++){
        const p=ps[i];p.vx=(p.vx+a[i*3]*dt)*damping;p.vy=(p.vy+a[i*3+1]*dt)*damping;p.vz=(p.vz+a[i*3+2]*dt)*damping;
        // Smooth flock pulse plus individual pace variation, without frame-to-frame jitter.
        const variation=o.speedVariation||0;
        const arousal=p.arousal||0,burst=Math.pow(.5+.5*Math.sin(time*1.05+(p.phase||0)),4);
        const emotionPace=1+arousal*(.30+burst*2.8);
        const pace=emotionPace*(1+variation*(.65*Math.sin(time*.48+p.role*2.094)+.35*Math.sin(time*.73+(p.phase||0))));
        const speed=Math.hypot(p.vx,p.vy,p.vz),cap=(o.maxSpeed||.20)*pace;
        const floor=(o.minSpeed||0)*pace;
        if(floor&&speed<floor&&speed>1e-8){p.vx*=floor/speed;p.vy*=floor/speed;p.vz*=floor/speed;}
        if(speed>cap){p.vx*=cap/speed;p.vy*=cap/speed;p.vz*=cap/speed;}
        // Drive actual speed toward a target, rather than merely lifting its ceiling.
        // Emotional surges accelerate individual heads and then visibly release them.
        if(o.speedVariation && Number.isFinite(p.arousal)){
          const current=Math.hypot(p.vx,p.vy,p.vz);
          const target=((o.minSpeed||.20)+((o.maxSpeed||.55)-(o.minSpeed||.20))*.30)*pace;
          const next=current+(target-current)*(1-Math.exp(-dt*3.5));
          if(current>1e-8){const gain=next/current;p.vx*=gain;p.vy*=gain;p.vz*=gain;}
        }
        p.x+=p.vx*dt;p.y+=p.vy*dt;p.z+=p.vz*dt;
      }
    }
  }
  if(typeof module!=='undefined'&&module.exports)module.exports=TextFlock3D;else root.TextFlock3D=TextFlock3D;
})(typeof window==='undefined'?{}:window);
