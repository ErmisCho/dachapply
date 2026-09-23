// TASK-246. Same constraint as postingSource.test.tsx: this vitest run has no DOM (no jsdom, no
// @testing-library, TASK-177 forbids adding one) and effects never run, so nothing that only appears
// after a fetch resolves can be rendered here. ImportPaste is what makes the round trip testable:
// the paste box and its control render from the first paint, and the two things that only appear
// after the POST - the result summary and the error/duplicate path - are their own pure components
// that take the server's payload as props, so they are rendered directly below.
// The anti-drift criterion (AC3) is not a render claim at all, so it is pinned against the file's
// own text: two call sites, one implementation, and no import code inside the intake page itself.
// What still needs a browser: importing a real ChatGPT reply on /add and seeing the URL stay put.
import {describe,expect,it} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {DuplicateResolver,ImportPaste,ImportResultSummary} from './App'
import appSource from './App.tsx?raw'   // vite serves the file's text; no DOM and no new dependency

const slice=(from:string,to:string)=>{const a=appSource.indexOf(from),b=appSource.indexOf(to);expect(a).toBeGreaterThan(-1);expect(b).toBeGreaterThan(a);return appSource.slice(a,b)}
const jobForm=slice('function JobForm(','function PublicDuplicateResolver(')
const importPage=slice('function ImportEval(','function Followups(')
const count=(hay:string,needle:string)=>hay.split(needle).length-1

describe('the intake panel accepts the response it handed the prompt over for (AC1)',()=>{
  it('renders a paste box and an import control with no first paint fetch',()=>{
    const html=renderToStaticMarkup(<ImportPaste compact/>)

    expect(html).toContain('<textarea')
    expect(html).toContain('aria-label="Paste ChatGPT JSON"')
    expect(html).toContain('placeholder="Paste JSON here"')
    expect(html).toContain('Validate and Import')
  })

  it('is a button, not a form submit - the panel sits inside the Add job <form>',()=>{
    // Without type="button" the control inherits submit and would re-post the job form instead of
    // importing. This is the one line that cannot be inferred from the /import page, where the
    // same markup has no <form> around it.
    expect(renderToStaticMarkup(<ImportPaste compact/>)).toContain('type="button"')
    expect(jobForm).toContain('<ImportPaste compact/>')
  })

  it('imports in place - the panel offers no link away to /import',()=>{
    const html=renderToStaticMarkup(<ImportPaste compact/>)

    expect(html).not.toContain('<a ')
    expect(html).not.toContain('href')
    expect(jobForm).not.toContain('to="/import"')
    expect(jobForm).not.toContain("nav('/import')")
  })

  it('starts disabled, so an empty box cannot be posted',()=>{
    expect(renderToStaticMarkup(<ImportPaste/>)).toContain('disabled=""')
  })
})

describe('the summary and the duplicate path are the import page\'s own (AC2)',()=>{
  it('reports created evaluation counts and ids',()=>{
    const html=renderToStaticMarkup(<ImportResultSummary result={{ok:true,count:2,created_ids:[7,8]}} compact/>)

    expect(html).toContain('Import successful')
    expect(html).toContain('Imported 2 evaluations')
    expect(html).toContain('Evaluation IDs: 7, 8')
  })

  it('lists the per-job lines for a jobs import',()=>{
    const result={ok:true,type:'jobs',jobs_found:2,imported_jobs:[{job_id:11,company:'Acme GmbH',title:'Backend Engineer (m/w/d)'},{job_id:12,company:'',title:''}]}
    const html=renderToStaticMarkup(<ImportResultSummary result={result} compact/>)

    expect(html).toContain('2 jobs found and imported.')
    expect(html).toContain('Acme GmbH')
    expect(html).toContain('Backend Engineer')       // displayJobTitle strips the (m/w/d) suffix
    expect(html).toContain('Unknown company')        // the empty row still gets a line
    expect(count(html,'<li>')).toBe(2)
  })

  it('offers the same collision choices when the response hits existing jobs',()=>{
    const error={type:'duplicate_conflicts',conflicts:[{index:0,url:'https://jobs.example.com/9182',incoming:{company:'Acme GmbH',title:'Backend Engineer'},existing_jobs:[{id:4,company:'Acme GmbH',title:'Backend Engineer'}]}]}
    const html=renderToStaticMarkup(<DuplicateResolver error={error} jsonText='{}' onDone={()=>{}}/>)

    expect(html).toContain('Duplicate jobs found')
    expect(html).toContain('Override all');expect(html).toContain('Duplicate all');expect(html).toContain('Skip all');expect(html).toContain('Abort')
    expect(html).toContain('Apply per-job choices')
    expect(html).toContain('Incoming: Acme GmbH')
    expect(html).toContain('Existing: #4 Acme GmbH')
  })
})

