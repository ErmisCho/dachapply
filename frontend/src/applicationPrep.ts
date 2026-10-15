// TASK-280.2: labels and actions for the documents prepared automatically when a job moves into To apply.
export type PrepVariant={key:string;document:'cv'|'letter'|'message';language:string;letter_template?:string;status:'queued'|'running'|'ready'|'failed';error?:string;files?:Record<string,string>;missing?:boolean;progress?:number;step_label?:string;estimated_seconds_remaining?:number}
export type PrepState={reason:string;rule:string;model:{provider?:string;model?:string;effort?:string};variants:PrepVariant[]}

const DOCUMENTS:Record<string,string>={cv:'CV',letter:'Full letter',message:'Short message'}
const LANGUAGES:Record<string,string>={en:'English',de:'German'}

export function variantLabel(v:PrepVariant){return `${DOCUMENTS[v.document]||v.document} · ${LANGUAGES[v.language]||v.language.toUpperCase()}`}

export function variantStatusText(v:PrepVariant){
  if(v.status==='ready')return v.missing?'Ready, but the file is no longer on disk':'Ready'
  if(v.status==='failed')return `Failed: ${v.error||'unknown error'}`
  if(v.status==='queued')return 'Queued'
  const eta=v.estimated_seconds_remaining?` · about ${Math.max(1,Math.round(v.estimated_seconds_remaining/60))} min left`:''
  return `${v.step_label||'Generating'}${typeof v.progress==='number'?` · ${Math.round(v.progress)}%`:''}${eta}`
}

export function isPreparing(state?:PrepState|null){return !!state?.variants.some(v=>v.status==='queued'||v.status==='running')}

// The one button: retry only what failed, or start when nothing was prepared (e.g. after a skip).
export function prepAction(state:PrepState|null|undefined,jobStatus:string):string{
  // The server prepares only for these statuses (never New/Reviewed or Applied and later).
  if(!state||!['to_apply','ready_to_submit'].includes(jobStatus))return ''
  if(state.variants.some(v=>v.status==='failed'))return 'Retry failed'
  return state.variants.length?'':'Prepare now'
}

export function preparedFile(v:PrepVariant){const path=v.files?.cv_pdf||v.files?.letter_pdf||v.files?.cv_tex||v.files?.letter_tex||'';return path.split(/[\\/]/).pop()||''}
