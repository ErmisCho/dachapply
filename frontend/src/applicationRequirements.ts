// TASK-280.1 AC5: labels, the board badge, and the PATCH payload for a job's application_requirements.
import type {ApplicationRequirements,RequirementDocument} from './types'

export const POSTING_LANGUAGES:Record<string,string>={en:'English',de:'German',mixed:'Mixed',unclear:'Unclear'}
export const APPLICATION_LANGUAGES:Record<string,string>={'':'Not stated',en:'English',de:'German'}
export const DOCUMENT_TYPES:Record<string,string>={cover_letter:'Cover letter',motivation_letter:'Motivation letter',short_message:'Short message',other:'Other document'}
export const DOCUMENT_STATUSES:Record<string,string>={required:'Required',preferred:'Preferred',optional:'Optional',not_accepted:'Not accepted',not_mentioned:'Not mentioned',unclear:'Unclear'}

export function isAnalysed(req?:Partial<ApplicationRequirements>|null):req is ApplicationRequirements{return !!req&&Object.keys(req).length>0}

// The editor always works on a full shape, so "Not analysed yet" can still be filled in by hand.
export function editableRequirements(req?:Partial<ApplicationRequirements>|null):ApplicationRequirements{
  return {posting_language:req?.posting_language||'unclear',application_language:req?.application_language||'',application_language_quote:req?.application_language_quote||'',documents:(req?.documents||[]).map(d=>({type:d.type,name:d.name||'',status:d.status,quote:d.quote||''})),source:req?.source||'owner'}
}

export function documentLabel(doc:Pick<RequirementDocument,'type'|'name'>){return doc.type==='other'?(doc.name||'').trim()||DOCUMENT_TYPES.other:DOCUMENT_TYPES[doc.type]||doc.type}

// Board badge: application language code + the strongest letter signal. null = nothing worth a badge.
export function requirementsBadge(req?:Partial<ApplicationRequirements>|null):{label:string;title:string}|null{
  if(!isAnalysed(req))return null
  const docs=req.documents||[]
  const doc=docs.find(d=>d.status==='required')||docs.find(d=>d.status==='preferred')||docs.find(d=>d.status==='not_accepted')
  const lang=req.application_language?req.application_language.toUpperCase():''
  const letter=doc?(doc.status==='not_accepted'?`No ${documentLabel(doc).toLowerCase()}`:`${documentLabel(doc)} ${doc.status}`):''
  const label=[lang,letter].filter(Boolean).join(' · ')
  if(!label)return null
  const title=['Application requirements'+(req.source==='owner'?' (edited by you)':''),lang&&`apply in ${APPLICATION_LANGUAGES[req.application_language]}`,...docs.filter(d=>d.status!=='not_mentioned').map(d=>`${documentLabel(d)}: ${(DOCUMENT_STATUSES[d.status]||d.status).toLowerCase()}`)].filter(Boolean).join('; ')
  return {label,title}
}

// PATCH body for an owner edit. `source` is the server's to set; `name` only travels with type 'other'.
export function requirementsPayload(req:ApplicationRequirements){
  return {posting_language:req.posting_language,application_language:req.application_language,application_language_quote:req.application_language_quote,documents:req.documents.map(d=>({type:d.type,...(d.type==='other'?{name:(d.name||'').trim()}:{}),status:d.status,quote:d.quote}))}
}
