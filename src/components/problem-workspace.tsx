'use client';

import { useMemo, useState } from 'react';
import { ArrowDownUp, Columns3, Box, ListChecks, Search } from 'lucide-react';
import { useApi, cohortQuery, type Cohort, type Ranking } from '@/lib/api';
import { sortRequirements, type RequirementSort } from '@/lib/requirement-ranking';
import { VehiclePreview } from './vehicle-preview';

export type ProblemMode = 'requirements' | 'model' | 'split';
type Sample = {id:string;quote:string;external_id?:string;type?:string;locator:Record<string,unknown>;source?:{filename:string;kind:string}};
export function ProblemWorkspace({mode,onMode,cohort,version,category,setCategory,categories,onReview,onEvidence,onDocuments}:{mode:ProblemMode;onMode:(mode:ProblemMode)=>void;cohort:Cohort;version:number;category:string;setCategory:(id:string)=>void;categories:Record<string,string>;onReview:(id:string)=>void;onEvidence:(id:string)=>void;onDocuments:(query:string)=>void}) {
  const {data,error}=useApi<Ranking>('/requirements?'+cohortQuery(cohort),version);
  const [query,setQuery]=useState(''),[status,setStatus]=useState('all'),[priority,setPriority]=useState('all');
  const [sort,setSort]=useState<RequirementSort>('priority'),[descending,setDescending]=useState(true),[selectedId,setSelectedId]=useState('');
  const rows=useMemo(()=>sortRequirements((data?.requirements||[]).filter(r=>(!category||r.category===category)&&(status==='all'||r.status===status)&&(priority==='all'||(priority==='critical'?r.critical:r.band===priority))&&`${r.feature} ${r.title} ${r.description}`.toLowerCase().includes(query.toLowerCase())),sort,descending),[data,category,status,priority,query,sort,descending]);
  const selected=rows.find(r=>r.id===selectedId)||rows[0];
  return <div className="problem-workspace">
    <div className="workspace-layout-bar"><div><strong>Problems ↔ G60 model</strong><span>One selection, connected views</span></div><div role="group" aria-label="Workspace layout"><button aria-pressed={mode==='requirements'} onClick={()=>onMode('requirements')}><ListChecks size={15}/>Problems only</button><button aria-pressed={mode==='model'} onClick={()=>onMode('model')}><Box size={15}/>Model only</button><button aria-pressed={mode==='split'} onClick={()=>onMode('split')}><Columns3 size={15}/>{mode==='split'?'Merged side by side':'Merge tabs'}</button></div></div>
    {error&&<p role="alert" className="notice error">{error}</p>}
    {!data&&!error&&<p className="loading">Loading customer problems…</p>}
    {data&&<div className={'problem-model-layout mode-'+mode}>
      <section className="panel problem-list-panel" hidden={mode==='model'} aria-label="Customer problems">
        <div className="panel-heading"><div><h2>Problems to solve</h2><p>Category, customer detail, sources and scores in one list.</p></div><span className="badge">{rows.length} problem{rows.length===1?'':'s'}</span></div>
        <div className="problem-filters">
          <label className="search-input"><Search size={16}/><input aria-label="Search problems" placeholder="Search problems…" value={query} onChange={e=>setQuery(e.target.value)}/></label>
          <select aria-label="Problem category" value={category} onChange={e=>setCategory(e.target.value)}><option value="">All 10 categories</option>{Object.entries(categories).map(([id,name])=><option key={id} value={id}>{id} · {name}</option>)}</select>
          <select aria-label="Problem status" value={status} onChange={e=>setStatus(e.target.value)}><option value="all">All statuses</option>{['proposed','approved','postponed','rejected'].map(s=><option key={s}>{s}</option>)}</select>
          <select aria-label="Problem priority" value={priority} onChange={e=>setPriority(e.target.value)}><option value="all">All priorities</option><option value="critical">Critical review</option>{['High','Medium','Low','Unscored'].map(s=><option key={s}>{s}</option>)}</select>
          <select aria-label="Sort problems" value={sort} onChange={e=>setSort(e.target.value as RequirementSort)}><option value="priority">Priority → impact → demand</option><option value="impact">Reviewed impact</option><option value="demand">Demand / potential reach</option><option value="name">Name A–Z</option></select>
          <button aria-label="Reverse problem order" aria-pressed={!descending} onClick={()=>setDescending(v=>!v)}><ArrowDownUp size={15}/>{descending?'Descending':'Ascending'}</button>
        </div>
        <p className="problem-ranking-note">Critical flags first, then reviewed impact and demand. Demand indicates potential reach; benefit and ROI have not been measured.</p>
        <div className="problem-list">{rows.map((r,i)=>{const samples=r.evidence_samples as unknown as Sample[];return <article key={r.id} className={'problem-card'+(selected?.id===r.id?' selected':'')} data-problem-id={r.id}>
          <button className="problem-select" aria-pressed={selected?.id===r.id} onClick={()=>setSelectedId(r.id)} aria-label={'Select problem: '+r.feature}><span className="problem-rank">{String(i+1).padStart(2,'0')}</span><span><small>{r.category} · {categories[r.category]||r.category}</small><strong>{r.feature}</strong><span>{r.title}</span></span><Box size={18}/></button>
          <div className="problem-detail"><p>{r.description}</p><small className="problem-provenance">{r.generated_by} · Part identification reads this detail and up to three supporting excerpts.</small></div>
          <div className="problem-scores"><span><small>Review priority</small><b className={r.critical?'critical':''}>{r.critical?'Critical review':r.band}</b></span><span><small>Demand</small><b>{((r.demand||0)*100).toFixed(1)}%</b><em>{r.numerator} / {r.denominator} records</em></span><span><small>Reviewed impact</small><b>{r.band}</b></span><span><small>Positive mentions</small><b>{r.likes}</b></span><span><small>Decision</small><b className={'status status-'+r.status}>{r.status}</b></span></div>
          <div className="problem-evidence"><div className="problem-evidence-heading"><strong>Evidence &amp; source citations</strong><span>Imported customer evidence</span></div>{samples.length?<><ProblemCitation sample={samples[0]} onEvidence={onEvidence}/>{samples.length>1&&<details className="more-citations"><summary>{samples.length-1} more supporting excerpts</summary>{samples.slice(1).map((s,index)=><ProblemCitation key={s.id+':'+index} sample={s} onEvidence={onEvidence}/>)}</details>}</>:<p>No supporting excerpts available.</p>}<small>Search related documents for additional passages and cited answers in Document intelligence.</small></div>
          <div className="problem-actions"><button onClick={()=>onDocuments(r.feature)}>Search documents</button><button onClick={()=>{setSelectedId(r.id);onMode('split');}}>Show on G60</button><button onClick={()=>onReview(r.id)}>Review &amp; approve</button></div>
        </article>;})}{!rows.length&&<p className="empty">No problems match these filters.</p>}</div>
      </section>
      <div className="problem-model-panel" hidden={mode==='requirements'}>{cohort.model!=='G60'?<p className="notice">The 3D model is available for G60 only.</p>:selected?<><div className="model-selection-summary"><small>SELECTED PROBLEM · {selected.category}</small><strong>{selected.feature}</strong><p>{selected.title}</p><button onClick={()=>onReview(selected.id)}>Review &amp; approve</button></div><VehiclePreview cohort={cohort} version={version} focused={selected} onReview={onReview}/></>:<p className="notice">No selected problem. Change the filters in Problems.</p>}</div>
    </div>}
  </div>;
}

function ProblemCitation({sample:s,onEvidence}:{sample:Sample;onEvidence:(id:string)=>void}){return <div className="problem-citation"><details><summary><blockquote>“{s.quote}”</blockquote><span className="quote-expand">Expand / collapse feedback</span></summary></details><button onClick={()=>onEvidence(s.id)}>{s.source?.filename||'Open original source'} · {Object.entries(s.locator||{}).filter(([key])=>key!=='external_id').map(([key,value])=>`${key}: ${String(value)}`).join(' · ')}{s.external_id?' · Feedback '+s.external_id:''}</button></div>;}
