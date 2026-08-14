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

export function stepText(task:any){
  const total=Number(task?.step_total)||0
  const label=task?.step_label||task?.stage
  if(!total) return label||''
  const completed=Math.min(Math.max(0,Number(task?.step_completed)||0),total)
  return `${label||'Working'} · step ${completed}/${total}`
}
