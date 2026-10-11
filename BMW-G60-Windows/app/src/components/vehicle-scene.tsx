'use client';

import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { createG60Geometry } from '@/lib/g60-geometry';
import { COMPONENTS, type CameraView, type ComponentId, type Concept, type Priority } from '@/lib/vehicle-priority';

type Props = {highlighted:ComponentId[]; applied: Concept[]; priorities: Record<ComponentId,Priority>; selected: ComponentId|null; concept: Concept; opacity: number; view: CameraView; reset: number; onSelect: (id:ComponentId)=>void};
export default function VehicleScene(props: Props) {
  const host=useRef<HTMLDivElement>(null),api=useRef<ReturnType<typeof createG60Geometry>|null>(null);
  const cameraApi=useRef<((view:CameraView)=>void)|null>(null),latest=useRef(props),[error,setError]=useState('');
  useEffect(()=>{latest.current=props;api.current?.setStyle(props.priorities,props.selected,props.opacity);api.current?.setConcept(props.concept,props.applied);api.current?.setFocus(props.highlighted,window.matchMedia('(prefers-reduced-motion: reduce)').matches);},[props]);
  useEffect(()=>{cameraApi.current?.(props.view);},[props.view,props.reset,props.selected]);
  useEffect(()=>{
    const element=host.current;if(!element)return;
    let renderer:THREE.WebGLRenderer;
    try {renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});}
    catch {setError('3D rendering is unavailable in this browser. Enable hardware acceleration or use a WebGL 2 browser. The component list and evidence remain available.');return;}
    renderer.setPixelRatio(Math.min(window.devicePixelRatio,2));renderer.outputColorSpace=THREE.SRGBColorSpace;
    renderer.setClearColor('#eaf2f9',0);renderer.domElement.setAttribute('aria-label','Interactive translucent G60 model. Drag to rotate, scroll to zoom, or select components below.');
    renderer.domElement.setAttribute('role','img');element.prepend(renderer.domElement);
    const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(37,1,.05,100);
    const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.enablePan=false;controls.minDistance=2;controls.maxDistance=12;controls.maxPolarAngle=Math.PI*.49;
    scene.add(new THREE.HemisphereLight('#f1f8ff','#7194b3',2.8));
    const key=new THREE.DirectionalLight('#ffffff',3);key.position.set(3,7,5);scene.add(key);
    const fill=new THREE.DirectionalLight('#99c9ff',2);fill.position.set(-3,3,-4);scene.add(fill);
    const car=createG60Geometry();scene.add(car.root);api.current=car;
    car.setStyle(latest.current.priorities,latest.current.selected,latest.current.opacity);car.setConcept(latest.current.concept,latest.current.applied);
    car.setFocus(latest.current.highlighted,window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    const grid=new THREE.GridHelper(12,36,'#a0b9ce','#d3e0ec');grid.position.y=-.035;scene.add(grid);
    const gridMaterials=Array.isArray(grid.material)?grid.material:[grid.material];gridMaterials.forEach(m=>{m.transparent=true;m.opacity=.45;});
    const cameraTarget=new THREE.Vector3(),lookTarget=new THREE.Vector3();
    const reducedMotion=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let cameraMoving=false;
    controls.addEventListener('start',()=>{cameraMoving=false;});
    const setCamera=(view:CameraView)=>{
      const positions:Record<CameraView,[number,number,number]>={exterior:[5.8,3.9,6.2],cabin:latest.current.selected==='seats'?[-2.2,2.1,2.4]:[-1.35,1.85,2.25],top:[.01,7,.001],side:[0,1.6,7.2]};
      cameraTarget.set(...positions[view]);lookTarget.set(view==='cabin'?.05:0,view==='cabin'?1:.55,0);cameraMoving=true;
      if(reducedMotion){camera.position.copy(cameraTarget);controls.target.copy(lookTarget);cameraMoving=false;}
      controls.update();
    };
    camera.position.set(5.8,3.9,6.2);controls.target.set(0,.55,0);cameraApi.current=setCamera;setCamera(latest.current.view);
    const observer=new ResizeObserver(()=>{const {width,height}=element.getBoundingClientRect();if(width&&height){renderer.setSize(width,height);camera.aspect=width/height;camera.updateProjectionMatrix();}});observer.observe(element);
    let visible=true;const intersection=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;});intersection.observe(element);
    const raycaster=new THREE.Raycaster(),pointer=new THREE.Vector2();let down:[number,number]=[0,0];
    const onDown=(event:PointerEvent)=>{down=[event.clientX,event.clientY];};
    const onUp=(event:PointerEvent)=>{
      if(Math.hypot(event.clientX-down[0],event.clientY-down[1])>5)return;
      const rect=renderer.domElement.getBoundingClientRect();pointer.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);raycaster.setFromCamera(pointer,camera);
      const hit=raycaster.intersectObjects(Object.values(car.components),true)[0];
      if(hit){let obj:THREE.Object3D|null=hit.object;while(obj&&!obj.userData.component)obj=obj.parent;if(obj)latest.current.onSelect(obj.userData.component as ComponentId);}
    };
    renderer.domElement.addEventListener('pointerdown',onDown);renderer.domElement.addEventListener('pointerup',onUp);
    let frame=0,previous=performance.now(),frames=0;const point=new THREE.Vector3();
    const draw=(now:number)=>{
      frame=requestAnimationFrame(draw);const delta=Math.min((now-previous)/1000,.05);previous=now;
      if(!visible||document.hidden)return;
      if(cameraMoving){camera.position.lerp(cameraTarget,1-Math.exp(-4*delta));controls.target.lerp(lookTarget,1-Math.exp(-4*delta));if(camera.position.distanceTo(cameraTarget)<.005)cameraMoving=false;}
      car.update(reducedMotion?2:delta);controls.update();renderer.render(scene,camera);
      element.dataset.rendered='true';element.dataset.frames=String(++frames);
      for(const label of element.querySelectorAll<HTMLButtonElement>('[data-anchor]')){
        const id=label.dataset.anchor as ComponentId;point.copy(car.anchors[id]).project(camera);
        label.style.left=`${(point.x*.5+.5)*100}%`;label.style.top=`${(-point.y*.5+.5)*100}%`;
        label.style.visibility=point.z>1||Math.abs(point.x)>.91||Math.abs(point.y)>.86?'hidden':'visible';
      }
    };
    frame=requestAnimationFrame(draw);
    const onLost=(event:Event)=>{event.preventDefault();setError('The 3D context was interrupted. Reload this page to restore the model.');};renderer.domElement.addEventListener('webglcontextlost',onLost);
    return ()=>{cancelAnimationFrame(frame);observer.disconnect();intersection.disconnect();controls.dispose();renderer.domElement.removeEventListener('pointerdown',onDown);renderer.domElement.removeEventListener('pointerup',onUp);renderer.domElement.removeEventListener('webglcontextlost',onLost);car.dispose();grid.geometry.dispose();gridMaterials.forEach(m=>m.dispose());renderer.dispose();renderer.domElement.remove();api.current=null;cameraApi.current=null;};
  },[]);
  return <div className="vehicle-canvas" ref={host} data-concept={props.concept} data-component={props.selected||'none'} data-view={props.view} data-applied={props.applied.join(',')} data-highlighted={props.highlighted.join(',')}>
    {error?<div className="vehicle-fallback" role="alert">{error}</div>:<>
      <div className="vehicle-canvas-tag"><span/>G60 · 5 SERIES<span className="vehicle-canvas-sub">Interactive schematic</span></div>
      {(['screen','vents','seats','drivetrain','brakes'] as ComponentId[]).map(id=><button key={id} data-anchor={id} title={`Select ${COMPONENTS[id]}`} aria-label={`Select ${COMPONENTS[id]} on model`} className={'vehicle-hotspot '+(props.highlighted.includes(id)?'active vehicle-hotspot-pulse':'')} onClick={()=>props.onSelect(id)}><i/>{id==='screen'?'Display':id==='vents'?'Air vents':id==='seats'?'Seats':COMPONENTS[id]}</button>)}
      <div className="vehicle-canvas-help">Drag to rotate · Scroll to zoom · Click a component</div>
    </>}
  </div>;
}
