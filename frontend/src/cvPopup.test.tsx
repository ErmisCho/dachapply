// This vitest run has no DOM (no jsdom, no @testing-library) and TASK-177 forbids adding one, so
// these read the emitted markup. Effects never run here, which means `preview` stays null and the
// loaded controls are not renderable in a test at all -- the popup's contents, its rendered size and
// the Applied write are measured in the browser instead, and the numbers live in the task notes.
import {describe,expect,it,vi} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {CvGenerator,LearnedPreferenceNote,feedbackStatusPatch} from './App'
import appSource from './App.tsx?raw'   // vite serves the file's text; no DOM and no new dependency
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
describe('what the popups claim was learned (TASK-236 AC8)',()=>{
  // TASK-236 keeps STORING every readjustment - nothing is deleted and the field stays byte-identical
  // - but it stops long and truncated entries from reaching the CV prompt. So `learned_preference`
  // still comes back non-empty for an entry that will never be sent again, and the line both popups
  // used to render unconditionally ("learned for future applications") became false for it. The
  // backend now says which case it is in `learned_preference_exclusion`: '' means the entry reaches
  // the prompt, anything else is the reason it does not.
  //
  // Neither popup can be rendered with a finished task here: `task` and `rows` are filled by effects,
  // and renderToStaticMarkup runs none. That is why the line lives in one small exported component -
  // it is the only part of either popup a DOM-less test can actually render. Both surfaces are
  // asserted separately below rather than one standing in for the other, and the last test pins that
  // each popup really does route through it.
  const entry='- [CV] Prefer three-line role summaries'
  const excluded={learned_preference:entry,learned_preference_exclusion:'1,842 chars: a pasted brief, not a preference'}
  const kept={learned_preference:entry,learned_preference_exclusion:''}
  const note=(task:any,row=false)=>renderToStaticMarkup(<LearnedPreferenceNote task={task} row={row}/>)

  it('single popup: says the adjustment was used once, not learned, when it will not reach the prompt',()=>{
    const html=note(excluded)

    expect(html).toContain('Adjustment applied to this job only, not reused for future applications.')
    expect(html).not.toContain('Adjustment learned for future applications.')
    expect(html).toContain('status-message-info')   // informational, not a success tick
  })

  it('single popup: keeps the green affirmation exactly as it was for an entry that does reach it',()=>{
    const html=note(kept)

    expect(html).toContain('Adjustment learned for future applications.')
    expect(html).toContain('status-message-success')
    expect(html).not.toContain('not reused for future applications')
  })

  it('batch popup: says the same thing in the row shape, and does not claim it was learned',()=>{
    const html=note(excluded,true)

    expect(html).toContain('Adjustment applied to this job only, not reused for future applications.')
    expect(html).not.toContain('Adjustment learned for future applications.')
    expect(html).toContain('text-slate-500')
    expect(html).not.toContain('text-green-700')
  })

  it('batch popup: keeps its own green row line for an entry that does reach the prompt',()=>{
    const html=note(kept,true)

    expect(html).toContain('<div class="mt-1 text-xs text-green-700">Adjustment learned for future applications.</div>')
    expect(html).not.toContain('not reused for future applications')
  })

  it('says nothing at all when no preference was written',()=>{
    expect(note({learned_preference:'',learned_preference_exclusion:''})).toBe('')
    expect(note(null)).toBe('')
    expect(note(undefined,true)).toBe('')
  })

  it('is what BOTH popups render - neither keeps a copy of the claim of its own',()=>{
    // A repo memory: a fix verified on one surface gets assumed to cover the other. The four tests
    // above prove the component; this proves the single and the batch popup both go through it, and
    // that the old unconditional sentence survives nowhere else in the file.
    expect(appSource).toContain('<LearnedPreferenceNote task={task}/>')      // single popup
    expect(appSource).toContain('<LearnedPreferenceNote task={row} row/>')   // batch popup, per row
    // Both remaining copies of the old sentence are the two branches inside the component itself
    // (single popup and batch row); a third would mean a popup grew its own unconditional claim again.
    expect(appSource.split('Adjustment learned for future applications.').length-1).toBe(2)
  })
})
