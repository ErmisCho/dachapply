// TASK-312: the queue of documents prepared automatically after analysis -- what is running, what waits,
// what was produced and what failed -- and the owner's controls over it. One module-level store feeds both
// this page and the navbar's count, so being on the page costs no second poll. No DOM in the test suite
// (TASK-177), so the store is plain functions and the page is a pure view of its snapshot.
import {useSyncExternalStore} from 'react'
import {Link} from 'react-router-dom'
import {api} from './api/client'
import {timeLeft} from './applicationPrep'

export type QueueStatus='queued'|'running'|'blocked'|'ready'|'failed'|'cancelled'
export type QueueItem={job_id:number;company:string;title:string;job_status:string;key:string;label:string;document:'cv'|'letter'|'message'|null;language:string|null;status:QueueStatus;position:number|null;progress:number;eta_seconds:number|null;error:string;files:string[];queued_at:string|null;started_at:string|null;finished_at:string|null}
export type QueueData={concurrency:number;items:QueueItem[]}
export type QueueAction='cancel'|'retry'|'first'
export type QueueSnapshot={data:QueueData|null;error:string;busy:string[];failed:{id:string;detail:string}|null}

const PATH='/jobs/application-prep/queue/'
const ACTIONS:Record<QueueAction,string>={first:'Move to front',cancel:'Cancel',retry:'Retry'}
const actionId=(item:QueueItem,action:QueueAction)=>`${item.job_id}:${item.key}:${action}`

let snap:QueueSnapshot={data:null,error:'',busy:[],failed:null}
const listeners=new Set<()=>void>()
let pages=0,timer:ReturnType<typeof setTimeout>|undefined
function set(next:Partial<QueueSnapshot>){snap={...snap,...next};listeners.forEach(f=>f())}

export const activeCount=(data:QueueData|null)=>data?.items.filter(i=>i.status==='queued'||i.status==='running').length||0
// Fast only while the page is open and something is moving; the navbar count alone never polls fast.
export const queueDelay=(data:QueueData|null,onPage:boolean)=>onPage&&activeCount(data)?3000:30000
function schedule(){clearTimeout(timer);timer=listeners.size?setTimeout(poll,queueDelay(snap.data,pages>0)):undefined}
async function poll(){try{set({data:await api(PATH),error:''})}catch(e:any){set({error:e?.detail||'Could not load the queue.'})}schedule()}

// Subscribing loads at once and keeps polling until the last subscriber leaves.
export function watchQueue(onChange:()=>void,page=false){listeners.add(onChange);if(page)pages++;poll();return()=>{listeners.delete(onChange);if(page)pages--;if(!listeners.size){clearTimeout(timer);timer=undefined}}}
const watchPage=(onChange:()=>void)=>watchQueue(onChange,true)
export const queueSnapshot=()=>snap
export function useQueue(page=false){return useSyncExternalStore(page?watchPage:watchQueue,queueSnapshot,queueSnapshot)}

export async function queueAction(item:QueueItem,action:QueueAction){
  const id=actionId(item,action);set({busy:[...snap.busy,id],failed:null})
  try{set({data:await api(PATH+'action/',{method:'POST',body:{job_id:item.job_id,key:item.key,action}})})}
  catch(e:any){set({failed:{id,detail:e?.detail||'The action failed.'}})}
  finally{set({busy:snap.busy.filter(b=>b!==id)})}
  schedule()   // a retry can start the fast poll, a cancel can end it
}

const when=(iso:string|null)=>iso?new Date(iso).toLocaleString(undefined,{dateStyle:'medium',timeStyle:'short'}):''

function Job({item}:{item:QueueItem}){return <Link className="break-words text-slate-600 underline-offset-2 hover:underline" to={`/jobs/${item.job_id}`}>{item.company} — {item.title}</Link>}

function Section({title,items,children}:{title:string;items:QueueItem[];children:(item:QueueItem)=>any}){
  if(!items.length)return null
  return <section className="rounded bg-white p-4 shadow-sm" aria-label={title}><h2 className="font-semibold">{title} <span className="text-sm font-normal text-slate-500">({items.length})</span></h2>
    <ul className="mt-2 grid gap-2 text-sm">{items.map(item=><li key={`${item.job_id}:${item.key}`} className="min-w-0 rounded border border-slate-100 p-2">{children(item)}</li>)}</ul></section>
}

