'use client';
import { useState } from 'react';
import { ArrowUpRight, CircleHelp, Coins, Star, ThumbsUp, TrendingUp } from 'lucide-react';
import { useApi, cohortQuery, number, type Cohort } from '@/lib/api';
import { Badge, Empty, ErrorBox, Loading } from './cockpit';

interface UspOption {option_code:string;label:string;price_eur_including_vat:number;net_price_eur:number;evidence_id:string;}
interface UspCost {options:UspOption[];net_price_min:number;net_price_median:number;net_price_max:number;low:number;mid:number;high:number;}
interface UspItem {feature_id:string;feature:string;category:string;likes:number;complaints:number;praise_share:number;praise_lower:number;complaint_share:number;complaint_upper:number;score:number;is_usp:boolean;cost:UspCost|null;efficiency:number|null;on_frontier:boolean;}
type CostedItem=UspItem&{cost:UspCost};
interface UspData {denominator:number;assumptions:{vat_rate:number;cost_ratio_low:number;cost_ratio_high:number;confidence_level:number;notice:string};summary:{usps:number;costed_features:number;costed_usps:number;priced_options:number};items:UspItem[];usp_version:string;}
type Scope='usps'|'costed'|'all';

const CHART={width:760,height:340,left:58,right:22,top:20,bottom:46};
const DEFAULT_RATIOS={low:40,high:70};
const COST_TICKS=5,COST_STEP=100;
const euro=(value:number)=>'€'+number(Math.round(value));
const points=(value:number)=>(value*100).toFixed(2)+' pp';
const ticks=(min:number,max:number,count:number)=>Array.from({length:count+1},(_,i)=>min+(max-min)*i/count);

export function UspView({cohort,version,onEvidence}:{cohort:Cohort;version:number;onEvidence:(id:string)=>void}){
 const [ratios,setRatios]=useState(DEFAULT_RATIOS),[scope,setScope]=useState<Scope>('usps'),[selected,setSelected]=useState<string|null>(null);
 const valid=ratios.low>0&&ratios.high<=100&&ratios.low<=ratios.high;
 const {data,error,loading}=useApi<UspData>(valid?`/usp?${cohortQuery(cohort)}&cost_ratio_low=${ratios.low/100}&cost_ratio_high=${ratios.high/100}`:null,version);
 const setRatio=(key:'low'|'high',value:string)=>setRatios({...ratios,[key]:Number(value)});
 const costed=(data?.items.filter(item=>item.cost)||[]) as CostedItem[];
 const rows=data?.items.filter(item=>scope==='all'||(scope==='usps'?item.is_usp:item.cost!==null))||[];
 const detail=costed.find(item=>item.feature_id===selected)||null;
 return <div className={loading?'view-content refreshing':'view-content'}>
  <div className="notice knowledge"><div className="notice-icon"><CircleHelp size={20}/></div><div><h3>Cost is an estimate, not BMW data</h3><p>{data?.assumptions.notice||'Cost is derived from printed German option prices under the cost-ratio assumption below.'}</p></div><Badge tone="amber">Assumption</Badge></div>
  <section className="panel"><div className="usp-controls"><div><h2>Cost-ratio assumption</h2><p>Share of the net option price assumed to be manufacturer cost. Adjust the band to test how sensitive the picture is.</p></div>
   <label>Low %<input type="number" min={1} max={100} value={ratios.low} aria-invalid={!valid} onChange={e=>setRatio('low',e.target.value)}/></label>
   <label>High %<input type="number" min={1} max={100} value={ratios.high} aria-invalid={!valid} onChange={e=>setRatio('high',e.target.value)}/></label></div>
   {!valid&&<ErrorBox message="Enter ratios between 1 and 100, with the low value no greater than the high value."/>}</section>
  {error?<ErrorBox message={error}/>:!data?(valid?<Loading/>:null):<>
   <div className="metric-grid"><Stat label="Unique selling points" value={String(data.summary.usps)} icon={Star} note="Praise reliably exceeds complaints"/><Stat label="USPs with a cost estimate" value={String(data.summary.costed_usps)} icon={Coins} note={`${data.summary.usps-data.summary.costed_usps} have no separately priced option`}/><Stat label="Features with a cost estimate" value={String(data.summary.costed_features)} icon={TrendingUp} note={`${data.summary.priced_options} priced options linked`}/><Stat label="Records in cohort" value={number(data.denominator)} icon={ThumbsUp} note="Fixed denominator for every share"/></div>
   <section className="panel"><div className="panel-heading"><div><h2>Customer praise against estimated cost</h2><p>Each point is a feature with a priced option. Bars span the low to high cost estimate.</p></div><Badge>{data.usp_version}</Badge></div>
    {costed.length?<UspChart items={costed} selected={selected} onSelect={setSelected}/>:<Empty title="No feature has a priced option for this model" description="Choose a model with an imported equipment price list."/>}
    <div className="usp-legend"><span><i className="dot usp"/>USP</span><span><i className="dot other"/>Not a USP</span><span><i className="dot frontier"/>Best praise for its cost</span><span><i className="line"/>Efficient frontier</span></div>
    {detail&&<div className="usp-detail"><strong>{detail.feature}</strong><span>Net praise {points(detail.score)} · estimated cost {euro(detail.cost.low)}–{euro(detail.cost.high)}</span><ul>{detail.cost.options.map(option=><li key={option.option_code+option.label}>{option.label} · {euro(option.price_eur_including_vat)} list price<button className="text-link" onClick={()=>onEvidence(option.evidence_id)}>Source<ArrowUpRight size={12}/></button></li>)}</ul></div>}
    <div className="panel-footnote"><CircleHelp size={13}/> Net praise is the lower {data.assumptions.confidence_level*100}% bound of the praise share minus the upper bound of the complaint share. Small samples score low on purpose.</div></section>
   <section className="panel"><div className="list-toolbar"><select aria-label="Features shown" value={scope} onChange={e=>setScope(e.target.value as Scope)}><option value="usps">Unique selling points</option><option value="costed">Features with a cost estimate</option><option value="all">All features</option></select><span className="result-count">{rows.length} features</span></div>
    {rows.length?<UspTable rows={rows} onSelect={setSelected}/>:<Empty title="No features in this view" description="Change the filter or the evidence cohort."/>}</section></>}
 </div>;
}

