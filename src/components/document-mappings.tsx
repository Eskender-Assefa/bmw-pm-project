'use client';
import { useEffect, useState } from 'react';
import { ArrowUpRight, ChevronLeft, ChevronRight, ClipboardCheck, X } from 'lucide-react';
import { api } from '@/lib/api';
import { Button } from './ui/button';
import { Badge, Empty, ErrorBox, Loading } from './cockpit';
import { passageLocation, type Assignment, type Passage } from './document-rag-types';

interface CategorySummary {id:string;name:string;mappings:number;passages:number;pending:number;reviewed:number;rejected:number;}
interface Overview {categories:CategorySummary[];items:{passage:Passage;assignment_index:number;assignment:Assignment}[];total:number;total_passages:number;total_mappings:number;}
interface Props {
 filterKey:string;query:string;version:number;category:string;documentName:string;
 selected:string[];onSelection:(ids:string[])=>void;onCategory:(category:string)=>void;
 onReview:(passage:Passage)=>void;onEvidence:(id:string)=>void;
}

export function DocumentMappings({filterKey,query,version,category,documentName,selected,onSelection,onCategory,onReview,onEvidence}:Props){
 const [data,setData]=useState<Overview|null>(null),[error,setError]=useState(''),[offset,setOffset]=useState(0);
 useEffect(()=>setOffset(0),[filterKey,query,version]);
 useEffect(()=>{
  const controller=new AbortController();setData(null);setError('');
  api<Overview>('/rag/mappings',{...JSON.parse(filterKey),query,offset,limit:20},controller.signal)
   .then(setData).catch(e=>{if(e.name!=='AbortError')setError(e.message);});
  return()=>controller.abort();
 },[filterKey,query,offset,version]);
 if(error)return <ErrorBox message={error}/>;
 if(!data)return <Loading/>;
 const eligible=[...new Set(data.items.filter(r=>r.passage.review_status==='pending').map(r=>r.passage.id))].slice(0,12);
 function toggle(id:string,checked:boolean){onSelection(checked?[...new Set([...selected,id])].slice(0,12):selected.filter(i=>i!==id));}
 return <section className="rag-overview" aria-label="Document category mappings">
  <div className="rag-overview-heading"><div><h2>Category coverage</h2><p>{documentName}</p></div><span>{data.total_passages.toLocaleString()} passages / {data.total_mappings.toLocaleString()} mapping rows</span></div>
  <div className="rag-table-scroll" role="region" aria-label="All ten category counts" tabIndex={0}>
   <table className="rag-coverage-table"><caption>All 10 categories. Counts reflect the document filters, across every results page.</caption><thead><tr><th scope="col">Category</th><th scope="col">Passages</th><th scope="col">Pending</th><th scope="col">Reviewed</th><th scope="col">Rejected</th><th scope="col"><span className="sr-only">View mappings</span></th></tr></thead><tbody>
    {data.categories.map(c=><tr key={c.id} className={category===c.id?'is-selected':''}><th scope="row"><strong>{c.id}</strong> {c.name}{c.mappings===0&&<small>No mapped evidence</small>}</th><td>{c.passages}</td><td>{c.pending}</td><td>{c.reviewed}</td><td>{c.rejected}</td><td><Button size="icon" variant="ghost" aria-label={'View mappings for '+c.id+' '+c.name} title={'View '+c.name} onClick={()=>onCategory(c.id)}><ChevronRight size={16}/></Button></td></tr>)}
   </tbody></table>
  </div>
  <div className="rag-overview-heading"><h2>{category?`${category} mappings`:'All category mappings'}</h2>{category&&<Button variant="outline" size="sm" onClick={()=>onCategory('')}><X size={14}/>Clear category</Button>}</div>
  <p className="rag-data-note">Feature values and variants are proposals. Not extracted means unknown; an empty category does not establish absence. Review status applies to the whole passage.</p>
  {data.items.length?<>
   <label className="rag-bulk-select"><input type="checkbox" aria-label="Select visible pending passages" disabled={!eligible.length} checked={!!eligible.length&&eligible.every(id=>selected.includes(id))} onChange={e=>onSelection(e.target.checked?eligible:selected.filter(id=>!eligible.includes(id)))}/>Select visible pending passages (up to 12)</label>
   <div className="rag-table-scroll" role="region" aria-label="Extracted feature mappings" tabIndex={0}>
    <table className="rag-feature-table"><caption>{data.total.toLocaleString()} mapping rows matching the selected category</caption><thead><tr><th scope="col">Category / scope</th><th scope="col">Feature / value</th><th scope="col">Car variant</th><th scope="col">Source</th><th scope="col">Passage review</th></tr></thead><tbody>
     {data.items.map(({passage:p,assignment:a,assignment_index:i})=><tr key={p.id+':'+i}>
      <td data-label="Category / scope"><label className="rag-row-select"><input type="checkbox" aria-label={'Select mapping '+p.id+' aspect '+(i+1)} checked={selected.includes(p.id)} disabled={p.review_status!=='pending'||(!selected.includes(p.id)&&selected.length>=12)} onChange={e=>toggle(p.id,e.target.checked)}/><strong>{a.category}</strong></label><Badge>{a.scope_layer}</Badge></td>
      <td data-label="Feature / value"><strong>{a.feature||'Feature not extracted'}</strong><div className={!a.value?'rag-unknown':''}>{a.value?`${a.value}${a.unit?' '+a.unit:''}`:'Value not extracted'}</div><details className="rag-row-quote"><summary>Supporting quote</summary><blockquote>{a.quote}</blockquote><p>{a.rationale}</p></details></td>
      <td data-label="Car variant"><strong>{a.variant||'Not extracted'}</strong><small>Model: {p.model||'Unknown'}</small></td>
      <td data-label="Source"><span>{p.filename}</span><button className="text-link" onClick={()=>onEvidence(p.evidence_id)}>{passageLocation(p)}<ArrowUpRight size={13}/></button><small>{p.origin} / Source market: {p.market||'Unknown'}</small></td>
      <td data-label="Passage review"><Badge tone={p.review_status==='reviewed'?'green':p.review_status==='rejected'?'red':'amber'}>{p.review_status}</Badge><small>{p.method}</small><Button size="sm" variant="outline" onClick={()=>onReview(p)}><ClipboardCheck size={14}/>Review</Button></td>
     </tr>)}
    </tbody></table>
   </div>
   <div className="rag-pagination"><span>{offset+1}-{Math.min(offset+20,data.total)} of {data.total.toLocaleString()} mapping rows</span><Button size="icon" variant="outline" title="Previous mappings" aria-label="Previous mapping page" disabled={!offset} onClick={()=>setOffset(Math.max(0,offset-20))}><ChevronLeft size={16}/></Button><Button size="icon" variant="outline" title="Next mappings" aria-label="Next mapping page" disabled={offset+20>=data.total} onClick={()=>setOffset(offset+20)}><ChevronRight size={16}/></Button></div>
  </>:<Empty title="No mapped evidence under these filters" description="No claim about the vehicle's available features can be made from this empty result."/>}
 </section>;
}
