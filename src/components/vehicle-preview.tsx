'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { Box, RotateCcw, ArrowUpRight, Layers3, Search, ArrowDownUp } from 'lucide-react';
import { api, useApi, cohortQuery, type Cohort, type Ranking, type RequirementView } from '@/lib/api';
import type { components } from '@/lib/api-types';
import { COMPONENTS, PRIORITY_COLORS, componentForRequirement, componentPriorities, approvedConcepts, DESIGN_CONCEPTS, type ComponentId, type Concept, type CameraView } from '@/lib/vehicle-priority';
import { sortRequirements, type RequirementSort } from '@/lib/requirement-ranking';
const VehicleScene=dynamic(()=>import('./vehicle-scene'),{ssr:false,loading:()=> <div className="vehicle-canvas vehicle-loading">Loading interactive G60…</div>});
type Target=components['schemas']['TargetResult'];
type Props={cohort:Cohort;version:number;focused?:RequirementView;onReview?:(id:string)=>void;onConceptChange?:(concept:Concept)=>void;compact?:boolean};

export function VehiclePreview({cohort,version,focused,onReview,onConceptChange,compact=false}:Props) {
  const {data,error}=useApi<Ranking>(cohort.model==='G60'?'/requirements?'+cohortQuery(cohort):null,version);
  const {data:meta}=useApi<{categories:Record<string,string>}>('/meta');
  if(cohort.model!=='G60')return <section className="panel vehicle-unavailable"><Box size={24}/><div><h2>3D preview available for G60</h2><p>Select G60 to explore the model. Other vehicle models have not been added.</p></div></section>;
  if(error)return <div className="notice error" role="alert">Could not load component priorities: {error}</div>;
  if(!data)return <section className="panel vehicle-loading">Loading G60 component priorities…</section>;
  return <VehicleWorkspace key={cohortQuery(cohort)+':'+(focused?.id||'overview')+':'+(focused?.revision||0)} requirements={data.requirements} categories={meta?.categories||{}} cohort={cohort} focused={focused} onReview={onReview} onConceptChange={onConceptChange} compact={compact}/>;
}
function VehicleWorkspace({requirements,categories,cohort,focused,onReview,onConceptChange,compact}:{requirements:RequirementView[];categories:Record<string,string>}&Omit<Props,'version'>) {
  const [query,setQuery]=useState(''),[category,setCategory]=useState(''),[band,setBand]=useState('all'),[status,setStatus]=useState('all');
  const [sort,setSort]=useState<RequirementSort>('priority'),[descending,setDescending]=useState(true),[selectedId,setSelectedId]=useState('');
  const [opacity,setOpacity]=useState(.2),[view,setView]=useState<CameraView>('exterior'),[reset,setReset]=useState(0),[showBaseline,setShowBaseline]=useState(false),[manualConcept,setManualConcept]=useState<Concept|null>(null);
  const cameraIntent=useRef(0);
  const [allowLive,setAllowLive]=useState(true);
  const [mapping,setMapping]=useState<{id:string;target:Target}|null>(null),[mappingBusy,setMappingBusy]=useState(false);
  const rows=useMemo(()=>sortRequirements(requirements.filter(r=>(!category||r.category===category)&&(band==='all'||(band==='critical'?r.critical:r.band===band))&&(status==='all'||r.status===status)&&`${r.feature} ${r.title} ${r.description}`.toLowerCase().includes(query.toLowerCase())),sort,descending),[requirements,category,band,status,query,sort,descending]);
  const selected=focused||rows.find(r=>r.id===selectedId)||rows[0];
  const applied=useMemo(()=>approvedConcepts(requirements),[requirements]);
  const priorities=useMemo(()=>componentPriorities(requirements),[requirements]);
  const localPart=selected?componentForRequirement(selected):null;
  const target=mapping?.id===selected?.id?mapping?.target:null;
  const parts:ComponentId[]=target?target.components:(localPart?[localPart]:[]);
  const component=parts[0]||null;
  const inferred:Concept=target?target.concept||'baseline':localPart==='screen'||localPart==='vents'||localPart==='seats'?localPart:'baseline';
  const concept:Concept=manualConcept??selected?.design_concept??inferred;
  const active=concept!=='baseline'?concept:(!showBaseline?applied.at(-1):null);
  const impact=active?DESIGN_CONCEPTS[active]:null;
  const cohortKey=cohortQuery(cohort);
  useEffect(()=>{
    setManualConcept(null);setShowBaseline(false);setMappingBusy(!!selected);setMapping(null);
    if(!selected)return;
    const part=componentForRequirement(selected);setView(part&&['screen','vents','seats','steering'].includes(part)?'cabin':'exterior');setReset(n=>n+1);
    const intent=++cameraIntent.current;
    const controller=new AbortController();
    api<Target>('/vehicle-target',{requirement_id:selected.id,cohort,allow_live:allowLive},controller.signal).then(value=>{
      if(controller.signal.aborted)return;
      setMapping({id:selected.id,target:value});setMappingBusy(false);
      if(cameraIntent.current===intent)setView(value.components.some(id=>['screen','vents','seats','steering'].includes(id))?'cabin':'exterior');
    }).catch(e=>{if(e.name!=='AbortError'){setMappingBusy(false);setMapping({id:selected.id,target:{components:part?[part]:[],concept:part==='screen'||part==='vents'||part==='seats'?part:null,confidence:part?'medium':'low',reason:'Local feature match.',supporting_quote:selected.feature,method:'local',notice:'Part mapping service unavailable; using local feature matching.'}});}});
    return()=>controller.abort();
  // Selecting another cohort or revision invalidates both the mapping and any in-flight response.
  },[selected?.id,selected?.revision,cohortKey,allowLive]);
  useEffect(()=>onConceptChange?.(concept),[concept,onConceptChange]);
  const selectRequirement=(id:string)=>{setSelectedId(id);setManualConcept(null);setShowBaseline(false);setReset(n=>n+1);};
  const preview=(next:Concept)=>{cameraIntent.current++;setManualConcept(next);setShowBaseline(false);setView('cabin');setReset(n=>n+1);};
  const filterChanged=()=>{setSelectedId('');setManualConcept(null);setShowBaseline(false);};
  const highlights=manualConcept&&manualConcept!=='baseline'?[manualConcept]:parts;
  return <section className={'panel vehicle-panel'+(compact?' vehicle-compact':'')} aria-label="G60 3D component priorities">
    <div className="panel-heading"><div><div className="vehicle-eyebrow"><Box size={13}/> PRIORITY EXPLORER</div><h2>Highest-priority improvements, in view.</h2><p>Select a customer need. The car finds the part and previews the change.</p></div><span className="badge badge-blue">G60 · 3D demo</span></div>
    {applied.length>0&&<div className="vehicle-applied"><strong>{applied.length} accepted design{applied.length>1?'s':''} on this G60</strong><span>{applied.map(id=>DESIGN_CONCEPTS[id].title).join(' · ')} · Saved with PM decisions</span></div>}
    <div className="vehicle-layout"><div className={'vehicle-visual'+(impact&&!showBaseline?' vehicle-impact-active':'')}>
      <div className="vehicle-viewbar" role="group" aria-label="Model camera">{(['exterior','cabin','top','side'] as CameraView[]).map(id=><button key={id} aria-pressed={view===id} onClick={()=>{cameraIntent.current++;setView(id);setReset(n=>n+1);}}>{id==='exterior'?'Whole car':id==='cabin'?'Cabin':id==='top'?'Top':'Side'}</button>)}<button className="vehicle-reset" aria-label="Reset 3D model" onClick={()=>{cameraIntent.current++;setShowBaseline(true);setManualConcept(null);setView('exterior');setOpacity(.2);setReset(n=>n+1);}}><RotateCcw size={13}/>Reset</button></div>
      <div className="vehicle-stage"><VehicleScene applied={showBaseline?[]:applied} priorities={priorities} selected={highlights[0]||null} highlighted={highlights} concept={showBaseline?'baseline':concept} opacity={opacity} view={view} reset={reset} onSelect={id=>{const match=rows.find(r=>componentForRequirement(r)===id);if(match)selectRequirement(match.id);}}/>
      {selected&&<div className="vehicle-focus-caption"><span className={highlights.length?'vehicle-focus-dot':''}/>{highlights.length?`LOCATED · ${highlights.map(id=>COMPONENTS[id]).join(' + ')}`:'NO SUPPORTED PART IDENTIFIED'}</div>}</div>
      {impact&&!showBaseline&&<div className="vehicle-impact" key={active+':'+reset} role="status"><div><span>{applied.includes(active!)?'ACCEPTED DESIGN':'ILLUSTRATIVE CHANGE'}</span><strong>{impact.title}</strong><p>{impact.description}</p></div><div className="vehicle-impact-number">{impact.metric}<small>{impact.detail}</small></div><p className="vehicle-impact-caption">Pulsing red = selected part · Cyan = changed shape · Ghost = original · Demo proportions</p></div>}
      <div className="vehicle-compare vehicle-stage-compare" role="group" aria-label="Concept comparison"><button aria-pressed={showBaseline} onClick={()=>setShowBaseline(true)}>Baseline</button><button aria-pressed={!showBaseline} onClick={()=>setShowBaseline(false)}>After</button><span role="status" data-testid="concept-status">{showBaseline?'Original proportions':concept!=='baseline'?'Concept: '+DESIGN_CONCEPTS[concept].title:applied.length?'Accepted designs applied':'Highlight only · no supported shape change'}</span></div>
      <div className="vehicle-legend" aria-label="Priority legend"><span><i style={{background:PRIORITY_COLORS.High}}/>Critical review / High</span><span><i style={{background:PRIORITY_COLORS.Medium}}/>Medium</span><span><i style={{background:PRIORITY_COLORS.Low}}/>Low</span><span><i style={{background:PRIORITY_COLORS.Unscored}}/>Unscored</span></div>
      <label className="vehicle-opacity"><Layers3 size={14}/>Body opacity<input aria-label="Body opacity" type="range" min="5" max="45" value={Math.round(opacity*100)} onChange={e=>setOpacity(Number(e.target.value)/100)}/><span>{Math.round(opacity*100)}%</span></label>
      {selected&&<div className="vehicle-mapping-note"><strong>{mappingBusy?'Locating the physical part…':target?.method==='ai'?'AI part suggestion':'Local part matching'}</strong><p>{target?.notice||'Matches the wording independently of the ten categories.'} {target?.reason}</p><label className="vehicle-ai-toggle"><input type="checkbox" checked={allowLive} onChange={e=>setAllowLive(e.target.checked)}/>Use AI to identify parts</label><p className="vehicle-ai-disclosure">Sends this requirement and up to 3 supporting comments to the configured OpenAI API.</p>{target?.supporting_quote&&<details><summary>Why this part?</summary><blockquote>{target.supporting_quote}</blockquote></details>}</div>}
    </div><div className="vehicle-inspector">
      {!compact&&<><div className="vehicle-queue-heading"><span>RANKED IMPROVEMENTS</span><strong>{rows.length} customer needs</strong></div>
      <div className="vehicle-queue-filters"><label className="vehicle-search"><Search size={14}/><input aria-label="Search ranked improvements" placeholder="Search customer needs…" value={query} onChange={e=>{setQuery(e.target.value);filterChanged();}}/></label>
      <select aria-label="Improvement category" value={category} onChange={e=>{setCategory(e.target.value);filterChanged();}}><option value="">All 10 categories</option>{Object.entries(categories).map(([id,name])=><option key={id} value={id}>{id} · {name}</option>)}</select>
      <div><select aria-label="Improvement priority" value={band} onChange={e=>{setBand(e.target.value);filterChanged();}}><option value="all">All priorities</option><option value="critical">Critical review</option>{['High','Medium','Low','Unscored'].map(v=><option key={v}>{v}</option>)}</select><select aria-label="Improvement status" value={status} onChange={e=>{setStatus(e.target.value);filterChanged();}}><option value="all">All statuses</option>{['proposed','approved','postponed','rejected'].map(v=><option key={v}>{v}</option>)}</select></div>
      <div><select aria-label="Sort improvements" value={sort} onChange={e=>{setSort(e.target.value as RequirementSort);filterChanged();}}><option value="priority">Priority → impact → demand</option><option value="demand">Demand / potential reach</option><option value="impact">Reviewed impact</option><option value="name">Name A–Z</option></select><button className="vehicle-sort-direction" aria-label="Reverse improvement order" aria-pressed={!descending} onClick={()=>{setDescending(v=>!v);filterChanged();}}><ArrowDownUp size={14}/>{descending?'↓':'↑'}</button></div></div>
      <p className="vehicle-ranking-note">Critical flags first, then reviewed impact and demand. Potential reach is a benefit proxy; actual benefit and ROI are unmeasured.</p>
      <div className="vehicle-ranked-list" role="group" aria-label="Ranked improvements">{rows.map((r,i)=><button key={r.id} className={'vehicle-ranked-row'+(selected?.id===r.id?' selected':'')} aria-label={r.feature} aria-pressed={selected?.id===r.id} onClick={()=>selectRequirement(r.id)}><span className="vehicle-rank">{String(i+1).padStart(2,'0')}</span><span><strong>{r.feature}</strong><small>{r.category} · {categories[r.category]||r.category}</small><span className="vehicle-row-signals"><b className={r.critical?'critical':''}>{r.critical?'Critical review':r.band+' impact'}</b><span>{((r.demand||0)*100).toFixed(1)}% demand</span><span>{r.status}</span></span></span></button>)}{!rows.length&&<p className="vehicle-no-results">No improvements match. Change the filters to see other needs.</p>}</div></>}
      {selected&&<div className="vehicle-selection"><span className="vehicle-selected-category">{selected.category} · {categories[selected.category]||'Customer need'}</span><strong>{selected.title}</strong><p>{selected.numerator} of {selected.denominator} records · {((selected.demand||0)*100).toFixed(1)}% demand</p><p>{component?`Part: ${parts.map(id=>COMPONENTS[id]).join(' + ')}`:'This need has no supported 3D part. It remains in the ranking.'}</p>{onReview&&<button className="text-link" onClick={()=>onReview(selected.id)}>Review &amp; accept this improvement<ArrowUpRight size={13}/></button>}</div>}
      <details className="vehicle-demo-presets"><summary>Explore other demo changes</summary><div className="vehicle-concepts" role="group" aria-label="Design concepts"><button aria-pressed={concept==='screen'} onClick={()=>preview('screen')}><strong>Larger screen</strong><small>Wider display surface</small><span>+80%</span></button><button aria-pressed={concept==='vents'} onClick={()=>preview('vents')}><strong>Larger air vents</strong><small>Increase vent opening height</small><span>3×</span></button><button aria-pressed={concept==='seats'} onClick={()=>preview('seats')}><strong>Adjustable seats</strong><small>Move, raise and recline front seats</small><span>3 axes</span></button></div></details>
    </div></div>
    <div className="vehicle-footnote">C01–C10 categories stay unchanged. Part identification uses requirement wording and evidence. Pulsing red indicates selection, not a new severity score. Accepted designs persist; row selection only previews. <details><summary>About this model &amp; sources</summary><p>Original G60 schematic using <a href="https://www.press.bmwgroup.com/south-africa/article/detail/T0419079EN/the-new-bmw-5-series-sedan?language=en" target="_blank" rel="noreferrer">BMW’s published proportions</a>. Cabin geometry and changes are illustrative; this is not BMW CAD.</p></details></div>
  </section>;
}