function Stat({label,value,icon:Icon,note}:{label:string;value:string;icon:typeof Star;note:string}){return <section className="metric"><div className="metric-label">{label}<Icon size={19}/></div><strong className="metric-value">{value}</strong><p>{note}</p></section>;}

function UspChart({items,selected,onSelect}:{items:CostedItem[];selected:string|null;onSelect:(id:string)=>void}){
 const maxCost=Math.ceil(Math.max(...items.map(item=>item.cost.high))/COST_TICKS/COST_STEP)*COST_STEP*COST_TICKS;
 const scores=items.map(item=>item.score*100),minScore=Math.min(...scores,0),maxScore=Math.max(...scores,0),pad=(maxScore-minScore||1)*.12;
 const low=minScore-pad,high=maxScore+pad,plotWidth=CHART.width-CHART.left-CHART.right,plotHeight=CHART.height-CHART.top-CHART.bottom;
 const x=(cost:number)=>CHART.left+cost/maxCost*plotWidth,y=(score:number)=>CHART.top+(high-score)/(high-low)*plotHeight;
 const frontier=items.filter(item=>item.on_frontier).sort((a,b)=>a.cost.mid-b.cost.mid);
 return <div className="usp-chart"><svg viewBox={`0 0 ${CHART.width} ${CHART.height}`} role="group" aria-label="Net customer praise against estimated manufacturer cost per feature">
  {ticks(low,high,4).map(tick=><g key={tick}><line className="grid" x1={CHART.left} x2={CHART.width-CHART.right} y1={y(tick)} y2={y(tick)}/><text className="tick" x={CHART.left-8} y={y(tick)+3} textAnchor="end">{tick.toFixed(1)}</text></g>)}
  {ticks(0,maxCost,COST_TICKS).map(tick=><text className="tick" key={tick} x={x(tick)} y={CHART.height-CHART.bottom+16} textAnchor="middle">{euro(tick)}</text>)}
  <line className="zero" x1={CHART.left} x2={CHART.width-CHART.right} y1={y(0)} y2={y(0)}/>
  <text className="axis" x={CHART.left+plotWidth/2} y={CHART.height-8} textAnchor="middle">Estimated manufacturer cost per vehicle (mid estimate, EUR)</text>
  <text className="axis" transform={`translate(14 ${CHART.top+plotHeight/2}) rotate(-90)`} textAnchor="middle">Net praise (percentage points)</text>
  {frontier.length>1&&<polyline className="frontier-line" points={frontier.map(item=>`${x(item.cost.mid)},${y(item.score*100)}`).join(' ')}/>}
  {items.map(item=>{const cx=x(item.cost.mid),cy=y(item.score*100),label=`${item.feature}: net praise ${points(item.score)}, estimated cost ${euro(item.cost.low)} to ${euro(item.cost.high)}`;
   return <g key={item.feature_id} className={'point'+(item.is_usp?' usp':'')+(item.on_frontier?' frontier':'')+(selected===item.feature_id?' selected':'')} role="button" tabIndex={0} aria-label={label} onClick={()=>onSelect(item.feature_id)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onSelect(item.feature_id);}}}>
    <title>{label}</title><line className="range" x1={x(item.cost.low)} x2={x(item.cost.high)} y1={cy} y2={cy}/><circle className="hit" cx={cx} cy={cy} r={14}/><circle className="mark" cx={cx} cy={cy} r={item.on_frontier?6:4.5}/>
    {(item.on_frontier||selected===item.feature_id)&&<text className="point-label" x={cx+9} y={cy-8}>{item.feature}</text>}</g>;})}
 </svg></div>;
}

function UspTable({rows,onSelect}:{rows:UspItem[];onSelect:(id:string)=>void}){
 return <div className="table-scroll"><table className="requirements-table usp-table"><thead><tr><th>Feature</th><th>Category</th><th>Praise</th><th>Complaints</th><th>Net praise</th><th>Estimated cost</th><th>Praise per €100</th></tr></thead><tbody>{rows.map(item=><tr key={item.feature_id} aria-label={item.feature} onClick={()=>item.cost&&onSelect(item.feature_id)}>
  <td><span className="row-title">{item.feature}</span><span className="row-description">{item.is_usp?<Badge tone="blue">USP</Badge>:<Badge>Not a USP</Badge>}{item.on_frontier&&<Badge tone="green">Best for its cost</Badge>}</span></td>
  <td><Badge>{item.category}</Badge></td><td>{number(item.likes)}<small> · {(item.praise_share*100).toFixed(1)}%</small></td><td>{number(item.complaints)}<small> · {(item.complaint_share*100).toFixed(1)}%</small></td>
  <td><strong>{points(item.score)}</strong></td><td>{item.cost?<>{euro(item.cost.low)}–{euro(item.cost.high)}<small> · {item.cost.options.length} option{item.cost.options.length===1?'':'s'}</small></>:<Badge tone="amber">No priced option</Badge>}</td>
  <td>{item.efficiency===null?'—':item.efficiency.toFixed(3)+' pp'}</td></tr>)}</tbody></table></div>;
}
