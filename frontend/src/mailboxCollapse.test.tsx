// TASK-177: the owner's "I don't see my own emails in the conversation threads now" report. The
// messages were there; a collapsed MailboxConversationMessage (App.tsx) rendered its header row and
// nothing else, so 14 rows of a 15-row thread were empty and the only cue was a one-character '▸'.
//
// Rendered with react-dom/server - already a dependency - because this repo's vitest run has no DOM
// (no jsdom, no @testing-library, and TASK-177 forbids adding one). That covers both render branches
// of the collapse and the two AC4 counts that can be counted from markup; it cannot dispatch a
// click, so the toggle itself is checked in the browser, not here.
import {describe,expect,it} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {MailboxThreadGroup} from './App'
import type {MailboxMessage} from './types'

// Shaped after the thread the task measured in production (/api/jobs/462/mailbox/: 15 messages, 6 of
// them the owner's, bodies of 740 and 909 characters). Not a copy of it - that endpoint needs the
// owner's session cookie, which this test does not have.
function msg(i:number,own:boolean,bodyLen:number,extra:Partial<MailboxMessage>={}):MailboxMessage{
  const at=new Date(Date.UTC(2025,8,16,8+i)).toISOString()
  return {id:i,sender:own?'me@example.com':'Recruiter <recruiter@ontec.at>',subject:'Your application',
    // A leading blank line and a greeting on its own line: the real shape of mail bodies, and the
    // reason the preview squeezes whitespace instead of slicing the raw text.
    body_text:bodyLen?('\n\nSehr geehrte Damen und Herren,\n\n'+'x'.repeat(Math.max(1,bodyLen-34))):'',
    received_at:at,classification:'other',matched_job:462,matched_job_company:'ONTEC AG',
    matched_job_title:'Data Engineer',draft:null,thread_id:'t-462',gmail_url:null,sent_by_owner:own,
    created_at:at,calendar_summary:'',calendar_location:'',calendar_organizer:'',calendar_start:null,
    calendar_end:null,attachments:[],...extra}
}
const OWN_POSITIONS=[2,4,6,9,11,14]
const thread=Array.from({length:15},(_,i)=>msg(i+1,OWN_POSITIONS.includes(i+1),i%2?909:740))

function counts(messages:MailboxMessage[]){
  const html=renderToStaticMarkup(<MailboxThreadGroup messages={messages}/>)
  const rows=html.split('<li ').slice(1)
  const own=rows.filter(r=>r.includes('justify-end'))
  const withBody=(r:string)=>r.includes('id="mailbox-msg-body-')
  return {html,
    rows:rows.length,                                  // AC4: message rows rendered
    rowsWithBody:rows.filter(withBody).length,         // AC4: rows that render a body (preview or full)
    ownRows:own.length,
    ownRowsWithBody:own.filter(withBody).length,
    fullBodies:(html.match(/whitespace-pre-wrap/g)||[]).length,  // the expanded bubble's own class
    // TASK-177 360px fix: the WORD is `hidden sm:inline` so a narrow viewport falls back to the
    // original glyph rather than overflowing the header row (measured: the word widened an
    // already-overflowing row from 15px to 45px at 360px). Word and glyph are therefore separate
    // nodes, and each is counted on its own instead of as one contiguous string.
    collapsedCues:(html.match(/Show <\/span>▸/g)||[]).length,
    expandedCues:(html.match(/Hide <\/span>▾/g)||[]).length,
    wordsHiddenOnNarrow:(html.match(/hidden sm:inline/g)||[]).length}
}

describe('TASK-177 a collapsed conversation message',()=>{
  it('renders a body line on every row, not only on the expanded one',()=>{
    const c=counts(thread)
    // Before this change these were rows:15, rowsWithBody:1, ownRowsWithBody:0.
    expect(c.rows).toBe(15)
    expect(c.rowsWithBody).toBe(15)
    expect(c.ownRowsWithBody).toBe(6)
    // AC9/Implementation Notes: collapse still EXISTS - exactly one full body, 14 one-line previews.
    expect(c.fullBodies).toBe(1)
  })

  it('labels its state in words, not in a single glyph',()=>{
    const c=counts(thread)
    expect(c.collapsedCues).toBe(14)
    expect(c.expandedCues).toBe(1)
    // every one of the 15 headers carries the word, and every word is the narrow-screen-hidden one
    expect(c.wordsHiddenOnNarrow).toBe(15)
    // The controlled region exists in BOTH states, so aria-controls never dangles.
    expect((c.html.match(/aria-expanded="false"/g)||[]).length).toBe(14)
  })

  it('truncates the preview instead of rendering the whole 909-character body',()=>{
    const c=counts(thread)
    const collapsed=c.html.split('<li ')[1]     // position 1 of 15 - collapsed
    expect(collapsed).toContain('Sehr geehrte Damen und Herren, xxx')
    expect(collapsed).toContain('…')
    expect(collapsed.replace(/<[^>]*>/g,'').length).toBeLessThan(400)
  })

  it('defaults the same way for the owner and for the other side (AC3)',()=>{
    // Same thread, every sent_by_owner flipped: identical counts, so the default is positional
    // (position===total), never owner-keyed.
    const flipped=thread.map(m=>({...m,sent_by_owner:!m.sent_by_owner}))
    const a=counts(thread),b=counts(flipped)
    expect([b.rows,b.rowsWithBody,b.fullBodies]).toEqual([a.rows,a.rowsWithBody,a.fullBodies])
    expect(b.ownRowsWithBody).toBe(15-a.ownRows)   // the 9 flipped-to-own rows all render a body
  })

  it('says so when a collapsed message has an invitation or attachment but no text',()=>{
    const c=counts([msg(1,false,0,{calendar_summary:'Interview',calendar_start:'2025-09-20T09:00:00Z'}),
                    msg(2,false,740)])
    expect(c.rowsWithBody).toBe(2)
    expect(c.html).toContain('No message text')
  })
})
