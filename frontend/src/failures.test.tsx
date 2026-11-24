// TASK-406.3: the failures page, as static markup (no DOM in this run).
import {describe,expect,it} from 'vitest'
import app from './App.tsx?raw'
import {renderToStaticMarkup} from 'react-dom/server'
import {FailuresView,RunView,elapsed,hasRunning,pollEvery,safePr,type FailuresData,type FixRun} from './Failures'

const run:FixRun={id:'r1',signature:'a',state:'running',step:'Editing',started_at:'2026-11-20T10:00:00Z',log:['line <b>1</b>','line 2']}
const group=(over:object={})=>({signature:'a',cause:'LaTeX could not compile <i>x</i>',class:'actionable',count:3,last:'2026-11-20T10:00:00Z',job_ids:[1],task_id:'TASK-9',state:'new',run:null,...over})
const data=(groups:any[],fix={enabled:false,reason:'Fix runs are not built yet.'}):FailuresData=>({groups,fix})
const view=(d:FailuresData|null,open='')=>renderToStaticMarkup(<FailuresView data={d} error="" open={open} busy="" onOpen={()=>{}} onFix={()=>{}} onStop={()=>{}}/>)

describe('failures page',()=>{
  it('lists cause, count, class, task and state, and renders text as text',()=>{
    const html=view(data([group()]))
    for(const t of ['Count','3','actionable','TASK-9','New','&lt;i&gt;x&lt;/i&gt;'])expect(html).toContain(t)
    expect(html).not.toContain('<i>x</i>')
  })
  it('disables Fix and says why; non-actionable groups have no Fix',()=>{
    const html=view(data([group(),group({signature:'b',class:'quota',state:'not_a_bug'})]))
    expect(html).toContain('disabled=""')
    expect(html).toContain('Fix runs are not built yet.')
    expect(html.match(/>Fix</g)).toHaveLength(1)
    expect(view(data([group({class:'unknown',state:'look'})]))).toContain('Needs a look')
  })
  it('shows the live run with step, elapsed time, log lines and a Stop button',()=>{
    const html=view(data([group({state:'running',run})],{enabled:true,reason:''}))
    expect(html).toContain('Editing')
    expect(html).toContain('line &lt;b&gt;1&lt;/b&gt;')
    expect(html).toContain('>Stop<')
    expect(html).not.toContain('>Fix<')
    expect(hasRunning(data([group({run})]))).toBe(true)
    expect(hasRunning(data([group({run:{...run,state:'pr'}})]))).toBe(false)
    expect([pollEvery(data([group({run})])),pollEvery(data([group({run:{...run,state:'pr'}})])),pollEvery(data([group({run:{...run,state:'merged'}})])),pollEvery(null)]).toEqual([3000,60000,0,0])
    expect(elapsed(run,Date.parse('2026-11-20T10:01:05Z'))).toBe('1m 5s')
  })
  it('links only https://github.com/ pull requests',()=>{
    expect(safePr('javascript:alert(1)')).toBe('')
    expect(safePr('https://evil.test/https://github.com/')).toBe('')
    expect(renderToStaticMarkup(<RunView run={{...run,state:'pr',pr_url:'https://github.com/o/r/pull/1'}}/>)).toContain('href="https://github.com/o/r/pull/1"')
    expect(renderToStaticMarkup(<RunView run={{...run,state:'pr',pr_url:'javascript:alert(1)'}}/>)).not.toContain('href')
  })
  it('shows records with file text, and a gone file as such',()=>{
    const rec={id:'x',time:'2026-11-20T10:00:00Z',job_id:1,route:'r',provider:'p',model:'m',error:'boom',diagnostics:'diag',instructions:'',files:[{name:'a.tex',text:'\\documentclass'},{name:'b.tex',text:null}]}
    const html=renderToStaticMarkup(<FailuresView data={data([group()])} error="" open="a" records={[rec]} busy="" onOpen={()=>{}} onFix={()=>{}} onStop={()=>{}}/>)
    for(const t of ['boom','diag','a.tex','documentclass','not readable'])expect(html).toContain(t)
  })
  it('is wired: owner flag, route and nav link',()=>{
    expect(app).toContain('user?.can_view_failures&&<Link className="nav-link" to="/failures">')
    expect(app).toContain('path="/failures"')
  })
})
