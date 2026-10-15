import {describe,expect,it} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {AutoAttachedControl,DraftSettings,MailboxUnmatchedRow,RecheckUnmatchedMail} from './App'

const noop=()=>{}
const options={
  models:[
    {provider:'openai',key:'gpt-6.1-sol',label:'GPT-6.1-Sol',efforts:['low','xhigh','max'],default_effort:'low',fast_tier:'priority'},
    {provider:'anthropic',key:'sonnet',label:'Claude Sonnet',efforts:['low','medium','high'],default_effort:'medium',fast_tier:''},
  ],
  draft_default:{provider:'openai',model:'gpt-6.1-sol',label:'GPT-6.1-Sol',effort:'xhigh',stored_model_missing:false},
}
const settings=(form:any,opts:any=options)=>renderToStaticMarkup(<DraftSettings form={form} setForm={noop} initialOptions={opts}/>)

describe('Settings -> Drafts (TASK-293)',()=>{
  it('defaults to the newest Codex at xhigh with model drafting on',()=>{
    const html=settings({draft_provider:'',draft_model:'',draft_effort:'',draft_auto_replies_with_model:true})
    expect(html).toContain('Draft model')
    expect(html).toContain('Default: newest Codex (GPT-6.1-Sol)')
    expect(html).toContain('<option value="xhigh" selected="">xhigh</option>')
    expect(html).not.toContain('Speed')
    expect(html).toMatch(/type="checkbox" class="row-select" checked=""\/>Write automatic reply drafts with the model/)
    expect(html).not.toContain('no longer offered')
  })

  it('shows the stored model with its own efforts, and the switch off',()=>{
    const html=settings({draft_provider:'anthropic',draft_model:'sonnet',draft_effort:'medium',draft_auto_replies_with_model:false})
    expect(html).toContain('<option value="anthropic|sonnet" selected="">')
    expect(html).toContain('<option value="medium" selected="">medium</option>')
    expect(html).not.toContain('>xhigh<')
    expect(html).toMatch(/type="checkbox" class="row-select"\/>Write automatic reply drafts/)
  })

  it('says when the stored model is no longer offered and what is used instead',()=>{
    const html=settings({draft_provider:'openai',draft_model:'gpt-5.4',draft_effort:'low',draft_auto_replies_with_model:true})
    expect(html).toContain('gpt-5.4 is no longer offered on this machine, so drafts use GPT-6.1-Sol at xhigh')
  })
})

describe('auto-attached mail (TASK-291)',()=>{
  const m:any={id:5,matched_job:3,auto_attached_at:'2026-10-14T09:00:00Z'}
  it('badges auto-attached mail with a Detach button, and nothing else',()=>{
    const html=renderToStaticMarkup(<AutoAttachedControl m={m}/>)
    expect(html).toContain('auto-attached')
    expect(html).toContain('Detach')
    expect(renderToStaticMarkup(<AutoAttachedControl m={{...m,auto_attached_at:null}}/>)).toBe('')
  })

  it('lists the dry run with its rule and offers Apply',()=>{
    const html=renderToStaticMarkup(<RecheckUnmatchedMail initialRows={[
      {id:1,received_at:'2026-09-24T10:00:00Z',sender:'Jane Doe',subject:'Invitation: Interview',job:9,job_label:'Salesforce — FDE',rule:'confident'},
      {id:2,received_at:null,sender:'Calendar',subject:'Updated invitation',job:9,job_label:'Salesforce — FDE',rule:'thread'},
    ]}/>)
    expect(html).toContain('Re-check unmatched mail')
    expect(html).toContain('Jane Doe')
    expect(html).toContain('Salesforce — FDE')
    expect(html).toContain('confident match')
    expect(html).toContain('same thread')
    expect(html).toContain('Apply (2)')
  })
})

describe('match reasons (TASK-297)',()=>{
  const sure={reason:'sender names Salesforce; only job there',unsure:false,candidates:[]}
  const unsure={reason:'2 jobs plausible, none singled out',unsure:true,candidates:[
    {id:1,label:'Hays — Data Engineer',why:'sender names Hays; title not named'},
    {id:2,label:'Hays — Platform Engineer',why:'sender names Hays; title not named'}]}
  const row=(m:any)=>renderToStaticMarkup(<MailboxUnmatchedRow m={{id:7,sender:'Anna',subject:'Your application',classification:'uncertain',body_text:'',...m}} jobs={[]} busy={false} dismissBusy={false} onAttach={noop} onDismiss={noop} onRestore={noop} onCreateJob={noop}/>)
  it('shows the reason next to the suggestion, and unsure candidates with why',()=>{
    expect(row({suggested_job:{id:3,label:'Salesforce — FDE'},match_reason:sure})).toContain('suggested: Salesforce — FDE</span><span class="ml-1 text-slate-500">(sender names Salesforce; only job there)')
    const html=row({suggested_job:null,match_reason:unsure})
    expect(html).toContain('unsure — 2 jobs plausible, none singled out; candidates: Hays — Data Engineer (sender names Hays; title not named), Hays — Platform Engineer (sender names Hays; title not named)')
    expect(html).toContain('text-amber-700')
  })
  it('puts the reason in the re-check list and on the auto-attached badge',()=>{
    expect(renderToStaticMarkup(<RecheckUnmatchedMail initialRows={[{id:1,received_at:null,sender:'Jane',subject:'Hi',job:9,job_label:'Salesforce — FDE',rule:'confident',reason:sure}]}/>)).toContain('sender names Salesforce; only job there')
    expect(renderToStaticMarkup(<AutoAttachedControl m={{id:5,matched_job:3,auto_attached_at:'2026-10-14T09:00:00Z',match_reason:{reason:'same Gmail thread as Salesforce — FDE',unsure:false,candidates:[]}} as any}/>)).toMatch(/title="Attached automatically [^"]* — same Gmail thread as Salesforce — FDE"/)
  })
})
