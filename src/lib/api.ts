'use client';
import { useEffect, useState } from 'react';
import type { components } from './api-types';
export type Cohort = components['schemas']['Cohort'];
export type RequirementView = components['schemas']['RequirementView'];
export type Ranking = components['schemas']['RankingResponse'];
export type Job = components['schemas']['JobView'];
export type DecisionInput = components['schemas']['DecisionRequest'];
export type Proposal = components['schemas']['AnalysisProposal'];
export async function api<T>(path:string,body?:unknown,signal?:AbortSignal):Promise<T>{
 const response=await fetch('/api/v1'+path,{method:body===undefined?'GET':'POST',headers:body===undefined?undefined:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal});
 if(!response.ok){let message='Request failed';try{const data=await response.json();message=typeof data.detail==='string'?data.detail:JSON.stringify(data.detail);}catch{}throw new Error(message);}
 return response.json();
}
export function useApi<T>(path:string|null,version=0){
 const [data,setData]=useState<T|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(false);
 useEffect(()=>{setData(null);setError('');if(!path){setLoading(false);return;}const controller=new AbortController();setLoading(true);api<T>(path,undefined,controller.signal).then(value=>{if(!controller.signal.aborted)setData(value);}).catch(e=>{if(e.name!=='AbortError')setError(e.message);}).finally(()=>{if(!controller.signal.aborted)setLoading(false);});return()=>controller.abort();},[path,version]);
 return {data,error,loading,setData};
}
export function cohortQuery(cohort:Cohort){return new URLSearchParams(Object.entries(cohort).filter(([,v])=>v!=null).map(([k,v])=>[k,String(v)])).toString();}
export const number=(value:number)=>new Intl.NumberFormat('en-US').format(value);
export const date=(value:string)=>new Date(value).toLocaleString('en-GB',{timeZone:'Europe/Berlin',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
