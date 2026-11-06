// TASK-355: a job's interview prep notes. Only where this account can run a model (never on the deployed
// site), so anywhere else the notes stay in the job's plain Notes list and no option shows.
import {useEffect,useState} from 'react'
import {api} from './api/client'
import {useQueue} from './PrepQueue'

export type PrepNotes={status:'idle'|'queued'|'running'|'failed'|'ready';error:string;note:{id:number;note:string;created_at:string}|null}

export const prepNotesAvailable=(job:{status:string},user:{can_generate_cv?:boolean}|null)=>job.status==='interview'&&!!user?.can_generate_cv
const busy=(state:PrepNotes|null)=>state?.status==='queued'||state?.status==='running'
const failure=(detail:string)=><div className="field-error-message mt-2" role="alert"><span className="field-error-icon" aria-hidden="true">!</span><span className="min-w-0 break-words">{detail}</span></div>

export function PrepNotesView({state,sending=false,onRun}:{state:PrepNotes|null;sending?:boolean;onRun:(regenerate:boolean)=>void}){
  const note=state?.note
  const run=(label:string,regenerate:boolean)=><button type="button" className="btn" disabled={sending} aria-busy={sending||undefined} onClick={()=>onRun(regenerate)}>{label}</button>
  return <section className="mt-4 rounded bg-white p-5 shadow-sm" aria-label="Interview prep notes">
    <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="font-semibold">Prep notes</h2>
      {state?.status==='idle'&&run('Prep notes',false)}
      {state?.status==='ready'&&run('Regenerate',true)}
      {state?.status==='failed'&&run('Retry',!!note)}</div>
    {state?.status==='queued'&&<p className="mt-2 text-sm text-slate-600" role="status">Waiting in the queue. This page updates when the notes are ready.</p>}
    {state?.status==='running'&&<p className="mt-2 text-sm text-slate-600" role="status">Writing prep notes. This page updates when they are ready.</p>}
    {state?.status==='idle'&&<p className="mt-2 text-sm text-slate-600">What to study and likely questions, from the posting, the evaluation and your profile.</p>}
    {state?.status==='failed'&&failure(state.error||'The notes could not be written.')}
    {note&&<div className="mt-3 whitespace-pre-wrap break-words text-sm">{note.note}</div>}
  </section>
}

export default function InterviewPrep({jobId,onNote}:{jobId:number;onNote?:(id:number|null)=>void}){
  const[state,setState]=useState<PrepNotes|null>(null);const[sending,setSending]=useState(false);const[err,setErr]=useState('')
  const failed=(e:any)=>setErr(e?.detail||'Could not load the prep notes.')
  const load=()=>api(`/jobs/${jobId}/interview-prep/`).then(setState).catch(failed)
  // TASK-354: no poll of its own. The navbar's queue poll already says when the run has left the queue.
  const queue=useQueue().data
  const listed=queue?.items.some(item=>item.job_id===jobId&&item.key==='interview-prep')
  useEffect(()=>{load()},[jobId])
  useEffect(()=>{if(busy(state)&&!listed)load()},[queue])
  useEffect(()=>{onNote?.(state?.note?.id??null)},[state?.note?.id])
  async function run(regenerate:boolean){setSending(true);setErr('');try{setState(await api(`/jobs/${jobId}/interview-prep/run/`,{method:'POST',body:{regenerate}}))}catch(e){failed(e)}finally{setSending(false)}}
  return <><PrepNotesView state={state} sending={sending} onRun={run}/>{err&&failure(err)}</>
}
