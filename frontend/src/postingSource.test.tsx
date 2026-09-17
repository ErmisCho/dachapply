// TASK-237/TASK-238. Same constraint as cvPopup.test.tsx: this vitest run has no DOM (no jsdom, no
// @testing-library, and TASK-177 forbids adding one) and effects never run, so anything either CV
// popup only shows after a fetch cannot be rendered from a test at all. PostingSource is what makes
// this testable: it is pure, it takes the payload as props, and both popups render the same one -
// the last test pins that neither of them kept markup of its own. What still needs a browser is
// whether the anchor really opens a new tab without closing the popup; that is measured by hand.
import {describe,expect,it} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {PostingSource} from './App'
import appSource from './App.tsx?raw'   // vite serves the file's text; no DOM and no new dependency
import type {LiveSourceText,PostingJob} from './types'

const stored='We are hiring a Senior Python Developer in Vienna.'
const job=(extra:Partial<PostingJob>={}):PostingJob=>({id:7,company:'Acme GmbH',title:'Senior Python Developer',
  url:'https://jobs.example.com/listing/9182',source_text:stored,source_chars:stored.length,source_is_fallback:false,...extra})
const render=(props:any={})=>renderToStaticMarkup(<PostingSource job={job()} {...props}/>)
const panes=(html:string)=>(html.match(/<pre/g)||[]).length

describe('the link to the original listing (TASK-238)',()=>{
  it('is a real anchor to the job url itself, opening a new tab',()=>{
    // AC2. A plain anchor IS the control - no onClick calling window.open, which would break
    // middle-click and ctrl-click and would not be keyboard-reachable as a link at all.
    const html=render()

    expect(html).toContain('href="https://jobs.example.com/listing/9182"')
    expect(html).toContain('target="_blank"')
    expect(html).toContain('rel="noopener noreferrer"')
    expect(html).not.toContain('tabindex="-1"')   // AC3: it stays in the tab order
  })

  it('names the destination, not just "open"',()=>{
    // AC3. "Link" or an unlabelled icon leaves a screen-reader user with no idea where it goes, and
    // the point of this control is that it is NOT the /jobs/<id> link the row already has.
    const html=render()

    expect(html).toContain('aria-label="Open the original posting for Acme GmbH Senior Python Developer at jobs.example.com in a new tab"')
    expect(html).toContain('title="Open the original posting at jobs.example.com in a new tab"')
    expect(html).not.toContain('href="/jobs/7"')   // the internal detail link is a different control
  })

  it('renders nothing at all for a job with no listing url',()=>{
    // AC4. Not a disabled stub and not href="" - an empty href reloads the current page.
    const html=render({job:job({url:''})})

    expect(html).not.toContain('<a ')
    expect(html).not.toContain('href')
    expect(html).not.toContain('Check the original posting')   // nothing to check either
    expect(html).toContain(stored)                             // ...and the stored text still shows
  })
})

describe('what the panel claims the stored text is (TASK-237)',()=>{
  it('calls a collected posting a collected posting, and says generation will use it',()=>{
    const html=render()

    expect(html).toContain(`Collected original posting text (${stored.length} characters). This is the text generation will use.`)
    expect(html).toContain(stored)
  })

  it('does not let a cleaned description pass for the posting',()=>{
    // AC3. The two cases must not read the same; source_is_fallback is the backend saying which one
    // this is, so the UI never has to guess and never flatters what it has.
    const html=render({job:job({source_is_fallback:true})})

    expect(html).toContain(`Cleaned description - no original posting text was collected (${stored.length} characters).`)
    expect(html).not.toContain('Collected original posting text')
  })

  it('says so plainly when there is no source text at all',()=>{
    const html=render({job:job({source_text:'',source_chars:0})})

    expect(html).toContain('No source text is stored for this job, so generation has no posting text to work from.')
    expect(html).not.toContain('This is the text generation will use.')
  })
})

describe('reading the posting at its url (TASK-237)',()=>{
  const fetched:LiveSourceText={ok:true,url:'https://jobs.example.com/listing/9182',final_url:'https://jobs.example.com/listing/9182',
    text:'Tasks: build data pipelines in Vienna. Requirements: Python, Airflow, dbt.',chars:74,stored_chars:49,matches_stored:false,
    fetched_at:'2026-09-17T10:00:00.000Z'}

  it('shows the fetched body in its own pane, and says it differs from what is stored',()=>{
    // AC1. The full body, in a scrollable pane of its own - beside the stored text rather than
    // silently replacing it, because nothing has been written yet at this point.
    const html=render({live:fetched})

    expect(html).toContain(fetched.text)
    expect(html).toContain(stored)
    expect(panes(html)).toBe(2)
    expect(html).toContain('Read from jobs.example.com')
    expect(html).toContain('74 characters')
    expect(html).toContain('differs from the stored text above')
    expect(html).toContain('Use this as the job text')   // AC4: adopting is an explicit action
  })

  it('does not claim a difference when the page matches what is stored',()=>{
    const html=render({live:{...fetched,matches_stored:true}})

    expect(html).toContain('identical to the stored text above')
    expect(html).not.toContain('differs from the stored text above')
  })

  it('reports a failure with the server reason and no body whatsoever',()=>{
    // AC3. The one thing that must never happen here is a fallback body rendered where the posting
    // would be: the stored text is still shown (labelled as stored), and nothing else pretends.
    const html=render({live:{ok:false,url:'https://jobs.example.com/listing/9182',error:'The site answered 403 Forbidden.',fetched_at:'2026-09-17T10:00:00.000Z'} as LiveSourceText})

    expect(html).toContain('The site answered 403 Forbidden.')
    expect(html).toContain('role="alert"')
    expect(panes(html)).toBe(1)                          // only the stored pane
    expect(html).not.toContain('Use this as the job text')
    expect(html).not.toContain('Read from jobs.example.com')
  })
})

describe('both generation surfaces render this one panel',()=>{
  it('is wired into the single popup and into every batch row',()=>{
    // A repo memory: a fix verified on one surface gets assumed to cover the other. Both call sites
    // are asserted here rather than one standing in for the other.
    expect(appSource).toContain('<PostingSource job={preview.job}')       // single popup / #cv-generator
    expect(appSource).toContain('<PostingSource job={row.preview.job}')   // batch popup, per row
  })

  it('left no unlabelled copy of the old batch source-text popover behind',()=>{
    // The batch rows used to dump row.job.original_source_text||row.job.raw_description into a bare
    // <pre> with no provenance at all - which is exactly the "stored text presented as the posting"
    // TASK-237 AC3 forbids. If that string comes back, a second, lying surface came back with it.
    expect(appSource).not.toContain('original_source_text||row.job.raw_description')
    expect(appSource).not.toContain("'No source text stored.'")
    expect(appSource).toContain('to={`/jobs/${row.job.id}`}')   // TASK-32's internal link is untouched
  })
})
