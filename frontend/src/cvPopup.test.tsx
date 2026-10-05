// This vitest run has no DOM (no jsdom, no @testing-library) and TASK-177 forbids adding one, so
// these read the emitted markup. Effects never run here, which means `preview` stays null and the
// loaded controls are not renderable in a test at all -- the popup's contents, its rendered size and
// the Applied write are measured in the browser instead, and the numbers live in the task notes.
import {describe,expect,it,vi} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {CvGenerator,LearnedPreferenceNote,feedbackStatusPatch} from './App'
import appSource from './App.tsx?raw'   // vite serves the file's text; no DOM and no new dependency
import type {Job} from './types'
import {replacementPrompt} from './cvModel'

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

  it('sizes to its content up to the viewport, with only a stable minimum (TASK-266)',()=>{
    // TASK-216 pinned a fixed height so `preview` arriving could not resize the box. TASK-266's owner
    // instruction overrides that ("there is no reason for this popup to need a scrollbar, it can
    // expand"): a 56rem cap scrolled at 1063px of content in a 1642px-tall window. Only a minimum
    // stays, so the loading state does not collapse; the popup scrolls only past the viewport.
    const html=popup()

    expect(html).toContain('min-h-[min(36rem,calc(100dvh-1.5rem))]')
    expect(html).toContain('max-h-[calc(100dvh-1.5rem)]')
    expect(html).not.toMatch(/ h-\[/)          // no fixed height of any kind
    expect(html).not.toContain('56rem')
  })

  it('is width-derived from the viewport, pinned on screen, and never scrolls sideways (TASK-266)',()=>{
    const html=popup()

    expect(html).toContain('w-[min(64rem,calc(100vw-1.5rem))]')
    expect(html).not.toContain('w-[48rem]')
    // fixed + inset-x-0 + mx-auto centres it in the viewport, so it cannot run off the right edge
    // the way `absolute left-0` under the toolbar button could on a 1024px window.
    expect(html).toMatch(/class="fixed inset-x-0 top-3 [^"]*mx-auto/)
    expect(html).toContain('overflow-y-auto')    // the single scroll area, only when content is taller
    expect(html).toContain('overflow-x-hidden')
    expect(html).toContain('[overflow-wrap:anywhere]')   // long generated-file paths wrap instead
  })

  it('keeps Applied on the Generate row and lets the job text grow with the window (TASK-266)',()=>{
    // The loaded controls never render here (no effects), so these read the source.
    expect(appSource).toContain('<div className="flex flex-nowrap items-center gap-2" data-cv-action-row><ProgressButton active={loading} task={task} label="Generate"')
    // The dialog is a flex column bounded by its max-h; the job-text section takes whatever height is
    // left and the textarea scrolls inside it, so no rem budget for the rest of the popup is guessed.
    expect(popup()).toMatch(/class="fixed inset-x-0 top-3 z-\[var\(--z-popup\)\] mx-auto flex flex-col /)
    expect(appSource).toContain("'mt-2 grid min-h-0 flex-auto items-start gap-2 lg:grid-cols-2'")
    expect(appSource).toContain("'lg:col-span-2 flex min-h-0 flex-col self-stretch [&>div]:flex [&>div]:min-h-0 [&>div]:flex-auto [&>div]:flex-col")
    expect(appSource).toContain('[&_textarea]:min-h-[6rem] [&_textarea]:flex-auto [&_textarea]:[field-sizing:content]')
    expect(appSource).not.toContain('100dvh-30rem')
  })
})

describe('repeat generation and reopened files (TASK-252, TASK-253)',()=>{
  it('asks the server first and confirms only on its existing-files 409 (TASK-259)',()=>{
    const generate=appSource.split('async function generate(){')[1].split('async function cancelTask(){')[0]

    // Unconfirmed first; the 409's field, not its text, picks the prompt; declining sends nothing more.
    expect(generate).toContain('started=await run(false)')
    expect(generate).toContain('if(!e?.existing_files)throw e;if(!window.confirm(replacementPrompt(e))){setTask(previous);return}started=await run(true)')
    expect(generate).not.toContain('e.detail')
  })

  it('bulk generation also asks the server first and confirms each job from its own 409 (TASK-259)',()=>{
    const generate=appSource.split('async function generate(){')[2].split('async function readjust(')[0]

    // No client-side pre-check, so no shared "Recreate them" prompt that cannot tell sent documents apart.
    expect(generate).not.toContain('Recreate them')
    expect(generate).toContain('started=await run(false)')
    expect(generate).toContain('if(!e?.existing_files)throw e;if(!window.confirm(`${row.job.company} — ${displayJobTitle(row.job.title)}: ${replacementPrompt(e)}`)){update(row.job.id,row);return}started=await run(true)')
    expect(generate).not.toContain('e.detail')
  })

  it('words the prompt from sent_documents: new copies for sent documents, recreate otherwise (TASK-259)',()=>{
    const message='Generated files already exist for this job. Confirm replacement before generating.'
    expect(replacementPrompt({existing_files:true,sent_documents:false,detail:message})).toBe('Generated files already exist for this job. Recreate them with the selected settings?')
    expect(replacementPrompt({existing_files:true,detail:message})).toBe('Generated files already exist for this job. Recreate them with the selected settings?')
    const sent=replacementPrompt({existing_files:true,sent_documents:true,detail:message})
    expect(sent).toContain('new copies')
    expect(sent).toContain('sent documents stay unchanged')
    expect(sent).not.toMatch(/replac|recreate/i)
  })

  it('enables the adjustment copy action from persisted preview content',()=>{
    expect(appSource).toContain('const clipboardTex=cvClipboardTex(task,preview)')
    expect(appSource).toContain('disabled={loading||revisionLoading||compileLoading||!clipboardTex}')
    expect(appSource).toContain('if(tex&&await copyToClipboard(tex))')
  })
})

describe('editable generation job context (TASK-253)',()=>{
  it('flags an unknown company and exposes one save action for company and job text',()=>{
    expect(appSource).toContain('Unknown company — correct it before generating.')
    expect(appSource).toContain('aria-label="Company for generated documents"')
    expect(appSource).toContain('aria-label="Current accepted job text"')
    expect(appSource).toContain('async function saveGenerationJob(text=sourceText)')
    expect(appSource).toContain('saveLabel="Save company and job text"')
    expect(appSource.split('Save company and job text').length-1).toBe(1)
    expect(appSource).toContain("body:{company,original_source_text:text}")
  })

  it('does not allow generation from unsaved edited values',()=>{
    expect(appSource).toContain('||jobDirty||jobSaving||!!pendingText||genInvalid')
    expect(appSource).toContain('||isUnknownCompany(company)||!sourceText.trim()')
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
