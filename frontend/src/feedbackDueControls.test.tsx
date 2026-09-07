import {describe,expect,it,vi} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {FeedbackDueList,FeedbackDuePaneHeader,FeedbackDueRow,JobMailboxConversationCard,applyFeedbackDueWrite,feedbackDueEmptyMessage,feedbackStatusPatch,loadFeedbackMailbox,locateFeedbackJob,refreshFeedbackDueRows,updateFeedbackDueJob} from './App'
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


// TASK-209 (TASK-208 AC5). The middle of the two pane actions, which the block above never touched:
// it proved the row emits a status and that the PATCH helper reports a refusal, but nothing proved
// what the status change SENDS, that a success reaches the board row and refetches the pane, that a
// refusal changes nothing, or that a refusal is visible at all. All synthetic - invented company, a
// .test recipient domain, hand-rolled fakes for every collaborator, no network.
const overdueRow:FeedbackRow={...row,id:208}
const upcomingRow:FeedbackRow={...row,id:209,company:'Beispiel Datentechnik AG',title:'Platform Engineer',status:'applied',feedback_due_date:'2026-09-30'}

describe('feedback deadline writes (TASK-208 AC5)',()=>{
  it('sends the status metadata the board writes, and clears what the new status does not carry',()=>{
    expect(feedbackStatusPatch('interview','2026-09-07')).toEqual({status:'interview',status_date:'2026-09-07',last_update_date:'2026-09-07',interview_stage:1,interview_total:5})
    expect(feedbackStatusPatch('offer','2026-09-07')).toEqual({status:'offer',status_date:'2026-09-07',last_update_date:'2026-09-07',interview_stage:null,interview_total:null})
    expect(feedbackStatusPatch('rejected','2026-09-07')).toEqual({status:'rejected',status_date:'2026-09-07',last_update_date:null,interview_stage:null,interview_total:null})
    expect(feedbackStatusPatch('withdrawn','2026-09-07')).toEqual({status:'withdrawn',status_date:null,last_update_date:null,interview_stage:null,interview_total:null})
  })

  it('lands a successful write on the board row and refetches the pane',async()=>{
    const saved={id:208,status:'offer',feedback_due_date:'2026-09-30'}
    const update=vi.fn().mockResolvedValue({updated:saved,error:null})
    const setError=vi.fn()
    const reload=vi.fn().mockResolvedValue(undefined)
    let jobs:any[]=[{id:207,status:'applied'},{id:208,status:'applied'}]
    const setJobs=vi.fn((updater:any)=>{jobs=updater(jobs)})

    expect(await applyFeedbackDueWrite(208,feedbackStatusPatch('offer','2026-09-07'),setError,setJobs,reload,update)).toBe(true)

    expect(update).toHaveBeenCalledWith(208,{status:'offer',status_date:'2026-09-07',last_update_date:'2026-09-07',interview_stage:null,interview_total:null})
    expect(jobs).toEqual([{id:207,status:'applied'},saved])
    expect(reload).toHaveBeenCalledOnce()
    expect(setError.mock.calls).toEqual([[null]])
  })

  it('lets a refused write change nothing at all, including the pane',async()=>{
    const update=vi.fn().mockResolvedValue({updated:null,error:{detail:'synthetic refusal'}})
    const setError=vi.fn()
    const setJobs=vi.fn()
    const reload=vi.fn().mockResolvedValue(undefined)

    expect(await applyFeedbackDueWrite(208,{feedback_due_date:'2026-09-30'},setError,setJobs,reload,update)).toBe(false)

    expect(setError.mock.calls).toEqual([[null],[{detail:'synthetic refusal'}]])
    expect(setJobs).not.toHaveBeenCalled()
    expect(reload).not.toHaveBeenCalled()
  })

  it('shows a refused write in the pane instead of swallowing it',()=>{
    const header=(error:any)=>renderToStaticMarkup(<FeedbackDuePaneHeader showOverdue showUpcoming loading={false} error={error} onShowOverdue={vi.fn()} onShowUpcoming={vi.fn()}/>)
    const failed=header({detail:'synthetic refusal'})
    expect(failed).toContain('role="alert"')
    expect(failed).toContain('synthetic refusal')
    expect(header(null)).not.toContain('role="alert"')
  })

  it('wires every row control to that row, not to the first or to nothing',()=>{
    const onReschedule=vi.fn()
    const onStatusChange=vi.fn()
    const onEmail=vi.fn()
    const list=FeedbackDueList({overdue:[overdueRow],upcoming:[upcomingRow],followedUpJobIds:new Set<number>(),onGo:vi.fn(),onEmail,onFollowedUp:vi.fn(),onReschedule,onStatusChange})
    const rows=elements(list).filter(x=>x.type===FeedbackDueRow)

    expect(rows.map(x=>x.props.row.id)).toEqual([208,209])
    expect(rows.map(x=>x.props.overdue)).toEqual([true,false])

    rows[1].props.onStatusChange('rejected')
    rows[0].props.onReschedule('2026-09-30')
    rows[1].props.onEmail()

    expect(onStatusChange).toHaveBeenCalledWith(upcomingRow,'rejected')
    expect(onReschedule).toHaveBeenCalledWith(overdueRow,'2026-09-30')
    expect(onEmail).toHaveBeenCalledWith(upcomingRow)
  })
})


