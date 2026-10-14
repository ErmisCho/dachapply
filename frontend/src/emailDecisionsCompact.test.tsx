// TASK-292: Email decisions as one line per job, plus a persisted Hide/Show toggle. No DOM in this
// vitest run, so the click-to-expand itself is checked in the browser; this covers the line's content,
// the collapsed-by-default render and the toggle's stored state.
import {afterEach,describe,expect,it,vi} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {EmailDecisions,mailboxDecisionLine,storeShowEmailDecisions,storedShowEmailDecisions} from './App'
import type {MailboxSuggestion} from './types'

const suggestion=(id:number,extra:Partial<MailboxSuggestion>={}):MailboxSuggestion=>({id,job:7,job_company:'Synthetic GmbH',job_title:'Backend Engineer (m/w/d)',suggestion_type:'status_change',payload:{status:'interview'},status:'pending',created_at:'2026-10-01T10:00:00Z',decided_at:null,postponed_until:null,message:{id,sender:'"Jane Recruiter" <jane@synthetic.test>',subject:'Invitation'} as any,...extra})

function stubStorage(init:Record<string,string>={}){const store={...init};vi.stubGlobal('localStorage',{getItem:(k:string)=>store[k]??null,setItem:(k:string,v:string)=>{store[k]=v}});return store}
afterEach(()=>vi.unstubAllGlobals())

describe('TASK-292 email decisions',()=>{
  it('builds one line: company, role, sender, what is suggested',()=>{
    expect(mailboxDecisionLine([suggestion(1),suggestion(2,{suggestion_type:'feedback_clear',payload:{}})])).toEqual({company:'Synthetic GmbH',role:'Backend Engineer',sender:'Jane Recruiter',what:'Mark as interview, Clear feedback clock'})
  })

  it('renders one collapsed line per job, not the full card',()=>{
    stubStorage()
    const html=renderToStaticMarkup(<EmailDecisions suggestions={[suggestion(1),suggestion(2,{job:8,job_company:'Other AG'})]} onDecided={vi.fn()}/>)
    expect(html.match(/data-decision-line/g)?.length).toBe(2)
    expect(html).toContain('Mark as interview')
    expect(html).toContain('Jane Recruiter')
    expect(html).not.toContain('Show full conversation')
    expect(html).toContain('>Hide<')
  })

  it('hides the section from the stored choice and persists the toggle',()=>{
    const store=stubStorage({dachapply_show_email_decisions:'false'})
    const html=renderToStaticMarkup(<EmailDecisions suggestions={[suggestion(1)]} onDecided={vi.fn()}/>)
    expect(html).not.toContain('data-decision-line')
    expect(html).toContain('Email decisions (1)')
    expect(html).toContain('>Show<')
    storeShowEmailDecisions(true)
    expect(store.dachapply_show_email_decisions).toBe('true')
    expect(storedShowEmailDecisions()).toBe(true)
    storeShowEmailDecisions(false)
    expect(storedShowEmailDecisions()).toBe(false)
  })
})
