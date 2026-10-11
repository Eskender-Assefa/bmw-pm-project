'use client';
import { useState } from 'react';
import { CircleHelp, ExternalLink, Globe, Radar, Target, ThumbsDown } from 'lucide-react';
import { useApi, cohortQuery, number, type Cohort } from '@/lib/api';
import { Badge, Empty, ErrorBox, Loading } from './cockpit';

type Horizon='now'|'next'|'later';
type Signal='praised'|'criticised'|'mixed'|'silent'|'not_linked';
interface TrendSource {title:string;publisher:string;url:string;published:string|null;}
interface Trend {id:string;title:string;summary:string;categories:string[];horizon:Horizon;markets:string[];powertrains:string[];features:string[];sources:TrendSource[];customer:{signal:Signal;likes:number;complaints:number;features:string[]};stance:string;relevant_to_cohort:boolean;}
interface TrendData {denominator:number;provenance:{version:string;review_status:string;collected_at:string;notice:string};summary:{total:number;relevant:number;by_horizon:Record<Horizon,number>;by_signal:Partial<Record<Signal,number>>};trends:Trend[];trends_version:string;}

const HORIZONS:{id:Horizon;label:string;note:string}[]=[{id:'now',label:'Now',note:'In market today'},{id:'next',label:'Next',note:'Expected within about three years'},{id:'later',label:'Later',note:'Beyond three years'}];
const MARKETS=['US','Europe','China','Global'];
const SIGNALS:Record<Signal,{label:string;tone:string}>={praised:{label:'Customers praise this',tone:'green'},criticised:{label:'Customers criticise this',tone:'red'},mixed:{label:'No reliable difference',tone:'amber'},silent:{label:'Not mentioned by this cohort',tone:'neutral'},not_linked:{label:'No matching feedback feature',tone:'neutral'}};

export function TrendsView({cohort,version,categories}:{cohort:Cohort;version:number;categories:Record<string,string>}){
 const [category,setCategory]=useState(''),[market,setMarket]=useState(''),[relevantOnly,setRelevantOnly]=useState(false);
 const {data,error,loading}=useApi<TrendData>(`/trends?${cohortQuery(cohort)}${category?'&category='+category:''}${market?'&market='+market:''}`,version);
 if(error)return <ErrorBox message={error}/>;if(!data)return <Loading/>;
 const shown=data.trends.filter(trend=>!relevantOnly||trend.relevant_to_cohort);
 return <div className={loading?'view-content refreshing':'view-content'}>
  <div className="notice knowledge"><div className="notice-icon"><CircleHelp size={20}/></div><div><h3>Public reporting, not yet reviewed</h3><p>{data.provenance.notice}</p></div><Badge tone="amber">Collected {data.provenance.collected_at}</Badge></div>
  <div className="metric-grid"><Stat label="Trends in view" value={String(data.summary.total)} icon={Radar} note={`${data.summary.by_horizon.now} now · ${data.summary.by_horizon.next} next · ${data.summary.by_horizon.later} later`}/><Stat label="Relevant to this cohort" value={String(data.summary.relevant)} icon={Target} note="Market and powertrain both match"/><Stat label="Where customers criticise" value={String(data.summary.by_signal.criticised||0)} icon={ThumbsDown} note="Complaints reliably exceed praise"/><Stat label="Records in cohort" value={number(data.denominator)} icon={Globe} note="Basis of every customer signal"/></div>
  <section className="panel"><div className="list-toolbar"><select aria-label="Product category" value={category} onChange={e=>setCategory(e.target.value)}><option value="">All categories</option>{Object.entries(categories).map(([id,name])=><option key={id} value={id}>{id} · {name}</option>)}</select><select aria-label="Target market" value={market} onChange={e=>setMarket(e.target.value)}><option value="">All markets</option>{MARKETS.map(name=><option key={name}>{name}</option>)}</select><label className="trend-toggle"><input type="checkbox" checked={relevantOnly} onChange={e=>setRelevantOnly(e.target.checked)}/>Only trends relevant to this cohort</label><span className="result-count">{shown.length} trends</span></div>
   {shown.length?<div className="trend-board">{HORIZONS.map(horizon=>{const items=shown.filter(trend=>trend.horizon===horizon.id);return <section key={horizon.id} className="trend-column" aria-label={`${horizon.label}: ${items.length} trends`}><header><h2>{horizon.label}<span>{items.length}</span></h2><p>{horizon.note}</p></header>{items.length?items.map(trend=><TrendCard key={trend.id} trend={trend} denominator={data.denominator}/>):<p className="trend-none">No trends in this horizon for the current filters.</p>}</section>;})}</div>:<Empty title="No trends in this view" description="Change the filters or the evidence cohort."/>}
   <div className="panel-footnote"><CircleHelp size={13}/> The suggested stance is a fixed rule on horizon and customer signal, not a decision. Register {data.provenance.version} · {data.trends_version}</div></section>
 </div>;
}

function Stat({label,value,icon:Icon,note}:{label:string;value:string;icon:typeof Radar;note:string}){return <section className="metric"><div className="metric-label">{label}<Icon size={19}/></div><strong className="metric-value">{value}</strong><p>{note}</p></section>;}

function TrendCard({trend,denominator}:{trend:Trend;denominator:number}){
 const signal=SIGNALS[trend.customer.signal],linked=trend.customer.signal!=='not_linked';
 return <article className={trend.relevant_to_cohort?'trend-card':'trend-card outside'}>
  <div className="trend-tags">{trend.categories.map(code=><Badge key={code}>{code}</Badge>)}{trend.markets.map(name=><Badge key={name} tone="blue">{name}</Badge>)}<Badge>{trend.powertrains.join(' · ')}</Badge></div>
  <h3>{trend.title}</h3><p>{trend.summary}</p>
  <div className="trend-signal"><Badge tone={signal.tone}>{signal.label}</Badge>{linked&&<span>{number(trend.customer.likes)} praise · {number(trend.customer.complaints)} complaints of {number(denominator)} records</span>}</div>
  <div className="trend-stance"><span>Suggested stance</span><strong>{trend.stance}</strong>{!trend.relevant_to_cohort&&<small>Outside this cohort's market or powertrain</small>}</div>
  <ul className="trend-sources">{trend.sources.map(source=><li key={source.url}><a href={source.url} target="_blank" rel="noopener noreferrer">{source.publisher}: {source.title}<ExternalLink size={11}/></a>{source.published&&<small>{source.published}</small>}</li>)}</ul>
 </article>;
}