// TASK-217. The pane's READ, which the two blocks above never touched: they proved a refused WRITE is
// visible, while a refused refresh emptied the rows and printed "No actionable job has a feedback
// deadline right now." - a claim about the server made when the server never answered, and printed
// immediately after a status change, where it is indistinguishable from the lead having been filtered
// out. All synthetic: invented companies, .test domains, a hand-rolled request fake, no network.
const staleRows:FeedbackRow[]=[{...row,id:210,company:'Nordlicht Systeme GmbH',title:'Site Reliability Engineer',status:'applied',feedback_due_date:'2026-09-10',gmail_search_url:'https://mail.google.test/#search/Nordlicht'}]

function paneState(initial:FeedbackRow[]=[]){
  const state:{rows:FeedbackRow[];error:any}={rows:initial,error:null}
  return {state,setRows:(rows:any[])=>{state.rows=rows as FeedbackRow[]},setError:(e:any)=>{state.error=e}}
}

describe('feedback deadline refresh (TASK-217)',()=>{
  it('reports a failed refresh instead of emptying the pane behind it',async()=>{
    const pane=paneState(staleRows)
    const request=vi.fn().mockRejectedValue({detail:'synthetic gateway timeout'})

    expect(await refreshFeedbackDueRows(pane.setRows,pane.setError,request)).toBe(false)

    expect(request).toHaveBeenCalledWith('/jobs/feedback-due/')
    expect(pane.state.rows).toEqual(staleRows)
    expect(pane.state.error).not.toBeNull()
    const header=renderToStaticMarkup(<FeedbackDuePaneHeader showOverdue showUpcoming loading={false} error={pane.state.error} onShowOverdue={vi.fn()} onShowUpcoming={vi.fn()}/>)
    expect(header).toContain('role="alert"')
    expect(header).toContain('may be out of date')
    expect(header).toContain('synthetic gateway timeout')
  })

  it('renders the refreshed rows with no error when the refresh lands',async()=>{
    const pane=paneState([])
    const request=vi.fn().mockResolvedValue(staleRows)

    expect(await refreshFeedbackDueRows(pane.setRows,pane.setError,request)).toBe(true)

    expect(pane.state.rows).toEqual(staleRows)
    expect(pane.state.error).toBeNull()
    expect(renderToStaticMarkup(<FeedbackDueList overdue={[]} upcoming={pane.state.rows} followedUpJobIds={new Set<number>()} onGo={vi.fn()} onEmail={vi.fn()} onFollowedUp={vi.fn()} onReschedule={vi.fn()} onStatusChange={vi.fn()}/>)).toContain('Nordlicht Systeme GmbH')
    expect(renderToStaticMarkup(<FeedbackDuePaneHeader showOverdue showUpcoming loading={false} error={pane.state.error} onShowOverdue={vi.fn()} onShowUpcoming={vi.fn()}/>)).not.toContain('role="alert"')
  })

  it('claims the pane is empty only when the server actually returned zero rows',async()=>{
    const empty=paneState(staleRows)
    expect(await refreshFeedbackDueRows(empty.setRows,empty.setError,vi.fn().mockResolvedValue([]))).toBe(true)
    expect(feedbackDueEmptyMessage(false,empty.state.error,empty.state.rows.length,0)).toBe('No actionable job has a feedback deadline right now.')

    const failed=paneState(staleRows)
    expect(await refreshFeedbackDueRows(failed.setRows,failed.setError,vi.fn().mockRejectedValue(new Error('synthetic network failure')))).toBe(false)
    expect(feedbackDueEmptyMessage(false,failed.state.error,0,0)).toBeNull()
    expect(feedbackDueEmptyMessage(false,failed.state.error,failed.state.rows.length,0)).toBeNull()
  })

  it('keeps the two honest sentences apart and says nothing while loading',()=>{
    expect(feedbackDueEmptyMessage(true,null,0,0)).toBeNull()
    expect(feedbackDueEmptyMessage(false,null,3,0)).toBe('Those deadline groups are hidden.')
    expect(feedbackDueEmptyMessage(false,null,3,3)).toBeNull()
  })
})
