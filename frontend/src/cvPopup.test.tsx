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
    expect(html).toContain('>Close</button>')
    expect(html).not.toContain('Detected language')
  })

  it('still commits to a FIXED height, so slow provider discovery cannot resize it',()=>{
    // TASK-216 AC1/AC2 are the reason a height is pinned at all: the popup must reach its final size
    // on the first render. TASK-228 made that size smaller, it did not make it content-dependent --
    // a `max-h` alone would let the box grow when `preview` arrives, which is exactly the jump
    // TASK-216 removed. This is the test that stops the two tasks undoing each other.
    const html=popup()

    expect(html).toMatch(/class="[^"]*\bh-\[\d+rem\]/)   // a fixed height, not only a ceiling
    expect(html).toContain('max-h-[85vh]')               // ...capped, so a short viewport still fits
    expect(html).not.toContain('h-[80vh]')               // the old viewport-proportional height
  })

  it('is narrower than it was, and still fits a 360px screen',()=>{
    // TASK-228 AC2/AC4. Measured in the browser, same job and state: 704x1459 -> 608x800.
    const html=popup()

    expect(html).toContain('w-[38rem]')
    expect(html).toContain('max-w-[calc(100vw-2rem)]')
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