export function QueueView({snap,onAction=queueAction}:{snap:QueueSnapshot;onAction?:(item:QueueItem,action:QueueAction)=>void}){
  const items=snap.data?.items||[]
  const of=(...statuses:QueueStatus[])=>items.filter(i=>statuses.includes(i.status))
  const button=(item:QueueItem,action:QueueAction)=>{const id=actionId(item,action);const busy=snap.busy.includes(id)
    return <button type="button" className={action==='cancel'?'btn-danger':'btn-muted'} disabled={busy||(action==='first'&&item.position===1)} aria-busy={busy||undefined} onClick={()=>onAction(item,action)}>{ACTIONS[action]}</button>}
  const failure=(item:QueueItem)=>snap.failed?.id.startsWith(`${item.job_id}:${item.key}:`)?<div className="field-error-message mt-1" role="alert"><span className="field-error-icon" aria-hidden="true">!</span><span>{snap.failed.detail}</span></div>:null
  return <main className="mx-auto max-w-4xl space-y-4 px-4 py-6">
    <div><h1 className="text-xl font-semibold">Document queue</h1>{snap.data&&<p className="text-sm text-slate-500">Up to {snap.data.concurrency} document{snap.data.concurrency===1?' is':'s are'} prepared at a time.</p>}</div>
    {snap.error&&<div className="field-error-message" role="alert"><span className="field-error-icon" aria-hidden="true">!</span><span>{snap.error}</span></div>}
    {!snap.data&&!snap.error&&<p className="text-slate-500">Loading…</p>}
    {snap.data&&!items.length&&<p className="text-sm text-slate-600">Nothing in the queue. Documents are queued automatically once a job is analysed as apply or maybe.</p>}
    <Section title="Running" items={of('running')}>{item=><>
      <div className="flex flex-wrap items-baseline gap-x-2"><span className="font-medium">{item.label}</span><Job item={item}/></div>
      <progress className="mt-1 block h-2 w-full appearance-none overflow-hidden rounded-full bg-slate-200 dark:bg-white/10 [&::-moz-progress-bar]:bg-blue-500 [&::-webkit-progress-bar]:bg-transparent [&::-webkit-progress-value]:bg-blue-500" max={100} value={item.progress} aria-label={`${item.label} progress`}/>
      <p className="text-xs text-slate-500">{Math.round(item.progress)}%{item.eta_seconds?` · ${timeLeft(item.eta_seconds)}`:''}</p></>}</Section>
    <Section title="Queued" items={of('queued')}>{item=><>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1"><span className="font-medium">#{item.position} {item.label}</span><Job item={item}/><span className="ml-auto flex gap-1">{button(item,'first')}{button(item,'cancel')}</span></div>{failure(item)}</>}</Section>
    <Section title="Blocked" items={of('blocked')}>{item=><>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1"><span className="font-medium">{item.label}</span><Job item={item}/><span className="ml-auto">{button(item,'retry')}</span></div>
      <p className="text-xs text-red-700">{item.error}</p>{failure(item)}</>}</Section>
    <Section title="Done" items={of('ready')}>{item=><>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1"><span className="font-medium">{item.label}</span><Job item={item}/><Link className="btn-muted ml-auto" to={`/jobs/${item.job_id}`}>Review</Link></div>
      {item.files.length>0&&<ul className="mt-1 break-all text-xs text-slate-600">{item.files.map(f=><li key={f}>{f}</li>)}</ul>}
      {item.finished_at&&<p className="text-xs text-slate-500">Finished {when(item.finished_at)}</p>}</>}</Section>
    <Section title="Failed / cancelled" items={of('failed','cancelled')}>{item=><>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1"><span className="font-medium">{item.label}</span><Job item={item}/><span className="ml-auto">{button(item,'retry')}</span></div>
      <p className={item.status==='cancelled'?'text-xs text-slate-600':'text-xs text-red-700'}>{item.status==='cancelled'?'Cancelled':`Failed: ${item.error||'unknown error'}`}</p>{failure(item)}</>}</Section>
  </main>
}

export default function PrepQueue(){return <QueueView snap={useQueue(true)}/>}
