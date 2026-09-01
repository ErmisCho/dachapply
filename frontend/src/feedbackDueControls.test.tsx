import {describe,expect,it,vi} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {FeedbackDueRow,JobMailboxConversationCard,loadFeedbackMailbox,locateFeedbackJob,updateFeedbackDueJob} from './App'
import type {FeedbackDueRow as FeedbackRow,JobMailboxPayload} from './types'

const row:FeedbackRow={id:208,company:'Synthetic GmbH',title:'Backend Engineer',status:'interview',feedback_due_date:'2026-09-09',gmail_search_url:'https://mail.google.test/#search/Synthetic%20GmbH'}
const props=()=>({row,overdue:false,followedUp:false,onGo:vi.fn(),onEmail:vi.fn(),onFollowedUp:vi.fn(),onReschedule:vi.fn(),onStatusChange:vi.fn()})
function elements(node:any,out:any[]=[]):any[]{if(Array.isArray(node)){node.forEach(x=>elements(x,out));return out}if(!node||typeof node!=='object')return out;if(node.type)out.push(node);elements(node.props?.children,out);return out}

describe('feedback deadline row controls (TASK-208)',()=>{
  it('renders reschedule and every real job status for this lead',()=>{
    const html=renderToStaticMarkup(<FeedbackDueRow {...props()}/>)
    expect(html).toContain('Reschedule feedback for Synthetic GmbH — Backend Engineer')
    expect(html).toContain('Change status for Synthetic GmbH — Backend Engineer')
    for(const status of ['new','reviewed','to_apply','applied','interview','offer','accepted','rejected','withdrawn','skipped','archived'])expect(html).toContain(`value="${status}"`)
  })

  it('opens the adjacent accessible email action',()=>{
    const callbacks=props()
    const all=elements(FeedbackDueRow(callbacks))
    const email=all.find(x=>x.type==='button'&&x.props['aria-label']==='Open email conversation for Synthetic GmbH — Backend Engineer')
    expect(email.props.className).toContain('min-h-[2.75rem]')
    expect(email.props.className).toContain('min-w-[2.75rem]')
    email.props.onClick()
    expect(callbacks.onEmail).toHaveBeenCalledOnce()
  })

  it('uses the owner-scoped job PATCH and returns failures without pretending they saved',async()=>{
    const request=vi.fn().mockResolvedValueOnce({...row,status:'offer'}).mockRejectedValueOnce({detail:'synthetic refusal'})

    const success=await updateFeedbackDueJob(row.id,{status:'offer'},request)
    const failure=await updateFeedbackDueJob(row.id,{feedback_due_date:'2026-09-15'},request)

    expect(request).toHaveBeenNthCalledWith(1,'/jobs/208/',{method:'PATCH',body:{status:'offer'}})
    expect(request).toHaveBeenNthCalledWith(2,'/jobs/208/',{method:'PATCH',body:{feedback_due_date:'2026-09-15'}})
    expect(success.updated?.status).toBe('offer')
    expect(success.error).toBeNull()
    expect(failure.updated).toBeNull()
    expect(failure.error).toEqual({detail:'synthetic refusal'})
  })

  it('loads the conversation once through the existing job-mailbox endpoint',async()=>{
    const request=vi.fn().mockResolvedValue({messages:[],notes:[]})
    expect(await loadFeedbackMailbox(208,request)).toEqual({messages:[],notes:[]})
    expect(request).toHaveBeenCalledOnce()
    expect(request).toHaveBeenCalledWith('/jobs/208/mailbox/')
  })

  it('locates a mounted row without reload and reloads only for a filtered-out row',async()=>{
    const mounted:any={offsetParent:{},scrollIntoView:vi.fn(),setAttribute:vi.fn()}
    const directRoot={querySelectorAll:vi.fn(()=>[mounted])}
    const directReload=vi.fn()
    expect(await locateFeedbackJob(208,directReload,directRoot,vi.fn())).toBe('mounted')
    expect(directReload).not.toHaveBeenCalled()
    expect(mounted.scrollIntoView).toHaveBeenCalledWith({block:'center'})

    let loaded=false
    const fallbackRoot={querySelectorAll:vi.fn(()=>loaded?[mounted]:[])}
    const fallbackReload=vi.fn(async()=>{loaded=true})
    expect(await locateFeedbackJob(208,fallbackReload,fallbackRoot,vi.fn())).toBe('reloaded')
    expect(fallbackReload).toHaveBeenCalledOnce()
  })

  it('shows the existing chat thread and an honest no-recipient fallback',()=>{
    const message=(id:number,own:boolean,received_at:string)=>({id,sender:own?'owner@example.test':'Recruiter <hr@example.test>',subject:'CTO follow-up',body_text:own?'Thanks, I will wait.':'Please follow up next week.',received_at,classification:'recruiter_reply',matched_job:208,matched_job_company:'Synthetic GmbH',matched_job_title:'Backend Engineer',draft:null,thread_id:'thread-208',gmail_url:`https://mail.google.test/#all/thread-208-${id}`,sent_by_owner:own,created_at:received_at,calendar_summary:'',calendar_location:'',calendar_organizer:'',calendar_start:null,calendar_end:null,attachments:[],suggestions:[]})
    const mailbox={messages:[message(2,true,'2026-09-02T10:00:00Z'),message(1,false,'2026-09-01T10:00:00Z')],notes:[]} as unknown as JobMailboxPayload
    const html=renderToStaticMarkup(<JobMailboxConversationCard jobId={208} company="Synthetic GmbH" title="Backend Engineer" suggestions={[]} onDecided={vi.fn()} initialMailbox={mailbox} initialHistoryOpen gmailSearchUrl={row.gmail_search_url}/>)
    expect(html).toContain('Full conversation (2 messages captured')
    expect(html.indexOf('Recruiter')).toBeLessThan(html.indexOf('owner@example.test'))
    expect(html).toContain('Open this message in Gmail')
    expect(html).toContain('Reply to this message')

    const empty=renderToStaticMarkup(<JobMailboxConversationCard jobId={208} company="Synthetic GmbH" title="Backend Engineer" suggestions={[]} onDecided={vi.fn()} initialMailbox={{messages:[],notes:[]}} initialHistoryOpen gmailSearchUrl={row.gmail_search_url}/>)
    expect(empty).toContain('No captured email conversation or recipient is known')
    expect(empty).toContain('Search Gmail for Synthetic GmbH')
    expect(empty).not.toContain('mailto:')
  })

  it('lets reschedule and status changes run independently or in sequence',()=>{
    const callbacks=props()
    const tree=FeedbackDueRow(callbacks)
    const all=elements(tree)
    const status=all.find(x=>x.type==='select')
    const date=all.find(x=>x.type==='input'&&x.props.type==='date')

    status.props.onChange({target:{value:'interview'}})
    expect(callbacks.onStatusChange).not.toHaveBeenCalled()
    date.props.onBlur({target:{value:'2026-09-15'}})
    status.props.onChange({target:{value:'rejected'}})

    expect(callbacks.onReschedule).toHaveBeenCalledWith('2026-09-15')
    expect(callbacks.onStatusChange).toHaveBeenCalledWith('rejected')
  })
})
