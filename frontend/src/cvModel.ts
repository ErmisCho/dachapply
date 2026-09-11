// Pure CV-generation model-capability and progress helpers.
// Extracted from App.tsx so they can be unit-tested without a DOM: the effort/speed
// rules must follow whatever the backend reports per model, never a hard-coded provider.

export function modelEffort(model:any){return model?.default_effort||model?.efforts?.[0]||''}

export function modelSpeed(model:any){return model?.fast_tier?'fast':'normal'}

// A model with no fast_tier (e.g. every Anthropic entry today) may only run at normal speed.
export function comboValid(model:any, effort:string, speed:string){
  if(!model) return false
  if(!(model.efforts||[]).includes(effort)) return false
  return !(speed === 'fast' && !model.fast_tier)
}

// Shown in the UI while the full absolute path stays on the clipboard. Handles either slash style
// so a Windows workspace still matches a path rendered with forward slashes.
export function shortPath(path?:string, workspace?:string){
  if(!path) return ''
  if(!workspace) return path
  const norm=(value:string)=>value.replace(/\\/g,'/').replace(/\/+$/,'')
  const prefix=norm(workspace)
  const full=norm(path)
  if(full.toLowerCase().startsWith(prefix.toLowerCase()+'/')) return full.slice(prefix.length+1)
  return path
}

export function stepText(task:any){
  const total=Number(task?.step_total)||0
  const label=task?.step_label||task?.stage
  if(!total) return label||''
  const completed=Math.min(Math.max(0,Number(task?.step_completed)||0),total)
  return `${label||'Working'} · step ${completed}/${total}`
}

export type CvPick={provider:string;model:string;effort:string;speed:string}
export const emptyCvPick:CvPick={provider:'openai',model:'',effort:'',speed:'normal'}

// The one normalizer every selection change goes through -- restoring a remembered pick, changing
// provider, changing model, changing effort or speed. TASK-231: a remembered model that is no longer
// offered (LM Studio models come and go, TASK-221) falls back to the first model of its provider and
// then to the first model offered at all, and an effort or speed the resolved model does not support
// is replaced by that model's default rather than sent. The result satisfies comboValid whenever the
// resolved model lists any efforts at all, which is what gates both Generate and Readjust.
export function cvPick(models:any[], want?:Partial<CvPick>|null):CvPick{
  const list=models||[]
  const sameProvider=list.filter((x:any)=>x.provider===want?.provider)
  const model=sameProvider.find((x:any)=>x.key===want?.model)||sameProvider[0]||list[0]
  if(!model) return emptyCvPick
  const kept=model.provider===want?.provider&&model.key===want?.model
  const effort=kept&&(model.efforts||[]).includes(want?.effort)?String(want?.effort):modelEffort(model)
  const speed=kept&&want?.speed?(want.speed==='fast'&&!model.fast_tier?'normal':want.speed):modelSpeed(model)
  return {provider:model.provider,model:model.key,effort,speed}
}

// TASK-231. Scoped per account so a second user on the same browser does not inherit a selection,
// and wrapped because localStorage throws outright in private mode or with site data blocked -- a
// popup that forgets the last model is much better than one that will not open.
const cvPicksKey=(account:string)=>`dachapply_cv_picks_${account}`

export function readCvPicks(account:string):{generate?:CvPick;adjust?:CvPick}{
  try{return JSON.parse(localStorage.getItem(cvPicksKey(account))||'{}')||{}}catch{return {}}
}

export function writeCvPicks(account:string, picks:{generate:CvPick;adjust:CvPick}){
  try{localStorage.setItem(cvPicksKey(account),JSON.stringify(picks))}catch{/* storage unavailable */}
}
