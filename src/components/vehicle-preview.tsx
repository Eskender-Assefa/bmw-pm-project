'use client';

import { useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { Box, RotateCcw, ArrowUpRight, Layers3 } from 'lucide-react';
import { useApi, cohortQuery, type Cohort, type Ranking, type RequirementView } from '@/lib/api';
import { COMPONENTS, PRIORITY_COLORS, componentForRequirement, componentPriorities, conceptForRequirement, type ComponentId, type Concept, type CameraView } from '@/lib/vehicle-priority';
const VehicleScene=dynamic(()=>import('./vehicle-scene'),{ssr:false,loading:()=> <div className="vehicle-canvas vehicle-loading">Loading interactive G60…</div>});

export function VehiclePreview({cohort,version,focused,onReview,compact=false}:{cohort:Cohort;version:number;focused?:RequirementView;onReview?:(id:string)=>void;compact?:boolean}) {
  const {data,error}=useApi<Ranking>(cohort.model==='G60'?'/requirements?'+cohortQuery(cohort):null,version);
  if(cohort.model!=='G60')return <section className="panel vehicle-unavailable"><Box size={24}/><div><h2>3D preview available for G60</h2><p>Select G60 to explore the model. Other vehicle models have not been added.</p></div></section>;
  if(error)return <div className="notice error" role="alert">Could not load component priorities: {error}</div>;
  if(!data)return <section className="panel vehicle-loading">Loading G60 component priorities…</section>;
  // Remount the controls for a newly selected requirement or cohort; never carry a concept into another scope.
  return <VehicleWorkspace key={cohortQuery(cohort)+':'+(focused?.id||'overview')+':'+(focused?.revision||0)} requirements={data.requirements} focused={focused} onReview={onReview} compact={compact}/>;
}
function VehicleWorkspace({requirements,focused,onReview,compact}:{requirements:RequirementView[];focused?:RequirementView;onReview?:(id:string)=>void;compact:boolean}) {
  const initial=focused?componentForRequirement(focused):null;
  const [component,setComponent]=useState<ComponentId|null>(initial),[concept,setConcept]=useState<Concept>(focused?conceptForRequirement(focused):'baseline'),[opacity,setOpacity]=useState(.2),[view,setView]=useState<CameraView>(initial&&['screen','vents','seats'].includes(initial)?'cabin':'exterior'),[reset,setReset]=useState(0),[requirementId,setRequirementId]=useState(focused?.id||'');
  const priorities=useMemo(()=>componentPriorities(requirements),[requirements]);
  const related=requirements.filter(r=>componentForRequirement(r)===component);
  const selected=requirements.find(r=>r.id===requirementId);
  const available=requirements.filter(r=>componentForRequirement(r));
  const unmapped=requirements.length-available.length;
  const choose=(id:ComponentId)=>{setComponent(id);setConcept('baseline');setRequirementId('');if(['screen','vents','seats','steering'].includes(id))setView('cabin');else setView('exterior');};
  const preview=(next:Concept)=>{setConcept(next);if(next!=='baseline'){setComponent(next);if(selected&&componentForRequirement(selected)!==next)setRequirementId('');setView('cabin');}setReset(n=>n+1);};
  const selectRequirement=(id:string)=>{
    setRequirementId(id);const r=requirements.find(r=>r.id===id);
    const part=r?componentForRequirement(r):null;setComponent(part);setConcept(r?conceptForRequirement(r):'baseline');
    setView(part&&['screen','vents','seats','steering'].includes(part)?'cabin':'exterior');setReset(n=>n+1);
  };
  return <section className={'panel vehicle-panel'+(compact?' vehicle-compact':'')} aria-label="G60 3D component priorities">
    <div className="panel-heading"><div><div className="vehicle-eyebrow"><Box size={13}/> COMPONENT INTELLIGENCE</div><h2>See where the next improvement belongs.</h2><p>G60 · Translucent model · Priorities from the selected evidence cohort</p></div><span className="badge badge-blue">3D demo</span></div>
    <div className="vehicle-layout"><div className="vehicle-visual">
      <div className="vehicle-viewbar" role="group" aria-label="Model camera">{(['exterior','cabin','top','side'] as CameraView[]).map(id=><button key={id} aria-pressed={view===id} onClick={()=>{setView(id);setReset(n=>n+1);}}>{id==='exterior'?'Whole car':id==='cabin'?'Cabin':id==='top'?'Top':'Side'}</button>)}<button className="vehicle-reset" aria-label="Reset 3D model" onClick={()=>{setConcept('baseline');setComponent(initial);setRequirementId(focused?.id||'');setView('exterior');setOpacity(.2);setReset(n=>n+1);}}><RotateCcw size={13}/>Reset</button></div>
      <VehicleScene priorities={priorities} selected={component} concept={concept} opacity={opacity} view={view} reset={reset} onSelect={choose}/>
      <div className="vehicle-legend" aria-label="Priority legend"><span><i style={{background:PRIORITY_COLORS.High}}/>Critical review / High</span><span><i style={{background:PRIORITY_COLORS.Medium}}/>Medium</span><span><i style={{background:PRIORITY_COLORS.Low}}/>Low</span><span><i style={{background:PRIORITY_COLORS.Unscored}}/>Unscored</span><span><i style={{background:PRIORITY_COLORS.none}}/>No mapped need</span></div>
      <label className="vehicle-opacity"><Layers3 size={14}/>Body opacity<input aria-label="Body opacity" type="range" min="5" max="45" value={Math.round(opacity*100)} onChange={e=>setOpacity(Number(e.target.value)/100)}/><span>{Math.round(opacity*100)}%</span></label>
    </div><div className="vehicle-inspector">
      <div className="vehicle-inspector-heading"><span>DESIGN EXPLORER</span><h3>{component?COMPONENTS[component]:'Choose a component'}</h3><p>{component?`${related.length} candidate requirements · ${priorities[component]==='critical'?'Critical review':priorities[component]==='none'?'No mapped need':priorities[component]}`:'Click the car or choose a component to inspect its needs.'}</p></div>
      <label className="vehicle-select-label">Component<select aria-label="Car component" value={component||''} onChange={e=>e.target.value?choose(e.target.value as ComponentId):selectRequirement('')}><option value="">All components</option>{Object.entries(COMPONENTS).map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label>
      <label className="vehicle-select-label">Improvement requirement<select aria-label="3D improvement requirement" value={requirementId} onChange={e=>selectRequirement(e.target.value)}><option value="">Choose a mapped requirement</option>{available.map(r=><option key={r.id} value={r.id}>{r.feature} · {r.band}</option>)}</select></label>
      {selected&&<div className="vehicle-selection"><strong>{selected.title}</strong><p>{selected.numerator} of {selected.denominator} records · {((selected.demand||0)*100).toFixed(1)}% demand</p>{onReview&&<button className="text-link" onClick={()=>onReview(selected.id)}>Review this requirement<ArrowUpRight size={13}/></button>}</div>}
      {focused&&!initial&&<p className="vehicle-concept-note">This requirement has no specific 3D component mapping yet.</p>}
      <div className="vehicle-concept-heading">TRY AN IMPROVEMENT</div>
      <div className="vehicle-concepts" role="group" aria-label="Design concepts">
        <button aria-pressed={concept==='screen'} onClick={()=>preview('screen')}><strong>Larger screen</strong><small>Wider display surface</small><span>+42%</span></button>
        <button aria-pressed={concept==='vents'} onClick={()=>preview('vents')}><strong>Larger air vents</strong><small>Increase vent opening height</small><span>+65%</span></button>
        <button aria-pressed={concept==='seats'} onClick={()=>preview('seats')}><strong>Adjustable seats</strong><small>Move, raise and recline front seats</small><span>3 axes</span></button>
      </div>
      <div className="vehicle-compare" role="group" aria-label="Concept comparison"><button aria-pressed={concept==='baseline'} onClick={()=>setConcept('baseline')}>Baseline</button><span role="status" data-testid="concept-status">{concept==='baseline'?'Original proportions':concept==='screen'?'Concept: enlarged screen':concept==='vents'?'Concept: enlarged air vents':'Concept: adjusted seats'}</span></div>
      <p className="vehicle-concept-note">Concept previews are illustrative and do not edit requirements or save PM decisions. Sizes and movement are demo assumptions.</p>
    </div></div>
    <div className="vehicle-footnote">Red marks critical-review flags or High PM impact. Blue needs are still Unscored; demand is not a severity rating. Component locations are illustrative.{unmapped>0&&` ${unmapped} requirements have no 3D mapping.`}<details><summary>About this model &amp; sources</summary><p>Original low-detail G60 schematic using published 5 Series proportions: 5.060 m length, 1.900 m width, 2.995 m wheelbase. Cabin geometry is approximate; this is not BMW CAD. <a href="https://www.press.bmwgroup.com/south-africa/article/detail/T0419079EN/the-new-bmw-5-series-sedan?language=en" target="_blank" rel="noreferrer">BMW dimensions</a>. <a href="https://sketchfab.com/3d-models/2023-bmw-i5-m60-207fd872d28b4cafa7fefe061ae98e26" target="_blank" rel="noreferrer">Higher-detail model candidate</a> (not bundled).</p></details></div>
  </section>;
}
