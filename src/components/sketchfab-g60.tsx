'use client';

import { useEffect, useRef, useState } from 'react';
import { G60Controller, DEMO_REGIONS, type ViewerAPI, type SceneSettings, type SurfaceProjection } from '@/lib/sketchfab-controller';
import type { CameraView } from '@/lib/vehicle-priority';
export const G60_SKETCHFAB_URL='https://sketchfab.com/models/ee328c2302494193a05cb4949b17ae55/embed';
type SketchfabConstructor=new(version:string,frame:HTMLIFrameElement)=>{init:(id:string,options:{autostart:number;preload:number;camera:number;autospin:number;success:(api:ViewerAPI)=>void;error:(error:unknown)=>void})=>void};
let scriptPromise:Promise<SketchfabConstructor>|undefined;
function loadViewer(){
  if(!scriptPromise)scriptPromise=new Promise<SketchfabConstructor>((resolve,reject)=>{
    const existing=(window as unknown as {Sketchfab?:SketchfabConstructor}).Sketchfab;if(existing){resolve(existing);return;}
    const script=document.createElement('script');script.src='https://static.sketchfab.com/api/sketchfab-viewer-1.12.1.js';script.async=true;
    script.onload=()=>{const sdk=(window as unknown as {Sketchfab?:SketchfabConstructor}).Sketchfab;if(sdk)resolve(sdk);else{scriptPromise=undefined;script.remove();reject(new Error('Sketchfab API unavailable.'));}};
    script.onerror=()=>{script.remove();scriptPromise=undefined;reject(new Error('Could not load Sketchfab. Check your connection and retry.'));};document.head.appendChild(script);
  });return scriptPromise;
}
export function SketchfabG60({highlighted,concepts,opacity,view,reset}:SceneSettings&{view:CameraView;reset:number}){
  const frame=useRef<HTMLIFrameElement>(null),controller=useRef<G60Controller|null>(null);
  const [surfaces,setSurfaces]=useState<SurfaceProjection[]>([]),[projectionError,setProjectionError]=useState('');
  const [ready,setReady]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[applying,setApplying]=useState(false),[attempt,setAttempt]=useState(0);
  useEffect(()=>{
    let cancelled=false;setReady(false);setError('');setSurfaces([]);
    const timer=setTimeout(()=>{if(!cancelled)setError('The hosted model is taking longer than expected. It needs an internet connection and a browser with WebGL enabled.');},120000);
    loadViewer().then(SDK=>{
      if(cancelled||!frame.current)return;
      new SDK('1.12.1',frame.current).init('ee328c2302494193a05cb4949b17ae55',{autostart:1,preload:1,camera:0,autospin:0,success(api){
        if(cancelled)return;api.start();api.addEventListener('viewerready',()=>{
          if(cancelled)return;
          const instance=new G60Controller(api);controller.current=instance;
          instance.initialize().then(()=>{if(!cancelled){clearTimeout(timer);setError('');setReady(true);}}).catch(e=>{if(!cancelled){clearTimeout(timer);setError(e.message);}});
        });
      },error(){if(!cancelled){clearTimeout(timer);setError('The hosted G60 could not start. Check your connection and WebGL support.');}}});
    }).catch(e=>{if(!cancelled){clearTimeout(timer);setError(e.message);}});
    return()=>{cancelled=true;clearTimeout(timer);controller.current?.dispose();controller.current=null;};
  },[attempt]);
  const selection=highlighted.join(','),changes=concepts.join(',');
  useEffect(()=>{if(!ready||!controller.current)return;let current=true;setApplying(true);setNotice('');controller.current.apply({highlighted,concepts,opacity}).then(message=>{if(current){setNotice(message);setApplying(false);}}).catch(e=>{if(current){setNotice('Preview update failed: '+e.message);setApplying(false);}});return()=>{current=false;};},[ready,selection,changes,opacity]);
  useEffect(()=>{if(ready)controller.current?.camera(view,highlighted);},[ready,view,reset,selection]);
  useEffect(()=>{
    if(!ready||!controller.current)return;
    let current=true,busy=false;setSurfaces([]);setProjectionError('');
    const instance=controller.current;
    const update=async()=>{if(busy||!current)return;busy=true;try{const value=await instance.projectSurfaces({highlighted,concepts,opacity});if(current){setSurfaces(value);setProjectionError('');}}catch{if(current){setSurfaces([]);setProjectionError('Surface marker unavailable. Reload the model to retry.');}}finally{busy=false;}};
    void update();const timer=setInterval(()=>void update(),120);
    return()=>{current=false;clearInterval(timer);};
  },[ready,selection,changes]);
  return <div className="sketchfab-g60" data-viewer-ready={ready}>
    <div className="sketchfab-reference-label"><span>2024 BMW G60</span><span>{ready?'Connected to hosted model':'Loading hosted model…'}</span></div>
    <div className="hosted-model-stage">    <iframe key={attempt} ref={frame} title="2024 BMW G60 by SLGA on Sketchfab" allow="autoplay; fullscreen; xr-spatial-tracking" allowFullScreen referrerPolicy="strict-origin-when-cross-origin"/>
    <svg className="model-surfaces" aria-label="Projected design surfaces">{surfaces.map(surface=>{
      const {points,part,changed,selected}=surface;
      const center=[points.reduce((sum,p)=>sum+p[0],0)/4,points.reduce((sum,p)=>sum+p[1],0)/4];
      const mix=(a:number[],b:number[],t:number)=>a.map((v,i)=>v+(b[i]-v)*t);
      return <g key={part} className={'model-surface'+(selected?' selected':'')+(changed?' changed':'')} data-surface={part} data-changed={changed}>
        <polygon points={points.map(p=>p.slice(0,2).join(',')).join(' ')} />
        {part==='vents'&&[.2,.4,.6,.8].map(t=>{const a=mix(points[0],points[3],t),b=mix(points[1],points[2],t);return <line key={t} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]}/>;})}
        {part!=='vents'&&<text x={center[0]} y={center[1]} textAnchor="middle" dominantBaseline="middle">{part==='screen'?(changed?'DISPLAY +80%':'DISPLAY'):DEMO_REGIONS[part]?.label}</text>}
      </g>;
    })}</svg>{(surfaces.length>0||concepts.includes('seats'))&&<div className="model-surface-label">{concepts.includes('seats')?'NEW SEATS · teal upholstery':surfaces.some(s=>DEMO_REGIONS[s.part])?'Selected component region':concepts.includes('screen')?'Display surface · +80% width':concepts.includes('vents')?'Vent opening · 3× height':'Selected dashboard region'}<small>{concepts.includes('seats')?'Seat redesign demo applied':'Approximate concept highlight · x-ray view'}</small></div>}</div>
    <div className="hosted-model-status" role="status">{error?<><span>{error}</span><button onClick={()=>setAttempt(a=>a+1)}>Retry model</button></>:!ready?'Loading the model and its editable parts…':applying?'Updating hosted model…':notice||projectionError||((highlighted.length||concepts.length)?'Preview applied to the hosted G60.':'Hosted G60 ready. Select a problem to explore.')}</div>
    <p className="sketchfab-attribution"><a href="https://sketchfab.com/3d-models/2024-bmw-g60-ee328c2302494193a05cb4949b17ae55" target="_blank" rel="noopener noreferrer nofollow">2024 BMW G60</a> by <a href="https://sketchfab.com/csperamune" target="_blank" rel="noopener noreferrer nofollow">SLGA</a> on Sketchfab</p>
  </div>;
}
