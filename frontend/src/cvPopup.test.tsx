// This vitest run has no DOM (no jsdom, no @testing-library) and TASK-177 forbids adding one, so
// these read the emitted markup. Effects never run here, which means `preview` stays null and the
// loaded controls are not renderable in a test at all -- the popup's contents, its rendered size and
// the Applied write are measured in the browser instead, and the numbers live in the task notes.
import {describe,expect,it,vi} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {CvGenerator,feedbackStatusPatch} from './App'
import type {Job} from './types'

const storage={getItem:vi.fn(()=>JSON.stringify({can_generate_cv:true})),removeItem:vi.fn()}
vi.stubGlobal('localStorage',storage)

const popup=(job:Partial<Job>={})=>renderToStaticMarkup(<CvGenerator compact job={{id:216,...job} as Job} onClose={()=>{}}/>)

describe('compact CV generator popup (TASK-216)',()=>{
  it('opens at its final height with loading, close, and dialog semantics already present',()=>{
    const html=popup()

    expect(html).toContain('role="dialog"')
    expect(html).toContain('aria-label="Generate CV and Motivation Letter"')
    expect(html).toContain('tabindex="-1"')
    expect(html).toContain('Loading generator options…')
    expect(html).toContain('aria-label="Close"')   // TASK-234: the word became a glyph, the name stayed
    expect(html).toContain('title="Close"')        // ...and an icon-only control also needs the tooltip
    expect(html).not.toContain('Adjust latest')
  })

  it('still commits to a FIXED height, so slow provider discovery cannot resize it',()=>{
    // TASK-216 AC1/AC2 are the reason a height is pinned at all: the popup must reach its final size
    // on the first render. TASK-228 made that size smaller, it did not make it content-dependent --
    // a `max-h` alone would let the box grow when `preview` arrives, which is exactly the jump
    // TASK-216 removed. This is the test that stops the two tasks undoing each other.
    const html=popup()

    expect(html).toMatch(/class="[^"]*\bh-\[\d+rem\]/)   // a fixed height, not only a ceiling
    expect(html).toMatch(/max-h-\[\d+vh\]/)                 // ...capped, so a short viewport still fits.
    // The exact vh is a calibration number, not the contract: TASK-233 moved it from 85 to 92 to fit
    // the fully-open state on a laptop. What must not regress is that a cap EXISTS beside the fixed
    // height, so pin the shape and let the number be tuned by measurement.
    expect(html).not.toContain('h-[80vh]')               // the old viewport-proportional height
  })

  it('trades width for height, and still fits a 360px screen',()=>{
    // TASK-228 made it 608x800 to stop it filling the screen. TASK-233 has to fit the FULLY OPEN
    // state into 85vh of a 744px laptop viewport (~632px) while TASK-230 adds a second model picker,
    // and a single column cannot do that: the body is two independent columns at lg and up -- the
    // same 1024px line where index.css stops forcing 44px touch targets -- so the box goes wider and
    // much shorter. max-w keeps the 360px case, where lg never matches and the columns stack again.
    const html=popup()

    expect(html).toContain('w-[48rem]')
    expect(html).toContain('max-w-[calc(100vw-2rem)]')
    expect(html).toContain('overflow-y-auto')   // AC2: scrolling stays as the safety net
  })
})

describe('marking a job Applied from the generator (TASK-227)',()=>{
  it('sends exactly the body the board sends for the same transition',()=>{
    // AC2. The window must not become a second way to write a status: the board builds this same
    // body (see bulkApply), and if the two ever disagree one of them starts writing a job that the
    // other would have written differently. Sharing feedbackStatusPatch is what prevents that, and
    // this pins the shape rather than trusting the sharing to stay in place.
    const body=feedbackStatusPatch('applied','2026-09-10')

    expect(body).toEqual({status:'applied',status_date:'2026-09-10',last_update_date:'2026-09-10',
                          interview_stage:null,interview_total:null})
  })

  it('does not stamp an interview stage onto an application',()=>{
    // The same helper serves 'interview', which DOES carry a stage. Applied must clear it, or a job
    // moved interview -> applied would keep a stage it is no longer in.
    expect(feedbackStatusPatch('interview','2026-09-10').interview_stage).toBe(1)
    expect(feedbackStatusPatch('applied','2026-09-10').interview_stage).toBeNull()
  })
})
