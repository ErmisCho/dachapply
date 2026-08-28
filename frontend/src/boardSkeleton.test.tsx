// TASK-188 AC7/AC9. The skeleton's whole promise is that swapping it for real rows moves nothing,
// and it keeps that promise structurally: it renders INSIDE the board's own wrapper, table, thead
// and tbody, so there is no second copy of the column layout to drift. What a test can still hold
// is the one number that copy-free arrangement depends on -- the cell count per row.
//
// Rendered with react-dom/server, the same way appPanels.test.tsx and mailboxCollapse.test.tsx do:
// this vitest run has no DOM (no jsdom, no @testing-library) and TASK-177 forbids adding one. So
// the geometry claims AC8 and AC9 actually make -- "does not appear before 250 ms", "stays 450 ms",
// "first-row top is equal in both states" -- are measured in a browser and are not simulated here.
import {describe,expect,it} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {SkeletonCards,SkeletonStatus,SkeletonTableRows,SKELETON_ROWS,SKELETON_TABLE_COLS} from './App'

const tableHtml=()=>renderToStaticMarkup(<table><tbody><SkeletonTableRows/></tbody></table>)

describe('board skeleton (TASK-188 AC7)',()=>{
  // index.css hides board columns with `.hide-col-* td:nth-child(N)` and pins each column's width
  // the same way, so a row that collapsed its cells into one colSpan would both misalign against
  // the header and silently defeat the owner's hidden-column choices.
  it('gives every skeleton row one cell per real board column',()=>{
    const html=tableHtml()
    expect(SKELETON_TABLE_COLS).toBe(12)
    expect(html.match(/<tr/g)).toHaveLength(SKELETON_ROWS)
    expect(html.match(/<td/g)).toHaveLength(SKELETON_ROWS*SKELETON_TABLE_COLS)
    expect(html).not.toContain('colspan')
  })

  // Same td padding and same row border as a real board row, so the skeleton's height comes from
  // the real row's box model rather than from a pixel value that has to be kept in sync with it.
  it('reuses the real row and cell classes rather than restating them',()=>{
    const html=tableHtml()
    expect(html).toContain('class="border-t align-top"')
    expect(html).toContain('class="px-1.5 py-1"')
  })

  it('renders placeholders for the 360px card layout too, not only the desktop table',()=>{
    // TASK-147 mounts exactly one of the two layouts, so a table-only skeleton would leave the
    // narrow board with nothing at all while it waits.
    const html=renderToStaticMarkup(<div><SkeletonCards/></div>)
    expect(html.match(/<article/g)).toHaveLength(SKELETON_ROWS)
    expect(html).toContain('dashboard-mobile-card')
  })

  // The bars are decoration; the fact that the board is loading is announced once, as text.
  it('hides the placeholder bars from assistive tech and announces the wait in words',()=>{
    expect(tableHtml().match(/aria-hidden="true"/g)).toHaveLength(SKELETON_ROWS)
    expect(renderToStaticMarkup(<SkeletonStatus/>)).toContain('role="status"')
    expect(renderToStaticMarkup(<SkeletonStatus/>)).toContain('sr-only')
  })

  // A skeleton that pulses through a reduced-motion preference is worse than a still one.
  it('stops the pulse for prefers-reduced-motion',()=>{
    expect(tableHtml()).toContain('motion-reduce:animate-none')
  })
})
