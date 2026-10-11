import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';
import * as THREE from 'three';
import { chromium } from '@playwright/test';

const root=process.cwd(),output=path.join(root,'.local/vehicle-check');await fs.mkdir(output,{recursive:true});
for(const name of ['vehicle-priority','g60-geometry']) {
  const source=await fs.readFile(path.join(root,`src/lib/${name}.ts`),'utf8');
  const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText.replace("'./vehicle-priority'","'./vehicle-priority.mjs'");
  await fs.writeFile(path.join(output,name+'.mjs'),code);
}
const priority=await import(pathToFileURL(path.join(output,'vehicle-priority.mjs')));
const {createG60Geometry}=await import(pathToFileURL(path.join(output,'g60-geometry.mjs')));
const req=(feature,band='Unscored',critical=false)=>({feature,band,critical,title:`Improve ${feature}`,description:'Review this customer need'});
assert.equal(priority.componentForRequirement(req('Seat belts')),null);
assert.equal(priority.componentForRequirement(req('Touch screen, operation')),'screen');
assert.equal(priority.componentForRequirement(req('Air conditioning control panel')),'vents');
assert.equal(priority.componentForRequirement(req('Seats')),'seats');
const priorities=priority.componentPriorities([req('Braking','Low',true),req('Seats','High'),req('Touch screen, operation')]);
assert.equal(priorities.brakes,'critical');assert.equal(priorities.seats,'High');assert.equal(priorities.screen,'Unscored');assert.equal(priorities.vents,'none');
assert.equal(priority.conceptForRequirement(req('Seats')),'baseline');
assert.equal(priority.conceptForRequirement({...req('Touch screen, operation'),title:'Make the screen larger'}),'screen');
const geometry=createG60Geometry();
const size=id=>{geometry.root.updateMatrixWorld(true);return new THREE.Box3().setFromObject(geometry.components[id]).getSize(new THREE.Vector3());};
const baselineScreen=size('screen'),baselineVents=size('vents');
geometry.setConcept('screen');for(let i=0;i<100;i++)geometry.update(.05);
assert.ok(size('screen').z>baselineScreen.z*1.3,'Screen geometry actually becomes wider');
geometry.setConcept('vents');for(let i=0;i<100;i++)geometry.update(.05);
assert.ok(size('vents').y>baselineVents.y*1.5,'Vent openings actually become taller');
const seat=geometry.components.seats.children.find(child=>child instanceof THREE.Group);
const baseSeat=seat.position.clone();geometry.setConcept('seats');for(let i=0;i<100;i++)geometry.update(.05);
assert.ok(seat.position.x>baseSeat.x+.15&&seat.position.y>baseSeat.y+.05,'Seats move and rise');
geometry.setConcept('baseline');for(let i=0;i<100;i++)geometry.update(.05);
assert.ok(Math.abs(size('screen').z-baselineScreen.z)<.001);assert.ok(seat.position.distanceTo(baseSeat)<.001);
geometry.setStyle(priorities,null,.2);
assert.equal(geometry.components.brakes.children[0].material.color.getHexString(),'ef4444');
geometry.dispose();
console.log('Passed component mapping, truthful priority colours, actual mesh transformations and reset.');

const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_EXECUTABLE_PATH||path.join(root,'.local/browser-cache/chromium-1248/chrome-linux64/chrome'),headless:true,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try {
  const page=await browser.newPage({viewport:{width:1500,height:1100}});page.setDefaultTimeout(30000);
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const writes=[];page.on('request',r=>{if(r.method()==='POST')writes.push(r.url());});
  await page.goto('http://127.0.0.1:3001/',{waitUntil:'domcontentloaded'});
  const tabs=page.locator('.sidebar nav .nav-item');
  assert.deepEqual(await tabs.allTextContents(),['Overview','Requirements','Evidence library','Comparisons','Decisions & audit']);
  const panel=page.getByRole('region',{name:'G60 3D component priorities'});
  await panel.locator('[data-rendered=true]').waitFor();
  await panel.screenshot({path:path.join(output,'baseline.png')});
  for(const [name,concept] of [['Larger screen','screen'],['Larger air vents','vents'],['Adjustable seats','seats']]) {
    await panel.getByRole('button',{name:new RegExp(name)}).click();
    await panel.locator(`[data-concept=${concept}][data-view=cabin]`).waitFor();
    await page.waitForTimeout(500); // Allow the short mesh transition to settle before visual comparison.
    assert.ok((await panel.getByTestId('concept-status').textContent()).startsWith('Concept:'));
    await panel.screenshot({path:path.join(output,concept+'.png')});
  }
  await panel.getByRole('button',{name:'Baseline',exact:true}).click();
  await panel.locator('[data-concept=baseline]').waitFor();
  await panel.getByLabel('Body opacity').fill('35');
  await panel.getByRole('button',{name:'Reset 3D model'}).click();
  assert.equal(await panel.getByLabel('Body opacity').inputValue(),'20');
  await page.getByRole('button',{name:'Requirements',exact:true}).click();
  await page.getByLabel('Search requirements').fill('Touch screen');
  await page.getByRole('button',{name:'Touch screen, operation',exact:true}).click();
  const drawer=page.getByRole('dialog',{name:'Requirement review'});
  await drawer.locator('[data-component=screen][data-rendered=true]').waitFor();
  await drawer.getByRole('button',{name:/Larger screen/}).click();
  await drawer.locator('[data-concept=screen]').waitFor();
  await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Overview',exact:true}).click();
  await page.getByLabel('Model',{exact:true}).selectOption('F70');
  await page.getByText('3D preview available for G60').waitFor();
  assert.equal(await page.locator('.vehicle-canvas canvas').count(),0);
  await page.getByLabel('Model',{exact:true}).selectOption('G60');
  await page.locator('[data-rendered=true]').waitFor();
  await page.setViewportSize({width:390,height:844});
  await page.getByRole('region',{name:'G60 3D component priorities'}).screenshot({path:path.join(output,'mobile.png')});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),'No page overflow on mobile');
  assert.deepEqual(writes,[],'Concepts must not save decisions or call AI');
  assert.deepEqual(errors,[],'No browser JavaScript errors');
  console.log('Passed unchanged dashboard tabs, WebGL rendering, all concepts, baseline reset, requirement focus, G60-only support, mobile layout and no backend writes.');
} finally {await browser.close();}
