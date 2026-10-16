// TASK-280.2: labels and actions for the documents prepared automatically when a job moves into To apply.
// TASK-280.3: the owner's review of them (keep / discard / final package). TASK-299: the board badge.
export type PrepVariant={key:string;document:'cv'|'letter'|'message';language:string;letter_template?:string;status:'queued'|'running'|'ready'|'failed';error?:string;files?:Record<string,string>;missing?:boolean;progress?:number;step_label?:string;estimated_seconds_remaining?:number;review?:''|'keep'|'discard';selected?:boolean;adjusting?:boolean;adjust_error?:string}
export type PrepState={reason:string;rule:string;model:{provider?:string;model?:string;effort?:string};variants:PrepVariant[];selection?:string[];invalidated?:string}
export type PrepSummary={running:number;done:number;failed:number;progress:number;eta:number}

const DOCUMENTS:Record<string,string>={cv:'CV',letter:'Full letter',message:'Short message'}
const LANGUAGES:Record<string,string>={en:'English',de:'German'}

export function variantLabel(v:PrepVariant){return `${DOCUMENTS[v.document]||v.document} · ${LANGUAGES[v.language]||v.language.toUpperCase()}`}

const minutes=(seconds?:number)=>seconds?` · about ${Math.max(1,Math.round(seconds/60))} min left`:''

export function variantStatusText(v:PrepVariant){
  if(v.adjusting)return `Adjusting${typeof v.progress==='number'?` · ${Math.round(v.progress)}%`:''}${minutes(v.estimated_seconds_remaining)}`
  if(v.status==='ready')return v.missing?'Ready, but the file is no longer on disk':'Ready'
  if(v.status==='failed')return `Failed: ${v.error||'unknown error'}`
  if(v.status==='queued')return 'Queued'
  return `${v.step_label||'Generating'}${typeof v.progress==='number'?` · ${Math.round(v.progress)}%`:''}${minutes(v.estimated_seconds_remaining)}`
}

export function isPreparing(state?:PrepState|null){return !!state?.variants.some(v=>v.status==='queued'||v.status==='running'||v.adjusting)}

// The one button: retry only what failed, or start when nothing was prepared (e.g. after a skip).
export function prepAction(state:PrepState|null|undefined,jobStatus:string):string{
  // The server prepares only for these statuses (never New/Reviewed or Applied and later).
  if(!state||!['to_apply','ready_to_submit'].includes(jobStatus))return ''
  // TASK-280.3: a failed variant the owner discarded is not retried.
  if(state.variants.some(v=>v.status==='failed'&&v.review!=='discard'))return 'Retry failed'
  return state.variants.length?'':'Prepare now'
}

export function preparedFile(v:PrepVariant){const path=v.files?.cv_pdf||v.files?.letter_pdf||v.files?.cv_tex||v.files?.letter_tex||'';return path.split(/[\\/]/).pop()||''}

// TASK-280.3: a variant the owner can act on -- ready, with its files on disk.
export const usable=(v:PrepVariant)=>v.status==='ready'&&!v.missing

// TASK-280.3 AC5: the review badge. Generated-but-unreviewed documents say plainly that they are drafts.
export function reviewText(v:PrepVariant){return v.selected?'In final package':v.review==='discard'?'Discarded':v.review==='keep'?'Kept':'Draft'}

// The final package line, e.g. "CV · German + Full letter · German".
export function packageText(state:PrepState){const keys=state.selection||[];return state.variants.filter(v=>keys.includes(v.key)).map(variantLabel).join(' + ')}

// TASK-299: the board badge, e.g. "Preparing 2 docs ▓▓▓░░ 45% · ~2 min left"; ready / failed once done.
// eta is the slowest running variant's, from the server.
export function prepBadge(s?:PrepSummary|null):{text:string;tone:string;title:string}|null{
  if(!s)return null
  if(s.running){
    const filled=Math.round(Math.min(100,Math.max(0,s.progress))/20)
    const left=s.eta?` · ~${Math.max(1,Math.round(s.eta/60))} min left`:''
    return {text:`Preparing ${s.running} doc${s.running===1?'':'s'} ${'▓'.repeat(filled)}${'░'.repeat(5-filled)} ${s.progress}%${left}`,tone:'blue',title:`${s.done} ready, ${s.failed} failed so far`}
  }
  if(s.failed)return {text:`${s.failed} doc${s.failed===1?'':'s'} failed`,tone:'red',title:`${s.done} prepared document(s) ready; retry the failed ones on the job page`}
  return {text:`${s.done} doc${s.done===1?'':'s'} ready`,tone:'green',title:'Prepared documents are ready to review on the job page'}
}

export const anyPreparing=(active:Record<string,PrepSummary>)=>Object.values(active).some(s=>s.running>0)
