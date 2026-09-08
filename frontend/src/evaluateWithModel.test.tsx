// TASK-220. The in-app evaluation writes fit_score, priority and recommendation - the three fields
// the board sorts on - so the whole feature rests on the owner being able to tell, without doubt,
// whether what is on screen has been saved yet. That distinction is wording, not logic: it cannot
// fail a typecheck and it cannot fail the backend's own tests. It is pinned here instead.
//
// Rendered with react-dom/server, the same way stallPanel.test.tsx does it: this vitest run has no
// DOM (no jsdom, no @testing-library) and TASK-177 forbids adding one. Reading the emitted markup is
// enough to assert which branch was taken; it cannot press the confirm button, so the two-request
// dry-run-then-commit flow itself is measured in the browser.
import {describe,expect,it} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {EvaluateWithModelOutcome} from './App'
import type {EvaluateWithModelPreviewRow,EvaluateWithModelResult} from './types'

const row=(over:Partial<EvaluateWithModelPreviewRow>={}):EvaluateWithModelPreviewRow=>({job_id:1,company:'Acme GmbH',title:'Backend Engineer',fit_score:78,priority:'high',recommendation:'apply',action:'create',replaces_fit_score:null,...over})
const result=(over:Partial<EvaluateWithModelResult>={}):EvaluateWithModelResult=>({ok:true,dry_run:true,created:0,errors:[],preview:[row()],...over})
// `error` is what api() throws for a 400 - the raw {ok:false,errors,detail} body, not a rewrapped one.
const render=(result:EvaluateWithModelResult|null,error?:any)=>renderToStaticMarkup(<EvaluateWithModelOutcome result={result} error={error}/>)

describe('EvaluateWithModelOutcome preview table',()=>{
  it('names a new evaluation and a replacement differently, with the score being replaced',()=>{
    const html=render(result({preview:[
      row({job_id:1,company:'Acme GmbH',title:'Backend Engineer',fit_score:78,action:'create',replaces_fit_score:null}),
      row({job_id:2,company:'Globex AG',title:'Platform Engineer',fit_score:64,priority:'medium',recommendation:'maybe',action:'replace',replaces_fit_score:41}),
    ]}))
    expect(html).toContain('Acme GmbH')
    expect(html).toContain('Globex AG')
    expect(html).toContain('New evaluation')
    expect(html).toContain('Replaces current fit 41')
    // The replaced score belongs to the row that is being overwritten, not to the new one.
    expect(html).not.toContain('Replaces current fit 64')
    expect(html).toContain('78')
    expect(html).toContain('maybe')
  })

  // A replace row whose previous score the server could not report must say so in words. `?? 0`
  // here would claim the board currently holds a fit of 0 for that job, which is a different and
  // false statement - the same defect StallPanel is guarded against in stallPanel.test.tsx.
  it('does not invent a replaced score it was not given',()=>{
    const html=render(result({preview:[row({action:'replace',replaces_fit_score:null})]}))
    expect(html).toContain('Replaces the current evaluation')
    expect(html).not.toContain('Replaces current fit 0')
  })

  it('explains an empty answer in words instead of rendering an empty table',()=>{
    const html=render(result({preview:[]}))
    expect(html).toContain('nothing to save')
    expect(html).toContain('The model answered without an evaluation')
    expect(html).not.toContain('<table')
  })

  it('gives every column a scoped header',()=>{
    const html=render(result())
    expect(html).toContain('<th scope="col"')
    expect(html).toContain('<th scope="row"')
    expect(html).not.toContain('<th class')  // no unscoped header cell
  })
})

describe('EvaluateWithModelOutcome says whether anything was written',()=>{
  it('states that nothing has been saved yet while the result is a dry run',()=>{
    const html=render(result({dry_run:true,created:0}))
    expect(html).toContain('nothing has been saved yet')
    expect(html).toContain('Nothing changes until you press Save')
    expect(html).toContain('What would happen')
    expect(html).not.toContain('Saved to the board')
  })

  it('says what was written once the commit came back, and stops saying nothing was',()=>{
    const html=render(result({dry_run:false,created:2}))
    expect(html).toContain('Saved to the board')
    expect(html).toContain('2 evaluations written')
    expect(html).toContain('What happened')
    expect(html).not.toContain('nothing has been saved yet')
  })

  it('reports jobs the server skipped alongside the ones it previewed',()=>{
    const html=render(result({errors:['Job 9 has no description to evaluate.']}))
    expect(html).toContain('Job 9 has no description to evaluate.')
    expect(html).toContain('Some selected jobs were skipped')
  })

  it('renders nothing at all before the first request',()=>{
    expect(render(null)).toBe('')
  })
})

describe('EvaluateWithModelOutcome provider failure',()=>{
  // The 400 body carries both: `errors` is the app's summary, `detail` is the provider's own stderr.
  // Collapsing either into a generic message is what makes a failed local model unfixable.
  it('renders every error string and the provider detail underneath',()=>{
    const html=render(null,{ok:false,errors:['The model did not return valid JSON.','Job 3 was left unevaluated.'],detail:'ollama: model "llama3" not found, try pulling it first'})
    expect(html).toContain('The model did not return valid JSON.')
    expect(html).toContain('Job 3 was left unevaluated.')
    expect(html).toContain('What the model actually returned')
    expect(html).toContain('not found, try pulling it first')
    expect(html).toContain('nothing has been saved')
  })

  it('does not print the detail twice when it is the only thing the server said',()=>{
    const html=render(null,{detail:'Provider timed out after 180s'})
    expect(html.match(/Provider timed out after 180s/g)).toHaveLength(1)
  })

  it('keeps the preview visible after a failed save, still marked as unsaved',()=>{
    const html=render(result({dry_run:true}),{ok:false,errors:['The provider exited with code 1.'],detail:''})
    expect(html).toContain('The provider exited with code 1.')
    expect(html).toContain('Acme GmbH')
    expect(html).toContain('nothing has been saved yet')
    expect(html).not.toContain('Saved to the board')
  })
})
