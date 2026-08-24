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
import {DashboardPanel} from './App'

const noop=()=>{}
function render(){
  return renderToStaticMarkup(
    <DashboardPanel id="total" onDragStart={noop} onDrop={noop} onDragOver={noop} onDragEnd={noop}>
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
