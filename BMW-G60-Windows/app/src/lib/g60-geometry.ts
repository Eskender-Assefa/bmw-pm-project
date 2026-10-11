import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { COMPONENTS, PRIORITY_COLORS, type ComponentId, type Concept, type Priority } from './vehicle-priority';

/** Original, editable schematic. Metres; +X is front, +Y is up. Not a production CAD model. */
export function createG60Geometry() {
  const root = new THREE.Group(); root.name = 'G60 schematic';
  const components = Object.fromEntries(Object.keys(COMPONENTS).map(id => {
    const group = new THREE.Group(); group.name = id; group.userData.component = id; root.add(group); return [id, group];
  })) as Record<ComponentId, THREE.Group>;
  const shellMaterials: THREE.MeshStandardMaterial[] = [];
  const partMaterials = Object.fromEntries(Object.keys(COMPONENTS).map(id => [id,
    new THREE.MeshStandardMaterial({color: '#529ddd', metalness: .2, roughness: .4, transparent: true, opacity: .92}),
  ])) as Record<ComponentId, THREE.MeshStandardMaterial>;
  const metal = new THREE.MeshStandardMaterial({color: '#b2c4d0', metalness: .7, roughness: .35});
  const dark = new THREE.MeshStandardMaterial({color: '#1b2934', roughness: .7});
  const soft = new THREE.MeshStandardMaterial({color: '#273e50', transparent: true, opacity: .38, depthWrite: false});
  function translucent(color: string, opacity: number) {
    const m = new THREE.MeshStandardMaterial({color, metalness: .22, roughness: .3, transparent: true, opacity, depthWrite: false, side: THREE.DoubleSide});
    m.userData.baseOpacity = opacity; shellMaterials.push(m); return m;
  }
  const body = translucent('#b1d9ef', .19), glass = translucent('#57a8d8', .1);
  const trim = translucent('#b2d1e3', .45);
  function mesh(geometry: THREE.BufferGeometry, material: THREE.Material, position: number[], parent: THREE.Object3D = root) {
    const item = new THREE.Mesh(geometry, material); item.position.set(position[0], position[1], position[2]); parent.add(item); return item;
  }
  function box(size: number[], position: number[], material: THREE.Material, parent: THREE.Object3D = root, radius = .025) {
    return mesh(new RoundedBoxGeometry(size[0], size[1], size[2], 2, Math.min(radius, ...size.map(n => n / 3))), material, position, parent);
  }
  function line(points: number[][], color = '#7fa6bc', opacity = .45, parent: THREE.Object3D = root) {
    const item = new THREE.Line(new THREE.BufferGeometry().setFromPoints(points.map(p => new THREE.Vector3(...p))), new THREE.LineBasicMaterial({color, transparent: true, opacity})); parent.add(item); return item;
  }
  function beam(a: number[], b: number[], radius: number, material: THREE.Material, parent: THREE.Object3D = root) {
    const start = new THREE.Vector3(...a), end = new THREE.Vector3(...b), delta = end.clone().sub(start);
    const item = mesh(new THREE.CylinderGeometry(radius, radius, delta.length(), 8), material, start.clone().add(end).multiplyScalar(.5).toArray(), parent);
    item.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0), delta.normalize()); return item;
  }
  function quad(points: number[][], material: THREE.Material) {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(points.flat(),3)); g.setIndex([0,1,2,0,2,3]); g.computeVertexNormals(); mesh(g,material,[0,0,0]);
  }
  // Side silhouette, with actual wheelbase (2.995 m) and four door sedan proportions.
  const side = new THREE.Shape();
  side.moveTo(-2.53,.42); side.lineTo(-2.49,.83); side.lineTo(-1.76,.99);
  side.lineTo(.67,.94); side.lineTo(2.25,.88); side.lineTo(2.53,.65); side.lineTo(2.51,.37);
  side.lineTo(1.875,.37); side.absarc(1.45,.37,.425,0,Math.PI,false);
  side.lineTo(-1.12,.37); side.absarc(-1.545,.37,.425,0,Math.PI,false); side.lineTo(-2.53,.42);
  const shell = new THREE.ExtrudeGeometry(side,{depth:1.86,bevelEnabled:false,curveSegments:16}); shell.translate(0,0,-.93);
  const bodyMesh = mesh(shell,body,[0,0,0]); bodyMesh.name = 'Translucent body';
  root.add(new THREE.LineSegments(new THREE.EdgesGeometry(shell,25),new THREE.LineBasicMaterial({color:'#7ea9c3',transparent:true,opacity:.35})));
  // Windscreen, rear glass, side glazing and slim roof rails reveal the cabin below.
  quad([[.72,.94,-.85],[.72,.94,.85],[.08,1.49,.72],[.08,1.49,-.72]],glass);
  quad([[-1.74,1,-.86],[-1.06,1.48,-.72],[-1.06,1.48,.72],[-1.74,1,.86]],glass);
  for (const s of [-1,1]) {
    quad([[.72,.94,s*.85],[.08,1.49,s*.72],[-1.06,1.48,s*.72],[-1.74,1,s*.86]],glass);
    beam([.72,.94,s*.85],[.08,1.49,s*.72],.025,trim);
    beam([.08,1.49,s*.72],[-1.06,1.48,s*.72],.026,trim);
    beam([-1.06,1.48,s*.72],[-1.74,1,s*.86],.035,trim);
    beam([-.64,.93,s*.9],[-.54,1.49,s*.73],.02,trim);
    line([[.72,.93,s*.935],[-.68,.93,s*.935],[-1.73,.97,s*.935]]);
    line([[-.65,.91,s*.94],[-.73,.43,s*.94]]);
    line([[.65,.9,s*.94],[.43,.44,s*.94]]);
    for(const x of [-.38,-1.28]) box([.15,.024,.015],[x,.88,s*.946],metal);
    box([.21,.09,.14],[.42,1.01,s*1.02],trim);
  }
  box([1.14,.032,1.45],[-.49,1.499,0],body);
  line([[.08,1.515,-.71],[.08,1.515,.71],[-1.06,1.50,.71],[-1.06,1.50,-.71],[.08,1.515,-.71]]);
  box([3.5,.065,1.59],[-.22,.43,0],soft);
  // Front kidney grille, twin DRL accents, long bonnet and slender rear lamps.
  for(const z of [-.23,.23]) {
    const kidney=box([.045,.28,.4],[2.49,.62,z],dark); kidney.rotation.z=-.08;
    for(let i=0;i<5;i++) box([.055,.22,.012],[2.52,.62,z+(i-2)*.07],metal);
  }
  for(const s of [-1,1]) {
    box([.035,.065,.47],[2.45,.79,s*.63],partMaterials.lighting,components.lighting);
    for (const z of [.47,.7]) line([[2.48,.83,s*z],[2.5,.77,s*(z+.025)],[2.47,.74,s*(z+.09)]],'#e8f7ff',1,components.lighting);
    box([.04,.044,.57],[-2.5,.81,s*.57],new THREE.MeshStandardMaterial({color:'#c7475a',emissive:'#91172b',emissiveIntensity:.4}));
    line([[2.24,.905,s*.47],[1.65,.93,s*.39],[.71,.96,s*.45]],'#85abc3',.65);
    line([[-2.48,.83,s*.8],[-1.77,1,s*.75]],'#85abc3',.6);
  }
  // Four wheels. Brake discs remain visible outside the body shell.
  for(const x of [1.45,-1.545]) for(const s of [-1,1]) {
    const tire=mesh(new THREE.CylinderGeometry(.35,.35,.22,32),dark,[x,.35,s*.88]); tire.rotation.x=Math.PI/2;
    const rim=mesh(new THREE.CylinderGeometry(.254,.254,.023,24),metal,[x,.35,s*1.002]);rim.rotation.x=Math.PI/2;
    const disc=mesh(new THREE.TorusGeometry(.205,.019,8,32),partMaterials.brakes,[x,.35,s*1.018],components.brakes);
    for(let i=0;i<5;i++) {const a=i*Math.PI*2/5;beam([x,.35,s*1.021],[x+Math.cos(a)*.24,.35+Math.sin(a)*.24,s*1.021],.017,dark);}
    box([.08,.17,.044],[x+.17,.36,s*1.026],partMaterials.brakes,components.brakes);
    disc.name='Brake disc';
  }
  // Interior groups are independent so concept changes deform only the target part.
  box([.36,.16,1.63],[.62,.89,0],soft);
  const display = new THREE.Group(); display.position.set(.405,1.10,-.17); components.screen.add(display);
  box([.038,.26,.89],[0,0,0],partMaterials.screen,display);
  box([.012,.212,.82],[-.027,0,0],new THREE.MeshStandardMaterial({color:'#0c2437',emissive:'#2478af',emissiveIntensity:.6}),display);
  // Screen graphics read from the rear of the cabin.
  for(let i=0;i<4;i++) box([.015,.014,.13],[-.036,.06-i*.037,.18],new THREE.MeshBasicMaterial({color:'#8bdeff'}),display,.005);
  const gauge=mesh(new THREE.TorusGeometry(.063,.005,6,28),new THREE.MeshBasicMaterial({color:'#7de7ff'}),[-.038,0,-.23],display);gauge.rotation.y=Math.PI/2;
  const vents = new THREE.Group(); vents.position.set(.44,.9,0); components.vents.add(vents);
  for (const z of [-.65,-.2,.2,.65]) {
    box([.07,.085,.2],[0,0,z],partMaterials.vents,vents,.016);
    for(let i=0;i<3;i++) box([.006,.006,.17],[-.038,(i-1)*.019,z],dark,vents,.001);
  }
  const frontSeats: THREE.Group[] = [], backrests: THREE.Group[] = [];
  for(const z of [-.44,.44]) {
    const seat=new THREE.Group();seat.position.set(-.2,.57,z);components.seats.add(seat);frontSeats.push(seat);
    box([.53,.13,.49],[0,0,0],partMaterials.seats,seat,.06);
    const back = new THREE.Group(); back.position.set(-.23,.06,0); seat.add(back); backrests.push(back);
    const pad=box([.13,.51,.46],[-.045,.26,0],partMaterials.seats,back,.06);pad.rotation.z=.13;
    box([.13,.15,.27],[-.085,.6,0],partMaterials.seats,back,.04);
    for(const side of [-1,1]) box([.42,.14,.055],[0,.05,side*.215],partMaterials.seats,seat);
    beam([-.17,-.12,-.16],[.22,-.12,-.16],.014,metal,seat);beam([-.17,-.12,.16],[.22,-.12,.16],.014,metal,seat);
  }
  box([.48,.13,1.36],[-1.14,.62,0],partMaterials.seats,components.seats,.07);
  const rear=box([.12,.44,1.33],[-1.39,.87,0],partMaterials.seats,components.seats,.06);rear.rotation.z=.18;
  for(const z of [-.48,0,.48])box([.12,.13,.25],[-1.45,1.16,z],partMaterials.seats,components.seats);
  box([.84,.13,.19],[-.22,.63,0],soft);
  const steering=mesh(new THREE.TorusGeometry(.17,.021,10,32),partMaterials.steering,[.21,1.04,.44],components.steering);steering.rotation.y=Math.PI/2;steering.rotation.z=-.15;
  box([.07,.1,.12],[.21,1.04,.44],partMaterials.steering,components.steering);
  box([.75,.34,.9],[1.48,.61,0],partMaterials.drivetrain,components.drivetrain,.07);
  for(let i=0;i<5;i++)box([.04,.035,.71],[1.25+i*.12,.80,0],metal,components.drivetrain);
  box([2.05,.12,1.31],[-.18,.28,0],partMaterials.battery,components.battery,.04);
  for(let i=0;i<7;i++)line([[-1.1+i*.29,.345,-.62],[-1.1+i*.29,.345,.62]],'#b7dbf2',.5,components.battery);
  box([.61,.25,1.30],[-2.07,.65,0],partMaterials.storage,components.storage);
  for(const x of [-2.51,2.52])box([.05,.08,.26],[x,.47,0],partMaterials.assistance,components.assistance);

  const anchors: Record<ComponentId, THREE.Vector3> = {
    screen:new THREE.Vector3(.4,1.3,-.18),vents:new THREE.Vector3(.45,.96,.65),seats:new THREE.Vector3(-.45,1.28,.47),
    drivetrain:new THREE.Vector3(1.48,.91,0),brakes:new THREE.Vector3(1.45,.38,1.05),battery:new THREE.Vector3(-.2,.3,-.74),
    steering:new THREE.Vector3(.21,1.06,.44),lighting:new THREE.Vector3(2.47,.82,.65),assistance:new THREE.Vector3(2.53,.47,0),storage:new THREE.Vector3(-2.04,.95,0),
  };
  const baselineGhosts = new THREE.Group();root.add(baselineGhosts);
  const outlines = {} as Record<'screen'|'vents'|'seats',THREE.BoxHelper>;
  const ghosts = {} as Record<'screen'|'vents'|'seats',THREE.Group>;
  root.updateMatrixWorld(true);
  for(const id of ['screen','vents','seats'] as const) {
    const ghost=components[id].clone(true);
    ghost.traverse(obj=>{if(obj instanceof THREE.Mesh)obj.material=new THREE.MeshBasicMaterial({color:'#b4e9ff',wireframe:true,transparent:true,opacity:.12,depthWrite:false});});
    ghost.visible=false;baselineGhosts.add(ghost);ghosts[id]=ghost;
    const outline=new THREE.BoxHelper(components[id],'#00e5ff');
    const m=outline.material as THREE.LineBasicMaterial;m.transparent=true;m.opacity=.85;m.depthTest=false;
    outline.renderOrder=10;outline.visible=false;root.add(outline);outlines[id]=outline;
  }
  const progress={screen:0,vents:0,seats:0};
  let targets = new Set<Concept>(), elapsed=0;
  let highlighted:ComponentId[]=[];let motionReduced=false;
  const baseColors={} as Record<ComponentId,THREE.Color>;
  return {root, components, anchors,
    setFocus(ids:ComponentId[],reduced=false){highlighted=ids;motionReduced=reduced;},
    setConcept(value: Concept, applied: Concept[] = []) {targets=new Set([...applied,...(value==='baseline'?[]:[value])]);},
    update(delta: number) {
      elapsed+=delta;
      for(const id of ['screen','vents','seats'] as const)progress[id]=THREE.MathUtils.damp(progress[id],targets.has(id)?1:0,3.8,delta);
      const screenScale=progress.screen,ventScale=progress.vents,seatShift=progress.seats;
      display.scale.set(1,1+screenScale*.65,1+screenScale*.8);
      display.position.y=1.1+screenScale*.13;
      vents.scale.set(1,1+ventScale*2,1+ventScale*.18);
      frontSeats.forEach((seat,i)=>{seat.position.x=-.2+seatShift*.38;seat.position.y=.57+seatShift*.20;backrests[i].rotation.z=seatShift*.5;});
      for(const id of Object.keys(COMPONENTS) as ComponentId[]){
        const material=partMaterials[id];
        if(highlighted.includes(id)){material.color.set('#ff202d');material.emissive.set('#ff1020');material.emissiveIntensity=motionReduced?.5:.25+(Math.sin(elapsed*Math.PI*1.6)+1)*.55;material.opacity=1;}
        else if(baseColors[id]){material.color.copy(baseColors[id]);material.emissive.copy(material.color);material.emissiveIntensity=.07;}
      }
      root.updateMatrixWorld(true);
      for(const id of ['screen','vents','seats'] as const){
        ghosts[id].visible=progress[id]>.01;outlines[id].visible=progress[id]>.01;
        outlines[id].update();
        (outlines[id].material as THREE.LineBasicMaterial).opacity=.65+Math.sin(elapsed*3)*.2;
      }
      anchors.screen.set(.4,1.3+screenScale*.3,-.18);
      anchors.vents.set(.45,.96+ventScale*.12,.65);
      anchors.seats.set(-.45+seatShift*.38,1.28+seatShift*.20,.47);
    },
    setStyle(priorities: Record<ComponentId,Priority>, selected: ComponentId|null, opacity: number) {
      for(const id of Object.keys(COMPONENTS) as ComponentId[]) {
        const material=partMaterials[id];material.color.set(PRIORITY_COLORS[priorities[id]]);baseColors[id]=material.color.clone();
        material.emissive.copy(material.color);material.emissiveIntensity=id===selected ? .35 : .07;
        material.opacity=selected && id!==selected ? .55 : .96;
      }
      for(const material of shellMaterials)material.opacity=material.userData.baseOpacity*(opacity/.2);
    },
    dispose() {
      const geometries=new Set<THREE.BufferGeometry>(),materials=new Set<THREE.Material>();
      root.traverse(obj=>{if(obj instanceof THREE.Mesh||obj instanceof THREE.Line){geometries.add(obj.geometry);for(const m of Array.isArray(obj.material)?obj.material:[obj.material])materials.add(m);}});
      geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());
    },
  };
}
