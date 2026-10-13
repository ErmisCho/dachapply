import {describe,expect,it} from 'vitest'
import appSource from './App.tsx?raw'
import {documentLabel,editableRequirements,isAnalysed,requirementsBadge,requirementsPayload} from './applicationRequirements'
import type {ApplicationRequirements} from './types'

const analysed:ApplicationRequirements={posting_language:'mixed',application_language:'de',application_language_quote:'Bewerbung bitte auf Deutsch',source:'analysis',documents:[
  {type:'cover_letter',status:'not_mentioned',quote:''},
  {type:'motivation_letter',status:'required',quote:'Motivationsschreiben erforderlich'},
  {type:'other',name:'Portfolio',status:'optional',quote:'Portfolio optional'},
]}

describe('application requirement labels (TASK-280.1)',()=>{
  it('labels each document type, using the name only for other',()=>{
    expect(documentLabel({type:'cover_letter'})).toBe('Cover letter')
    expect(documentLabel({type:'motivation_letter'})).toBe('Motivation letter')
    expect(documentLabel({type:'short_message'})).toBe('Short message')
    expect(documentLabel({type:'other',name:' Portfolio '})).toBe('Portfolio')
    expect(documentLabel({type:'other',name:''})).toBe('Other document')
  })
  it('treats {} and missing as not analysed, and still gives the editor a full shape',()=>{
    expect(isAnalysed({})).toBe(false)
    expect(isAnalysed(undefined)).toBe(false)
    expect(isAnalysed(analysed)).toBe(true)
    expect(editableRequirements({})).toEqual({posting_language:'unclear',application_language:'',application_language_quote:'',documents:[],source:'owner'})
  })
})

describe('board badge',()=>{
  it('shows the application language and the strongest letter signal',()=>{
    const b=requirementsBadge(analysed)!
    expect(b.label).toBe('DE · Motivation letter required')
    expect(b.title).toContain('apply in German')
    expect(b.title).toContain('Portfolio: optional')
    expect(b.title).not.toContain('Cover letter')
  })
  it('prefers required over preferred, and reports an explicit no-letter',()=>{
    expect(requirementsBadge({...analysed,application_language:'',documents:[{type:'cover_letter',status:'preferred',quote:'x'},{type:'short_message',status:'required',quote:'y'}]})!.label).toBe('Short message required')
    expect(requirementsBadge({...analysed,application_language:'en',documents:[{type:'cover_letter',status:'not_accepted',quote:'no cover letter'}]})!.label).toBe('EN · No cover letter')
  })
  it('renders nothing when not analysed or when there is nothing to say',()=>{
    expect(requirementsBadge({})).toBeNull()
    expect(requirementsBadge({...analysed,application_language:'',documents:[{type:'cover_letter',status:'not_mentioned',quote:''}]})).toBeNull()
  })
  it('says when the owner edited it',()=>{
    expect(requirementsBadge({...analysed,source:'owner'})!.title).toMatch(/^Application requirements \(edited by you\)/)
  })
})

describe('edit payload',()=>{
  it('drops source and keeps name only for other documents',()=>{
    const edited=editableRequirements(analysed)
    expect(requirementsPayload(edited)).toEqual({posting_language:'mixed',application_language:'de',application_language_quote:'Bewerbung bitte auf Deutsch',documents:[
      {type:'cover_letter',status:'not_mentioned',quote:''},
      {type:'motivation_letter',status:'required',quote:'Motivationsschreiben erforderlich'},
      {type:'other',name:'Portfolio',status:'optional',quote:'Portfolio optional'},
    ]})
    expect(requirementsPayload(edited)).not.toHaveProperty('source')
  })
})

describe('wiring in App.tsx',()=>{
  it('saves through the job details PATCH only when the requirements changed',()=>{
    expect(appSource).toContain('...(JSON.stringify(reqForm)!==reqInitial.current?{application_requirements:requirementsPayload(reqForm)}:{})')
    expect(appSource).toContain('const dirty=JSON.stringify({form,evForm,reqForm})!==baseline.current')
    expect(appSource).toContain('setReqForm(nextReq)')
  })
  it('renders the editor on the job page and the badge on both board layouts',()=>{
    expect(appSource).toContain('<ApplicationRequirementsEditor value={reqForm} analysed={isAnalysed(job.application_requirements)}')
    expect(appSource).toContain("{!analysed?'Not analysed yet':source==='owner'?'Edited by you':'From the job analysis'}")
    expect(appSource).toContain('<figcaption className="font-medium">The posting says:</figcaption>')
    expect(appSource).toContain('<UrgencyBadges job={j} className="flex shrink-0 gap-1"/><RequirementsBadge job={j} className="flex shrink-0"/>')
    expect(appSource).toContain('<UrgencyBadges job={j}/><RequirementsBadge job={j}/>')
  })
})
