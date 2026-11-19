/* A pinned head and a flexible, inextensible 3D Verlet chain with gravity and aerodynamic drag. */
(function(root){
  'use strict';
  class RibbonChain3D {
    constructor(head,length,segments=32){
      this.head=head;this.length=length;this.spacing=length/segments;this.nodes=[];
      const speed=Math.hypot(head.vx,head.vy,head.vz)||1;
      for(let i=0;i<=segments;i++){
        const s=i*this.spacing;
        const x=head.x-head.vx/speed*s,y=head.y-head.vy/speed*s-.03*Math.sin(i*.3),z=head.z-head.vz/speed*s;
        this.nodes.push({x,y,z,px:x-head.vx/60,py:y-head.vy/60,pz:z-head.vz/60});
      }
    }
    step(dt,time,gravity=.002){
      const ns=this.nodes,h=this.head,drag=Math.exp(-dt*.38),ds=dt*dt;
      ns[0].x=h.x;ns[0].y=h.y;ns[0].z=h.z;
      for(let i=1;i<ns.length;i++){
        const p=ns[i],vx=(p.x-p.px)*drag,vy=(p.y-p.py)*drag,vz=(p.z-p.pz)*drag;
        p.px=p.x;p.py=p.y;p.pz=p.z;
        const exposure=i/(ns.length-1);
        // Shared three-dimensional airflow; relative drag preserves a trailing wake.
        const t=time*.38,phase=h.phase||0;
        const airX=.24*Math.sin(p.y*1.4+t)+.12*Math.cos(p.z*1.7-t);
        const airY=.22*Math.sin(p.z*1.5+t*.9)+.12*Math.cos(p.x*1.6-t);
        const airZ=.24*Math.sin(p.x*1.4-t)+.12*Math.cos(p.y*1.8+t);
        const coupling=.8,flutter=.045*exposure;
        p.x+=vx+(coupling*(airX+h.vx*.35-vx/dt)+flutter*Math.sin(time*1.3+phase+exposure*4))*ds;
        p.y+=vy+(-gravity+coupling*(airY+h.vy*.35-vy/dt))*ds;
        p.z+=vz+(coupling*(airZ+h.vz*.35-vz/dt)+flutter*Math.cos(time*1.1+phase+exposure*4))*ds;
      }
      for(let pass=0;pass<14;pass++){
        ns[0].x=h.x;ns[0].y=h.y;ns[0].z=h.z;
        for(let i=1;i<ns.length;i++){
          const a=ns[i-1],b=ns[i],dx=b.x-a.x,dy=b.y-a.y,dz=b.z-a.z,d=Math.hypot(dx,dy,dz)||1e-9;
          const k=(d-this.spacing)/d;
          if(i===1){b.x-=dx*k;b.y-=dy*k;b.z-=dz*k;}
          else{a.x+=dx*k*.5;a.y+=dy*k*.5;a.z+=dz*k*.5;b.x-=dx*k*.5;b.y-=dy*k*.5;b.z-=dz*k*.5;}
        }
        // Weak bending stiffness keeps the strip supple without letting adjacent letters fold flat.
        for(let i=2;i<ns.length;i++){
          const a=ns[i-2],b=ns[i],dx=b.x-a.x,dy=b.y-a.y,dz=b.z-a.z,d=Math.hypot(dx,dy,dz)||1e-9;
          const k=(d-this.spacing*1.97)/d*.045;
          if(i>2){a.x+=dx*k*.5;a.y+=dy*k*.5;a.z+=dz*k*.5;}
          b.x-=dx*k*.5;b.y-=dy*k*.5;b.z-=dz*k*.5;
        }
      }
      ns[0].x=h.x;ns[0].y=h.y;ns[0].z=h.z;
    }
  }
  if(typeof module!=='undefined'&&module.exports)module.exports=RibbonChain3D;else root.RibbonChain3D=RibbonChain3D;
})(typeof window==='undefined'?{}:window);
