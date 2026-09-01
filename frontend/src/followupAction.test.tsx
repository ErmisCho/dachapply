import {describe,expect,it,vi} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {MemoryRouter} from 'react-router-dom'
import {confirmFollowUpSent,hasUpcomingInterview,JobFollowUpContext,JobFollowUps} from './App'
import type {Job,JobMailboxPayload,MailboxDraft} from './types'

const job={id:42,company:'Acme',title:'Engineer',status:'interview'} as Job
const draft:MailboxDraft={id:9,status:'written',block_reason:'',subject:'Re: Interview',body_text:'Exact prepared reply\nSecond line',evaluator:'template',gmail_draft_id:'draft-9',gmail_message_id:'message-9',gmail_thread_id:'thread-9',gmail_url:'https://mail.google.com/mail/u/0/?authuser=owner%40example.test#drafts?compose=message-9',sent_at:null,stale_reason:'',chat_history:[],created_at:'2026-08-28T10:00:00Z'}
const mailbox={messages:[{id:7,sender:'Recruiter <hr@acme.test>',subject:'Interview update',body_text:'Can you meet?',received_at:'2026-08-28T09:00:00Z',classification:'recruiter_reply',matched_job:42,matched_job_company:'Acme',matched_job_title:'Engineer',draft,thread_id:'thread-9',gmail_url:null,sent_by_owner:false,created_at:'2026-08-28T09:00:00Z',calendar_summary:'',calendar_location:'',calendar_organizer:'',calendar_start:null,calendar_end:null,attachments:[]}],notes:[{id:3,job:42,note:'Waiting for final feedback',note_type:'general',created_by:1,created_at:'2026-08-27T10:00:00Z'}]} as unknown as JobMailboxPayload

describe('actionable follow-up context (TASK-113)',()=>{
  it('shows status, matched-message context, notes, verbatim draft, and exact Gmail link together',()=>{
    const html=renderToStaticMarkup(<JobFollowUpContext job={job} mailbox={mailbox}/>)
    expect(html).toContain('Job status:')
    expect(html).toContain('interview')
    expect(html).toContain('Interview update')
    expect(html).toContain('Recruiter reply')
    expect(html).toContain('Waiting for final feedback')
    expect(html).toContain('Exact prepared reply\nSecond line')
    expect(html).toContain('#drafts?compose=message-9')
  })

  it('patches the job with the exact draft and optional next date',async()=>{
    const request=vi.fn().mockResolvedValue({followup:{id:5},next_followup:null})
    await confirmFollowUpSent(5,9,'2026-09-10',7,request)
    expect(request).toHaveBeenCalledWith('/jobs/5/confirm-follow-up-sent/',{method:'PATCH',body:{draft_id:9,next_follow_up_date:'2026-09-10',followup_id:7}})
  })

  it('offers the sent action for feedback overdue even without a FollowUp row',()=>{
    const overdue={...job,feedback_due_date:'2000-01-01'}
    const html=renderToStaticMarkup(<MemoryRouter><JobFollowUps job={overdue} mailbox={mailbox}/></MemoryRouter>)
    expect(html).toContain('Expected feedback is overdue.')
    expect(html).toContain('I sent this Gmail draft')
  })

  it('pauses the sent action while an interview is strictly upcoming',()=>{
    const now=Date.parse('2026-09-03T09:00:00Z')
    expect(hasUpcomingInterview({interview_at:'2026-09-03T10:00:00Z'},now)).toBe(true)
    expect(hasUpcomingInterview({interview_at:'2026-09-03T09:00:00Z'},now)).toBe(false)
    expect(hasUpcomingInterview({interview_at:'2026-09-03T08:59:59Z'},now)).toBe(false)
    expect(hasUpcomingInterview({interview_at:null},now)).toBe(false)

    const upcoming={...job,feedback_due_date:'2000-01-01',interview_at:'2999-09-03T10:00:00Z'}
    const html=renderToStaticMarkup(<MemoryRouter><JobFollowUps job={upcoming} mailbox={mailbox}/></MemoryRouter>)
    expect(html).toContain('Follow-up paused')
    expect(html).toContain('Set a new feedback date after the interview')
    expect(html).not.toContain('I sent this Gmail draft')
  })

  it('explains a blocked draft and renders no Gmail action',()=>{
    const blocked:MailboxDraft={...draft,status:'blocked',block_reason:'salary below configured floor',gmail_url:null}
    const payload={...mailbox,messages:[{...mailbox.messages[0],draft:blocked}]}
    const html=renderToStaticMarkup(<JobFollowUpContext job={job} mailbox={payload}/>)
    expect(html).toContain('Reply not drafted: salary below configured floor')
    expect(html).not.toContain('Open exact Gmail draft')
  })
})
