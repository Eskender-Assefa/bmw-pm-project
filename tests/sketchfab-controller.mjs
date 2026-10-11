import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import ts from 'typescript';
await fs.mkdir('.local/viewer-tests',{recursive:true});
const source=await fs.readFile('src/lib/sketchfab-controller.ts','utf8');
await fs.writeFile('.local/viewer-tests/controller.mjs',ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText);
const {G60Controller,surfaceCorners,DEMO_REGIONS}=await import('../.local/viewer-tests/controller.mjs');
const distance=(a,b)=>Math.hypot(...a.map((v,i)=>v-b[i]));
for(const [part,width,height] of [['screen',1.8,1.65],['vents',1.18,3]]){
 const before=surfaceCorners(part,false),after=surfaceCorners(part,true);
 assert.ok(Math.abs(distance(after[0],after[1])/distance(before[0],before[1])-width)<1e-10);
 assert.ok(Math.abs(distance(after[1],after[2])/distance(before[1],before[2])-height)<1e-10);
}
const identity=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
const originals=['Car_Body','Glass','Seats','Interior','Door_Panel','SteeringWheel','Lights'].map((name,i)=>({id:name,name,stateSetID:i,channels:{Opacity:{enable:false,factor:1},AlbedoPBR:{texture:{uid:'original-'+name}},EmitColor:{enable:false,color:[0,0,0]}}}));
const changes=new Map();let matrix,camera={position:[0,1,1],target:[0,0,1]},fail=false;
const api={getNodeMap(cb){cb(null,{999:{instanceID:999,name:'Seats_42',type:'MatrixTransform',localMatrix:identity}});},getMaterialList(cb){cb(null,originals);},setMatrix(id,value,cb){assert.equal(id,999,'Discovers node by name, not a fixed ID');matrix=value;cb(null);},setMaterial(value,cb){changes.set(value.name,value);cb?.(fail?'material rejected':null);},getCameraLookAt(cb){cb(null,camera);},getWorldToScreenCoordinates(pos,cb){cb({canvasCoord:pos,glCoord:pos});},setFov(){},setCameraLookAt(position,target){camera={position,target};}};
const controller=new G60Controller(api);
try{
 await controller.initialize();
 await controller.apply({highlighted:['seats'],concepts:['seats'],opacity:.2});
 assert.deepEqual(matrix,identity,'After preserves seat placement and proportions');
 assert.deepEqual(changes.get('Seats').channels.AlbedoPBR.color,[.015,.48,.62],'After shows new upholstery instead of red selection paint');
 await new Promise(resolve=>setTimeout(resolve,750));
 assert.deepEqual(changes.get('Seats').channels.AlbedoPBR.color,[.015,.48,.62],'Selection pulse does not overwrite the new design');
 await controller.apply({highlighted:[],concepts:[],opacity:1});
 assert.deepEqual(matrix,identity);
 assert.deepEqual(changes.get('Seats'),originals.find(m=>m.name==='Seats'),'Restores original textures after a highlight');
 const note=await controller.apply({highlighted:['battery'],concepts:[],opacity:.2});
 assert.match(note,/Approximate demo region/);
 const regions=await controller.projectSurfaces({highlighted:Object.keys(DEMO_REGIONS),concepts:[],opacity:.2});
 assert.equal(regions.length,Object.keys(DEMO_REGIONS).length,'Every approximate region renders a highlight');
 const overlays=await controller.projectSurfaces({highlighted:['screen','vents'],concepts:['screen'],opacity:.2});
 assert.equal(overlays.length,2);assert.equal(overlays[0].changed,true);
 camera.position=[0,-3,1];assert.deepEqual(await controller.projectSurfaces({highlighted:['screen'],concepts:[],opacity:.2}),[],'Hide the reverse face of dashboard overlays');
 fail=true;await assert.rejects(controller.apply({highlighted:[],concepts:[],opacity:.2}),/material rejected/);
 fail=false;await controller.apply({highlighted:[],concepts:[],opacity:.2});
 const a=controller.apply({highlighted:['seats'],concepts:['seats'],opacity:.2});
 const b=controller.apply({highlighted:[],concepts:[],opacity:.2});await Promise.all([a,b]);assert.deepEqual(matrix,identity,'Latest selection wins');
 console.log('Passed mesh discovery, original-material restoration, seat reset, projection scale/facing, demo regions, new seat appearance, error recovery and rapid selection updates.');
}finally{controller.dispose();}