describe('one implementation, two call sites (AC3)',()=>{
  it('posts to the import endpoint from exactly the four places that already did',()=>{
    // ImportPaste (serving both new call sites), DuplicateResolver's resolved retry, the job detail
    // page's calibration import, and the dashboard prompt modal's auto-import. That count was 4
    // before this task and is 4 after it: the intake panel added no fifth, which is the drift this
    // task exists to prevent.
    expect(count(appSource,"api('/evaluations/import/'")).toBe(4)
    expect(jobForm).not.toContain("api('/evaluations/import/'")
  })

  it('is defined once and rendered by both the intake panel and the import page',()=>{
    expect(count(appSource,'function ImportPaste(')).toBe(1)
    expect(count(appSource,'<ImportPaste')).toBe(2)
    expect(importPage).toContain('<ImportPaste/>')
  })

  it('left no paste box of its own on either page',()=>{
    expect(importPage).not.toContain('<textarea')   // the prose still names the control; the markup is gone
    expect(importPage).not.toContain('useState')    // /import is now chrome around ImportPaste, nothing more
    expect(jobForm).not.toContain('Validate and Import')
    expect(jobForm).not.toContain('<DuplicateResolver')       // reached through ImportPaste only
    expect(jobForm).not.toContain('<ImportResultSummary')
  })

  it('is not offered in public mode, where the endpoint would 403',()=>{
    // views.import_eval has no AllowAny, so DRF's default IsAuthenticated rejects a logged-out
    // visitor. The intake import sits in the !publicMode branch and the German panel has none.
    const panel=jobForm.slice(jobForm.indexOf('{!publicMode&&summary?.count>0'))
    expect(panel.indexOf('<ImportPaste compact/>')).toBeLessThan(panel.indexOf('{publicMode&&summary?.count>0'))
    expect(panel.slice(panel.indexOf('{publicMode&&summary?.count>0'))).not.toContain('<ImportPaste')
  })
})

describe('the three failure modes stay distinguishable (AC4)',()=>{
  const render=(error:any)=>renderToStaticMarkup(<DuplicateResolver error={error} jsonText='not json' onDone={()=>{}}/>)

  it('says where the JSON broke',()=>{
    const html=render({ok:false,errors:['Invalid JSON on line 3, column 12: Illegal trailing comma before end of object']})

    expect(html).toContain('Invalid JSON on line 3, column 12')
    expect(html).not.toContain('Root must contain evaluations list')
    expect(html).toContain('role="alert"')
  })

  it('says a well-formed response carried nothing importable',()=>{
    const html=render({ok:false,errors:['Root must contain evaluations list']})

    expect(html).toContain('Root must contain evaluations list')
    expect(html).not.toContain('Invalid JSON')
  })

  it('shows the server\'s own rejection, one line per problem',()=>{
    const html=render({ok:false,errors:['evaluation[0].job_id does not exist: 123','evaluation[1].fit_score must be 0-100']})

    expect(html).toContain('evaluation[0].job_id does not exist: 123')
    expect(html).toContain('evaluation[1].fit_score must be 0-100')
    expect(render({detail:'Request was throttled. Expected available in 42 seconds.'})).toContain('Request was throttled')
  })

  it('keeps the error heading the import page uses',()=>{
    expect(appSource).toContain('<h2 className="font-semibold text-red-700">Validation errors</h2>')
    expect(count(appSource,'Validation errors</h2>')).toBe(1)
  })
})
