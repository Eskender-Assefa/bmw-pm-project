'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { api, useApi, cohortQuery, type Cohort, type Ranking, type RequirementView } from '@/lib/api';
import type { components } from '@/lib/api-types';
import { COMPONENTS, componentForRequirement, approvedConcepts, DESIGN_CONCEPTS, type ComponentId, type Concept, type CameraView } from '@/lib/vehicle-priority';
import { SketchfabG60 } from './sketchfab-g60';
import { sortRequirements } from '@/lib/requirement-ranking';
type Target=components['schemas']['TargetResult'];
type Props={cohort:Cohort;version:number;focused?:RequirementView;onReview?:(id:string)=>void;onConceptChange?:(concept:Concept)=>void;compact?:boolean};

export function VehiclePreview(props:Props) {
  const {data,error}=useApi<Ranking>(props.cohort.model==='G60'?'/requirements?'+cohortQuery(props.cohort):null,props.version);
  if(props.cohort.model!=='G60')return <section className="panel vehicle-unavailable">The 3D model is available for G60 only.</section>;
  if(error)return <p role="alert">Could not load G60 priorities: {error}</p>;
  if(!data)return <p className="loading">Loading G60 priorities…</p>;
  return <VehicleWorkspace {...props} requirements={data.requirements}/>;
}
function VehicleWorkspace({requirements,cohort,focused,onConceptChange,compact}:Props&{requirements:RequirementView[]}) {
  const selected=focused||sortRequirements(requirements,'priority')[0];
  const [opacity,setOpacity]=useState(.12),[view,setView]=useState<CameraView>('exterior'),[reset,setReset]=useState(0),[baseline,setBaseline]=useState(false),[manual,setManual]=useState<Concept|null>(null);
  const [allowLive,setAllowLive]=useState(true),[mapping,setMapping]=useState<{id:string;target:Target}|null>(null),[busy,setBusy]=useState(false);
  const cameraIntent=useRef(0);
  const applied=useMemo(()=>approvedConcepts(requirements),[requirements]);
  const local=selected?componentForRequirement(selected):null;
  const target=mapping?.id===selected?.id?mapping.target:null;
  const parts:ComponentId[]=target?target.components:local?[local]:[];
  const concept:Concept=manual??selected?.design_concept??target?.concept??'baseline';
  const highlighted:ComponentId[]=manual&&manual!=='baseline'?[manual]:parts;
  const concepts=baseline?[]:[...new Set([...applied,...(concept==='baseline'?[]:[concept])])];
  const key=cohortQuery(cohort);
  useEffect(()=>{
    setManual(null);setBaseline(false);setMapping(null);setBusy(!!selected);
    if(!selected)return;
    const part=componentForRequirement(selected),intent=++cameraIntent.current;
    setView(part&&['screen','vents','seats','steering'].includes(part)?'cabin':'exterior');setReset(n=>n+1);
    const controller=new AbortController();
    api<Target>('/vehicle-target',{requirement_id:selected.id,cohort,allow_live:allowLive},controller.signal).then(value=>{
      if(controller.signal.aborted)return;
      setMapping({id:selected.id,target:value});setBusy(false);
      if(cameraIntent.current===intent)setView(value.components.some(id=>['screen','vents','seats','steering'].includes(id))?'cabin':'exterior');
    }).catch(e=>{if(e.name!=='AbortError'){setBusy(false);setMapping({id:selected.id,target:{components:part?[part]:[],concept:null,confidence:part?'medium':'low',reason:'Local feature match.',supporting_quote:selected.feature,method:'local',notice:'Part service unavailable; using local matching.'}});}});
    return()=>controller.abort();
  },[selected?.id,selected?.revision,key,allowLive]);
  useEffect(()=>onConceptChange?.(concept),[concept,onConceptChange]);
  return <section className={'panel hosted-vehicle'+(compact?' vehicle-compact':'')} aria-label="G60 3D component priorities">
    <div className="vehicle-viewbar" role="group" aria-label="Model camera">{(['exterior','cabin','top','side'] as CameraView[]).map(id=><button key={id} aria-pressed={view===id} onClick={()=>{cameraIntent.current++;setView(id);setReset(n=>n+1);}}>{id==='exterior'?'Whole car':id==='cabin'?'Cabin':id==='top'?'Top':'Side'}</button>)}</div>
    <SketchfabG60 highlighted={highlighted} concepts={concepts} opacity={opacity} view={view} reset={reset}/>
    <div className="hosted-controls"><div className="vehicle-compare" role="group" aria-label="Concept comparison"><button aria-pressed={baseline} onClick={()=>setBaseline(true)}>Baseline</button><button aria-pressed={!baseline} onClick={()=>setBaseline(false)}>After</button><span data-testid="concept-status">{baseline?'Original proportions':concepts.length?concepts.map(c=>DESIGN_CONCEPTS[c].title).join(' + '):'Highlight only'}</span></div>
    <label className="vehicle-opacity">Body opacity<input aria-label="Body opacity" type="range" min="3" max="100" value={Math.round(opacity*100)} onChange={e=>setOpacity(Number(e.target.value)/100)}/><span>{Math.round(opacity*100)}%</span></label>
    {applied.length>0&&<p className="hosted-accepted">Saved designs: {applied.map(c=>DESIGN_CONCEPTS[c].title).join(' · ')}</p>}
    <details className="vehicle-demo-presets"><summary>Preview a design change</summary><div className="vehicle-concepts" role="group" aria-label="Design concepts">{(['screen','vents','seats'] as const).map(id=><button key={id} aria-pressed={concept===id} onClick={()=>{cameraIntent.current++;setManual(id);setBaseline(false);setView('cabin');setReset(n=>n+1);}}><strong>{id==='screen'?'Larger screen':id==='vents'?'Larger air vents':'Adjustable seats'}</strong><small>{id==='seats'?'Move the seat assembly':'Enlarge the surface concept'}</small></button>)}</div></details>
    {manual&&<p className="hosted-accepted">Manual demo preview: {manual==='baseline'?'baseline':DESIGN_CONCEPTS[manual].title}</p>}
    <div className="vehicle-mapping-note"><strong>{busy?'Identifying the physical part…':target?.method==='ai'?'AI part identification':'Local part matching'}</strong><p>{parts.length?'Suggested part: '+parts.map(id=>COMPONENTS[id]).join(' + '):'No supported part identified for this problem.'}</p><p>{target?.notice} {target?.reason}</p><label className="vehicle-ai-toggle"><input type="checkbox" checked={allowLive} onChange={e=>setAllowLive(e.target.checked)}/>Use AI to identify parts</label><p>Sends the problem wording and up to three supporting comments to the configured OpenAI API.</p>{target?.supporting_quote&&<details><summary>Supporting wording</summary><blockquote>{target.supporting_quote}</blockquote></details>}</div>
    <p className="hosted-disclaimer">Red pulses mark the selected part, not a new severity score. Previewing does not approve a change. Screen and vent previews are anchored concept overlays; the seats move as one assembly. Demo proportions, not engineering geometry.</p>
    </div>
  </section>;
}
