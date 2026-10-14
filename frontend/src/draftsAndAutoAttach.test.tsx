import {describe,expect,it} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {AutoAttachedControl,DraftSettings,RecheckUnmatchedMail} from './App'

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
    expect(html).toMatch(/type="checkbox" checked=""\/>Write automatic reply drafts with the model/)
    expect(html).not.toContain('no longer offered')
  })

  it('shows the stored model with its own efforts, and the switch off',()=>{
    const html=settings({draft_provider:'anthropic',draft_model:'sonnet',draft_effort:'medium',draft_auto_replies_with_model:false})
    expect(html).toContain('<option value="anthropic|sonnet" selected="">')
    expect(html).toContain('<option value="medium" selected="">medium</option>')
    expect(html).not.toContain('>xhigh<')
    expect(html).toMatch(/type="checkbox"\/>Write automatic reply drafts/)
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
