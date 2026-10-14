// TASK-294: per-job notes inside an email decision are collapsed behind "Notes (n)" by default; the
// feedback-deadline popup opts back into the old always-open view with initialNotesOpen.
import {describe,expect,it,vi} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {JobMailboxConversationCard} from './App'
import type {JobMailboxPayload} from './types'

const mailbox={messages:[],notes:[{id:1,job:7,note:'Asked for salary range',note_type:'general',created_by:null,created_at:'2026-10-01T10:00:00Z'},{id:2,job:7,note:'Second round with CTO',note_type:'interview',created_by:null,created_at:'2026-10-02T10:00:00Z'}]} as JobMailboxPayload
const card=(open?:boolean)=>renderToStaticMarkup(<JobMailboxConversationCard jobId={7} company="Synthetic GmbH" title="Backend Engineer" suggestions={[]} onDecided={vi.fn()} initialMailbox={mailbox} initialNotesOpen={open}/>)

describe('TASK-294 email decision notes',()=>{
  it('collapses notes behind Notes (n) by default, same notes inside',()=>{
    const html=card()
    expect(html).toMatch(/<details class="mt-3"><summary[^>]*>Notes \(2\)<\/summary>/)
    expect(html).toContain('Asked for salary range')
    expect(html).toContain('Second round with CTO')
  })
  it('keeps them open where the caller asks (feedback-deadline popup)',()=>{
    expect(card(true)).toMatch(/<details class="mt-3" open="">/)
  })
})
