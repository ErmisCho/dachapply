// TASK-406.3: the owner's failed-document groups, their records and the supervised fix runs. All text is rendered as text.
import {useCallback,useEffect,useRef,useState} from 'react'
import {api} from './api/client'
import {pollWhileVisible} from './appUtils'

export type FixRun={id:string;signature:string;state:string;step?:string;started_at?:string;finished_at?:string;log?:string[];pr_url?:string;task_id?:string;error?:string}
export type Group={signature:string;cause:string;class:string;count:number;last:string;job_ids:number[];task_id:string;state:string;run:FixRun|null}
export type FailRecord={id:string;time:string;job_id:number|null;route:string;provider:string;model:string;error:string;diagnostics:string;instructions:string;files:{name:string;text:string|null}[]}
export type FailuresData={groups:Group[];fix:{enabled:boolean;reason:string}}

const STATES:Record<string,string>={new:'New',running:'Running',pr:'PR open',merged:'Merged',failed:'Failed',stopped:'Stopped',interrupted:'Interrupted',not_a_bug:'Not a bug',look:'Needs a look'}
export const stateLabel=(s:string)=>STATES[s]||s
export const hasRunning=(d:FailuresData|null)=>!!d?.groups.some(g=>g.run?.state==='running')
export const safePr=(url?:string)=>url&&url.startsWith('https://github.com/')?url:''
export function elapsed(run:FixRun,now=Date.now()){const a=Date.parse(run.started_at||'');if(!a)return '';const s=Math.max(0,Math.round(((Date.parse(run.finished_at||'')||now)-a)/1000));return s<60?`${s}s`:`${Math.floor(s/60)}m ${s%60}s`}
const when=(iso:string)=>new Date(iso).toLocaleString(undefined,{dateStyle:'medium',timeStyle:'short'})
const pre='mt-1 max-h-64 overflow-auto whitespace-pre-wrap break-all rounded border bg-slate-50 p-2 text-xs dark:bg-slate-900'

export function RunView({run}:{run:FixRun}){const pr=safePr(run.pr_url)
  return <div className="mt-2 text-sm"><p className="break-words"><b>{stateLabel(run.state)}</b>{run.step&&<> · {run.step}</>}{elapsed(run)&&<> · {elapsed(run)}</>}</p>
    {run.error&&<p className="break-words text-red-700 dark:text-red-300" role="status">{run.error}</p>}
    {!!run.log?.length&&<pre className={pre} aria-label="Last log lines">{run.log.join('\n')}</pre>}
    {pr&&<p className="mt-1"><a className="break-all underline" href={pr} target="_blank" rel="noreferrer">{pr}</a></p>}</div>}

export function RecordsView({records}:{records:FailRecord[]|undefined}){
  if(!records)return <p className="mt-2 text-sm">Loading…</p>
  if(!records.length)return <p className="mt-2 text-sm">No records.</p>
  return <div className="mt-2 grid gap-3">{records.map(r=><article key={r.id} className="rounded border p-2 text-sm"><p className="break-words text-xs text-slate-600 dark:text-slate-300">{when(r.time)} · job {r.job_id??'?'} · {r.route} · {[r.provider,r.model].filter(Boolean).join(' ')}</p>
    <h4 className="mt-1 font-medium">Error</h4><pre className={pre}>{r.error}</pre>
    {r.diagnostics&&<><h4 className="mt-1 font-medium">Diagnostics</h4><pre className={pre}>{r.diagnostics}</pre></>}
    {r.instructions&&<><h4 className="mt-1 font-medium">Instructions</h4><pre className={pre}>{r.instructions}</pre></>}
    {r.files.map(f=><div key={f.name}><h4 className="mt-1 break-all font-medium">{f.name}</h4>{f.text===null?<p className="text-xs">File is gone or not readable.</p>:<pre className={pre}>{f.text}</pre>}</div>)}</article>)}</div>}

export function FailuresView({data,error,open,records,busy,onOpen,onFix,onStop}:{data:FailuresData|null;error:string;open:string;records?:FailRecord[];busy:string;onOpen:(s:string)=>void;onFix:(s:string)=>void;onStop:(id:string)=>void}){
  return <main className="mx-auto max-w-5xl space-y-4 px-4 py-5"><h1 className="text-3xl font-semibold">Failures</h1>
    {error&&<p className="break-words text-sm text-red-700 dark:text-red-300" role="alert">{error}</p>}
    {!data&&!error&&<p className="text-sm">Loading…</p>}
    {data&&!data.groups.length&&<p className="text-sm">No failed documents recorded.</p>}
    {data?.groups.map(g=>{const run=g.run;return <section key={g.signature} className="premium-card p-4" aria-label={g.cause}>
      <h2 className="break-words font-medium">{g.cause}</h2>
      <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 text-sm"><dt>Count</dt><dd>{g.count}</dd><dt>Last</dt><dd>{when(g.last)}</dd><dt>Class</dt><dd>{g.class}</dd><dt>Task</dt><dd className="break-words">{g.task_id||'none'}</dd><dt>State</dt><dd>{stateLabel(g.state)}</dd></dl>
      {run&&<RunView run={run}/>}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <button type="button" className="btn-muted" aria-expanded={open===g.signature} onClick={()=>onOpen(g.signature)}>{open===g.signature?'Hide records':'Show records'}</button>
        {g.class==='actionable'&&run?.state!=='running'&&<button type="button" className="btn-primary" disabled={!data.fix.enabled||busy===g.signature} onClick={()=>onFix(g.signature)}>Fix</button>}
        {run?.state==='running'&&<button type="button" className="btn-muted" disabled={busy===run.id} onClick={()=>onStop(run.id)}>Stop</button>}
        {g.class==='actionable'&&!data.fix.enabled&&<span className="break-words text-xs">{data.fix.reason}</span>}</div>
      {open===g.signature&&<RecordsView records={records}/>}</section>})}</main>}

export default function Failures(){
  const[data,setData]=useState<FailuresData|null>(null),[error,setError]=useState(''),[open,setOpen]=useState(''),[records,setRecords]=useState<FailRecord[]>(),[busy,setBusy]=useState('')
  const load=useCallback(()=>api('/failures/').then((d:FailuresData)=>{setData(d);setError('')}).catch((e:any)=>setError(e?.detail||'Could not load the failures.')),[])
  useEffect(()=>{load()},[load])
  const running=hasRunning(data)
  useEffect(()=>running?pollWhileVisible(load,3000):undefined,[running,load])
  const act=(id:string,path:string)=>{setBusy(id);api(path,{method:'POST'}).then(load).catch((e:any)=>setError(e?.detail||'The request failed.')).finally(()=>setBusy(''))}
  const wanted=useRef('')  // a slow answer for a group opened before must not show under the one open now
  const onOpen=(s:string)=>{wanted.current=open===s?'':s;setOpen(wanted.current);if(!wanted.current)return;setRecords(undefined);api(`/failures/${s}/`).then(d=>{if(wanted.current===s)setRecords(d.records)}).catch((e:any)=>setError(e?.detail||'Could not load the records.'))}
  return <FailuresView data={data} error={error} open={open} records={records} busy={busy} onOpen={onOpen} onFix={s=>act(s,`/failures/${s}/fix/`)} onStop={id=>act(id,`/failures/runs/${id}/stop/`)}/>
}
