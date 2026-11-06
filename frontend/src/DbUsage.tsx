// TASK-356: database usage for the one configured account. Loaded once per view, never polled: the numbers
// change hourly at most, and opening this reads a local file, not the database.
import {useEffect,useState} from 'react'
import {api} from './api/client'

export type UsageMetric={label:string;used:number|null;limit:number;unit:string;percent:number|null}
export type DbUsage={configured:boolean;checked_at?:string|null;error?:string|null;period?:{start:string|null;end:string|null}|null;metrics?:Record<string,UsageMetric>|null}

const NOT_CONFIGURED='Database usage tracking is not configured.'
export const usageAmount=(m:UsageMetric)=>m.used===null?`unknown of ${m.limit} ${m.unit}`:`${m.used} of ${m.limit} ${m.unit} (${m.percent}%)`
const when=(iso?:string|null)=>iso?new Date(iso).toLocaleString(undefined,{dateStyle:'medium',timeStyle:'short'}):'not yet'
const checked=(usage:DbUsage)=>`Last checked: ${when(usage.checked_at)}`

function useDbUsage(){const[usage,setUsage]=useState<DbUsage|null>(null);useEffect(()=>{api('/db-usage/').then(setUsage).catch(()=>setUsage({configured:true,error:'Could not load the usage.'}))},[]);return usage}

export function DbUsageView({usage}:{usage:DbUsage|null}){
  return <section className="premium-card p-4" aria-label="Database usage"><h2 className="text-xs uppercase text-slate-500">Database usage</h2>
    {!usage?<p className="mt-2 text-sm text-slate-600">Loading…</p>:!usage.configured?<p className="mt-2 text-sm text-slate-600">{NOT_CONFIGURED}</p>:<>
      {usage.metrics&&<dl className="mt-2 grid gap-1 text-sm">{Object.values(usage.metrics).map(m=><div key={m.label} className="flex flex-wrap justify-between gap-x-3"><dt className="font-medium">{m.label}</dt><dd className="break-words">{usageAmount(m)}</dd></div>)}</dl>}
      <p className="mt-2 text-xs text-slate-500">{checked(usage)}</p>
      {usage.error&&<p className="mt-1 text-xs text-red-700" role="status">Last check failed: {usage.error}</p>}</>}
  </section>
}

export function DbUsageLineView({usage}:{usage:DbUsage|null}){
  if(!usage)return null
  const text=!usage.configured?NOT_CONFIGURED:[...Object.values(usage.metrics||{}).map(m=>`${m.label} ${usageAmount(m)}`),checked(usage)].join(' · ')
  return <p className="mb-2 break-words text-xs text-slate-600 dark:text-slate-300"><span className="font-medium">Database:</span> {text}</p>
}

export function DbUsagePanel(){return <DbUsageView usage={useDbUsage()}/>}
export function DbUsageLine(){return <DbUsageLineView usage={useDbUsage()}/>}
