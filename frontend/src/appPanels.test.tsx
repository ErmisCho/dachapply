// TASK-181 AC1: the per-panel `⋮` Panel options button and the hover-only cluster behind it are both
// gone from every panel. The authoritative count is done in a browser against the real board; this is
// the CI guard that stops either coming back, since a returning `⋮` would silently restore the very
// button the owner asked to be removed.
//
// Rendered with react-dom/server, the same way mailboxCollapse.test.tsx does it: this vitest run has
// no DOM (no jsdom, no @testing-library) and TASK-177 forbids adding one. That is enough to count
// buttons in markup; it cannot start a drag, so the reorder/hide gestures are measured in the browser
// and the ordering rules they call into are unit-tested in appUtils.test.ts.
import {describe,expect,it} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {DashboardPanel,DraftReplyBlock} from './App'
import type {MailboxDraft} from './types'

const noop=()=>{}
function render(drag:{held?:boolean;landing?:boolean}={}){
  return renderToStaticMarkup(
    <DashboardPanel id="total" onDragStart={noop} onDrop={noop} onDragOver={noop} onDragEnd={noop} {...drag}>
      <div className="mailbox-selectable">panel body</div>
    </DashboardPanel>
  )
}

describe('DashboardPanel chrome (TASK-181 AC1)',()=>{
  it('renders no buttons of its own at all',()=>{
    expect(render().match(/<button/g)).toBeNull()
  })

  it('renders neither the menu trigger nor its three actions',()=>{
    const html=render()
    for(const gone of ['⋮','Panel options','Move left','Move right','Hide panel'])expect(html).not.toContain(gone)
  })

  // TASK-102's defect was that these were display:none and so unreachable by keyboard or touch. The
  // fix is not to hide them better - it is that they are not here at all any more.
  it('renders no hover-only cluster',()=>{
    expect(render()).not.toContain('group-hover')
  })

  // TASK-134's guard lives on this element: the panel is draggable, and its mousedown handler turns
  // that off over .mailbox-selectable so message text still selects. The handler cannot be seen in
  // static markup, but if `draggable` ever stops being rendered here the guard is guarding nothing.
  it('is still the draggable element, tagged with its panel id',()=>{
    const html=render()
    expect(html).toContain('draggable="true"')
    expect(html).toContain('data-panel="total"')
  })
})

// TASK-183. The drag feedback TASK-181 shipped without. The gestures themselves are measured in a
// browser; what is pinned here is the part a DOM-less run can still police - that a panel shows the
// "will land here" signal ONLY when the drag actually moves it, which is AC5's "does not falsely
// signal a move", and that none of it leaks into a panel sitting still.
describe('DashboardPanel drag feedback (TASK-183 AC1/AC5/AC6)',()=>{
  it('shows nothing at all when no drag is in flight',()=>{
    const html=render()
    expect(html).not.toContain('Drops here')
    expect(html).not.toContain('outline-blue-500')
    expect(html).not.toContain('opacity-60')
  })

  // AC6: the owner has to be able to see which panel they are holding once the board starts moving
  // around it. AC5: being held is NOT the same claim as being about to move, so the destination
  // marker stays off - this is the drag that lands the panel back where it started.
  it('dims the panel being held without promising a move',()=>{
    const html=render({held:true})
    expect(html).toContain('opacity-60')
    expect(html).not.toContain('Drops here')
    expect(html).not.toContain('outline-blue-500')
  })

  it('marks the slot the panel will land in when the drop would move it',()=>{
    const html=render({held:true,landing:true})
    expect(html).toContain('Drops here')
    expect(html).toContain('outline-blue-500')
  })

  // TASK-181 AC1 again, now that the panel renders chrome of its own: the destination badge is a
  // span. A button here would put back the very control the owner asked to have removed.
  it('adds no button while doing it',()=>{
    expect(render({held:true,landing:true}).match(/<button/g)).toBeNull()
  })
})

const mailboxDraft:MailboxDraft={id:1,status:'written',block_reason:'',subject:'Re: Update',body_text:'Current prepared response',evaluator:'template',gmail_draft_id:'draft-1',gmail_message_id:'message-1',gmail_thread_id:'thread-1',gmail_url:'https://mail.google.test/#drafts?compose=message-1',sent_at:null,stale_reason:'',chat_history:[],created_at:'2026-08-31T08:00:00Z'}

describe('stale mailbox draft presentation (TASK-206)',()=>{
  it('replaces stale body and editing actions with a non-destructive notice',()=>{
    const html=renderToStaticMarkup(<DraftReplyBlock draft={{...mailboxDraft,body_text:'Contradictory stale response',stale_reason:'you already replied later in this conversation'}}/>)
    expect(html).toContain('Draft no longer applicable')
    expect(html).toContain('you already replied later in this conversation')
    expect(html).toContain('existing Gmail draft was not changed')
    expect(html).toContain('Open stale Gmail draft')
    expect(html).not.toContain('Contradictory stale response')
    expect(html).not.toContain('Chat to revise')
  })

  it('keeps a current draft available',()=>{
    const html=renderToStaticMarkup(<DraftReplyBlock draft={mailboxDraft}/>)
    expect(html).toContain('Current prepared response')
    expect(html).toContain('Chat to revise')
    expect(html).not.toContain('Draft no longer applicable')
  })
})
