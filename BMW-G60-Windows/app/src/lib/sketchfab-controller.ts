import type { CameraView, ComponentId, Concept, DemoPart } from './vehicle-priority';

export type Channel = {enable?:boolean;factor?:number;color?:number[];type?:string;texture?:unknown;[key:string]:unknown};
export type Material = {id:string;name:string;stateSetID:number;channels:Record<string,Channel>;[key:string]:unknown};
export type SceneNode = {instanceID:number;name:string;type:string;localMatrix?:Record<string,number>};
type Callback<T=void> = (error:unknown,value:T)=>void;
export interface ViewerAPI {
  start():void;
  addEventListener(name:string,callback:()=>void):void;
  getNodeMap(callback:Callback<Record<string,SceneNode>>):void;
  getMaterialList(callback:Callback<Material[]>):void;
  setMaterial(material:Material,callback?:Callback):void;
  setMatrix(id:number,matrix:number[],callback?:Callback):void;
  setFov(angle:number,callback?:Callback<number>):void;
  setCameraLookAt(position:number[],target:number[],duration:number,callback?:Callback):void;
  getCameraLookAt(callback:Callback<{position:number[];target:number[]}>):void;
  getWorldToScreenCoordinates(position:number[],callback:(coordinates:{canvasCoord:number[];glCoord:number[]})=>void):void;
}
export type DesignConcept=Exclude<Concept,'baseline'>;
export type SceneSettings={highlighted:DemoPart[];concepts:DesignConcept[];opacity:number};
export const MATERIAL_PARTS:Partial<Record<ComponentId,string>>={seats:'Seats',steering:'SteeringWheel',lighting:'Lights'};
// Coordinates calibrated on the public Viewer API, in its Z-up world space.
// These are surface projections because the author merged the display and dashboard into larger assemblies.
export const SURFACES={
  screen:{position:[.1,-.46,1],normal:[.15,.96,.22],baseline:[.78,.19,.055],after:[1.404,.3135,.055]},
  vents:{position:[-.1,-.47,.88],normal:[0,1,0],baseline:[.8,.045,.13],after:[.944,.135,.20]},
};
// Approximate x-ray markers: these stand in for parts absent from the hosted mesh.
export const DEMO_REGIONS:Partial<Record<DemoPart,{label:string;position:number[];size:number[]}>>={
  drivetrain:{label:'ENGINE / POWER',position:[0,-1.4,.9],size:[1.25,1.3]},
  brakes:{label:'BRAKES / WHEEL',position:[.83,-1.42,.5],size:[.65,.75]},
  battery:{label:'ENERGY / BATTERY',position:[0,.15,.3],size:[1.25,2]},
  assistance:{label:'DRIVER ASSISTANCE',position:[0,-2.15,.65],size:[1.2,.55]},
  storage:{label:'LUGGAGE AREA',position:[0,1.75,.95],size:[1.3,1]},
  body:{label:'VEHICLE / BODY',position:[0,0,1],size:[1.65,4.2]},
};
export const CAMERAS:Record<CameraView,{position:number[];target:number[]}>= {
  exterior:{position:[5,-7,3.4],target:[0,0,.65]},
  cabin:{position:[0,.65,1.2],target:[0,-.45,.93]},
  top:{position:[.01,0,8],target:[0,0,.4]},
  side:{position:[7,0,2.5],target:[0,0,.7]},
};
function call<T>(invoke:(callback:Callback<T>)=>void):Promise<T>{
  return new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('Sketchfab did not acknowledge the change.')),12000);invoke((error,value)=>{clearTimeout(timer);error?reject(new Error(String(error))):resolve(value);});});
}
export class G60Controller {
  private materials:Material[]=[];
  private seats:SceneNode|undefined;
  private seatOriginal:number[]=[];
  private pulseMaterials:Material[]=[];
  private timer:ReturnType<typeof setInterval>|undefined;
  private queue=Promise.resolve();
  private disposed=false;
  private revision=0;
  constructor(private api:ViewerAPI){}
  async initialize(){
    const [nodes,materials]=await Promise.all([call<Record<string,SceneNode>>(cb=>this.api.getNodeMap(cb)),call<Material[]>(cb=>this.api.getMaterialList(cb))]);
    this.materials=structuredClone(materials);
    this.seats=Object.values(nodes).find(n=>n.type==='MatrixTransform'&&/^Seats_\d+$/.test(n.name));
    if(this.seats?.localMatrix)this.seatOriginal=Array.from({length:16},(_,i)=>this.seats!.localMatrix![String(i)]);
  }
  async projectSurfaces(settings:SceneSettings):Promise<SurfaceProjection[]>{
    if(this.disposed)return [];
    if(!settings.highlighted.length&&!settings.concepts.length)return [];
    const camera=await call<{position:number[];target:number[]}>(cb=>this.api.getCameraLookAt(cb));
    const surfaces:SurfaceProjection[]=[];
    for(const part of ['screen','vents'] as const){
      if(!settings.highlighted.includes(part)&&!settings.concepts.includes(part))continue;
      const surface=SURFACES[part],changed=settings.concepts.includes(part);
      // Hide a cabin surface when looking at its reverse side. No occlusion claim is made:
      // the overlay is an x-ray design marker, while exposed mesh parts are edited in the viewer.
      const facing=surface.normal.reduce((sum,n,i)=>sum+n*(camera.position[i]-surface.position[i]),0);
      if(facing<=0)continue;
      const corners=surfaceCorners(part,changed);
      const points=await Promise.all(corners.map(point=>new Promise<number[]>((resolve,reject)=>{
        const timer=setTimeout(()=>reject(new Error('Surface projection unavailable.')),3000);
        this.api.getWorldToScreenCoordinates(point,coordinates=>{clearTimeout(timer);resolve(coordinates.canvasCoord);});
      })));
      if(points.every(p=>p?.length>=2&&p.every(Number.isFinite)))surfaces.push({part,points,changed,selected:settings.highlighted.includes(part)});
    }
    for(const part of settings.highlighted){
      const region=DEMO_REGIONS[part];if(!region)continue;
      const corners=[[-1,-1],[1,-1],[1,1],[-1,1]].map(([x,y])=>[region.position[0]+x*region.size[0]/2,region.position[1]+y*region.size[1]/2,region.position[2]]);
      const points=await Promise.all(corners.map(point=>new Promise<number[]>((resolve,reject)=>{
        const timer=setTimeout(()=>reject(new Error('Region projection unavailable.')),3000);
        this.api.getWorldToScreenCoordinates(point,c=>{clearTimeout(timer);resolve(c.canvasCoord);});
      })));
      if(points.every(p=>p?.length>=2&&p.every(Number.isFinite)))surfaces.push({part,points,changed:false,selected:true});
    }
    return surfaces;
  }
  camera(view:CameraView,highlighted:DemoPart[]=[]){const seats=view==='cabin'&&highlighted.includes('seats');const camera=seats?{position:[3,2.8,2.5],target:[0,.4,.8]}:CAMERAS[view];this.api.setFov(view==='cabin'&&!seats?60:35);this.api.setCameraLookAt(camera.position,camera.target,0);}
  apply(settings:SceneSettings):Promise<string>{
    let message='';const revision=++this.revision;
    const operation=this.queue.then(async()=>{if(this.disposed||revision!==this.revision)return;message=await this.update(settings);});
    this.queue=operation.catch(()=>{});
    return operation.then(()=>message);
  }
  private async update({highlighted,concepts,opacity}:SceneSettings){
    this.stopPulse();
    const pulseNames=highlighted.flatMap(id=>MATERIAL_PARTS[id as ComponentId]?[MATERIAL_PARTS[id as ComponentId]!]:[]);
    for(const original of this.materials){
      if(this.disposed)return '';
      const material=structuredClone(original);
      if((['Car_Body','Glass'].includes(material.name)||((highlighted.includes('seats')||concepts.includes('seats'))&&['Interior','Door_Panel'].includes(material.name))))material.channels.Opacity={...material.channels.Opacity,enable:true,type:'alphaBlend',factor:material.name==='Glass'?Math.min(opacity,.08):opacity};
      if(material.name==='Seats'&&concepts.includes('seats')){
        material.channels.AlbedoPBR={enable:true,factor:1,color:[.015,.48,.62]};
        material.channels.EmitColor={enable:true,factor:.22,color:[0,.55,.7],type:'additive'};
        material.channels.RoughnessPBR={enable:true,factor:.3};
        material.channels.MetalnessPBR={enable:true,factor:.08};
      }
      await call(cb=>this.api.setMaterial(material,cb));
      if(pulseNames.includes(material.name)&&!(material.name==='Seats'&&concepts.includes('seats')))this.pulseMaterials.push(material);
    }
    if(this.seats&&this.seatOriginal.length===16)await call(cb=>this.api.setMatrix(this.seats!.instanceID,[...this.seatOriginal],cb));
    if(this.disposed)return '';
    const pulse=(bright:boolean)=>{for(const original of this.pulseMaterials){const m=structuredClone(original);m.channels.AlbedoPBR={enable:true,factor:1,color:bright?[1,.015,.025]:[.2,.01,.015]};m.channels.EmitColor={enable:true,color:bright?[1,.015,.025]:[.3,.005,.01],factor:bright?.9:.25,type:'additive'};this.api.setMaterial(m);}};
    pulse(true);
    if(this.pulseMaterials.length&&!globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches){let bright=true;this.timer=setInterval(()=>{bright=!bright;pulse(bright);},700);}
    const regions=highlighted.filter(id=>DEMO_REGIONS[id]);
    const missing=highlighted.filter(id=>MATERIAL_PARTS[id as ComponentId]&&!this.materials.some(m=>m.name===MATERIAL_PARTS[id as ComponentId]));
    return [...(regions.length?['Approximate demo region highlighted.']:[]),...(missing.length?[`Model parts unavailable: ${missing.join(', ')}.`]:[]),...(concepts.includes('seats')&&!this.seats?['Seat transform unavailable.']:[])].join(' ');
  }
  private stopPulse(){clearInterval(this.timer);this.pulseMaterials=[];}
  dispose(){this.disposed=true;this.stopPulse();}
}

export type SurfaceProjection={part:DemoPart;points:number[][];changed:boolean;selected:boolean};
export function surfaceCorners(part:'screen'|'vents',changed:boolean){
  const surface=SURFACES[part],size=changed?surface.after:surface.baseline;
  const normal=surface.normal,length=Math.hypot(normal[0],normal[1]);
  const right=[normal[1]/length,-normal[0]/length,0];
  // Orthogonal in-plane axes, normalized to keep the stated demo proportions exact.
  const vertical=[-normal[2]*right[1],normal[2]*right[0],normal[0]*right[1]-normal[1]*right[0]];
  const upLength=Math.hypot(...vertical);const axis=vertical.map(v=>-v/upLength);
  return [[-1,1],[1,1],[1,-1],[-1,-1]].map(([x,y])=>surface.position.map((v,i)=>v+right[i]*x*size[0]/2+axis[i]*y*size[1]/2));
}
