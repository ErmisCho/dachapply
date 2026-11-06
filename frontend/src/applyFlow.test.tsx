// TASK-351/352/353. No DOM in this vitest run: this covers what renders; tests/apply-flow.mjs clicks it in Chrome.
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {MemoryRouter} from 'react-router-dom'
import appSource from './App.tsx?raw'
import {ClearSkipDialog,FitBandTable,FunnelPanel,JobApplyBar,NextUpPanel,PostingIncomplete,postingHold,salaryNotStated,storedHiddenPanels,storedPanelOrder} from './App'
import {chosenTex,type PrepVariant} from './applicationPrep'
import type {Job,Stats} from './types'

const noop=async()=>{}
const job=(extra:Partial<Job>={})=>({id:7,company:'Acme',title:'Engineer',status:'ready_to_submit',url:'https://jobs.example/7',...extra}) as Job
const bar=(extra:Partial<Job>={},letter:string|undefined='Anschreiben · German (recommended)')=>renderToStaticMarkup(<JobApplyBar job={job(extra)} letter={letter} onCopy={noop} onMarkApplied={noop}/>)
const button=(html:string,label:string)=>html.split('<button').find(b=>b.includes(label))||''
const counts={applications:4,interviews:1,offers:0,applied_to_interview_rate:25,interview_to_offer_rate:0}
const stats=(all_time={},extra={}):Stats=>({funnel:{recent_window_days:90,recent_window_start:'2026-08-08',all_time:{...counts,...all_time},recent:counts,interviews_without_application:0,...extra}})
function stubStorage(init:Record<string,string>={}){vi.stubGlobal('localStorage',{getItem:(k:string)=>init[k]??null,setItem:(k:string,v:string)=>{init[k]=v},removeItem:(k:string)=>{delete init[k]}});return init}
afterEach(()=>vi.unstubAllGlobals())

describe('TASK-351 Next up',()=>{
  it('links each job to its page and says how many there are in all',()=>{
    const html=renderToStaticMarkup(<MemoryRouter><NextUpPanel total={11} rows={[{id:3,company:'Acme',title:'Engineer (m/w/d)',status:'ready_to_submit',latest_fit_score:82},{id:4,company:'Beta',title:'Lead',status:'to_apply',latest_fit_score:null}]}/></MemoryRouter>)
    expect(html).toContain('2 of 11')
    expect(html).toContain('href="/jobs/3"')
    expect(html).toContain('Ready to submit')
    expect(html).toContain('Fit 82')
    expect(html.match(/Fit /g)?.length).toBe(1)
  })
  it('leads a fresh board and is added ahead of an older saved order',()=>{
    stubStorage()
    expect(storedPanelOrder()[0]).toBe('next_up')
    stubStorage({dachapply_dashboard_panel_order:JSON.stringify(['funnel','total'])})
    expect(storedPanelOrder().slice(0,1)).toEqual(['next_up'])
    expect(storedPanelOrder().indexOf('funnel')).toBeLessThan(storedPanelOrder().indexOf('total'))
  })
  it('leaves a saved hidden choice alone, including hiding Next up itself',()=>{
    const hidden=['next_up','funnel','mailbox_unmatched']
    const store=stubStorage({dachapply_dashboard_panel_hidden:JSON.stringify(hidden),dachapply_dashboard_panel_defaults_seeded:JSON.stringify(['mailbox_unmatched'])})
    expect(storedHiddenPanels()).toEqual(hidden)
    expect(store.dachapply_dashboard_panel_hidden).toBe(JSON.stringify(hidden))
  })
})

describe('TASK-351 job page bar',()=>{
  beforeEach(()=>{stubStorage()})
  it('opens the job URL in a new tab',()=>{
    const html=bar()
    expect(html).toContain('href="https://jobs.example/7"')
    expect(html).toContain('target="_blank"')
    expect(html).toContain('Open posting')
    expect(button(bar({url:''}),'Open posting')).toContain('disabled')
  })
  it('stays below the nav',()=>{
    expect(bar()).toContain('sticky top-[3.3rem]')
  })
  it('names the letter it copies and cannot copy without one',()=>{
    expect(bar()).toContain('Copy Anschreiben · German (recommended)')
    expect(button(bar(),'Copy TeX')).not.toContain('disabled')
    expect(button(bar({},''),'Copy TeX')).toContain('disabled')
  })
  it('offers Mark applied only while the job is still unapplied',()=>{
    for(const status of ['new','reviewed','to_apply','ready_to_submit'])expect(button(bar({status}),'Mark applied')).not.toContain('disabled')
    for(const status of ['interview','offer','rejected'])expect(button(bar({status}),'Mark applied')).toContain('disabled')
    expect(bar({status:'applied'})).not.toContain('Mark applied')
    expect(bar({status:'applied'})).toContain('Applied')
  })
  it('copies what TexPicker has selected: the choice, or the recommended one',()=>{
    const v=(key:string,recommended=false)=>({key,document:'letter',language:'de',status:'ready',recommended}) as PrepVariant
    const options=[v('a'),v('b',true)]
    expect(chosenTex(options,'')).toBe('b')
    expect(chosenTex(options,'a')).toBe('a')
    expect(chosenTex(options,'gone')).toBe('b')
    expect(appSource.match(/chosenTex\(/g)?.length).toBe(2)
  })
})

describe('TASK-352 confirmation',()=>{
  const rows=[{id:1,company:'Acme',title:'Engineer (m/w/d)'},{id:2,company:'Beta',title:'Lead'}]
  it('lists company and title with the count, in the page',()=>{
    const html=renderToStaticMarkup(<ClearSkipDialog rows={rows} onConfirm={()=>{}} onClose={()=>{}}/>)
    expect(html).toContain('role="dialog"')
    expect(html).toContain('Move 2 jobs to Skipped?')
    expect(html).toContain('Move 2 to Skipped')
    expect(html).toContain('<b>Acme</b> · Engineer')
    expect(html).toContain('<b>Beta</b> · Lead')
    expect(html).toContain('Cancel')
  })
  it('is only offered when something matches',()=>{
    expect(appSource).toContain('{skipRecommended.length>0&&<button')
    expect(appSource).toContain('setClearSkip(skipRecommended)')
  })
})

describe('TASK-353 results',()=>{
  it('says undated interviews count, not that they are left out',()=>{
    const html=renderToStaticMarkup(<FunnelPanel stats={stats({},{interviews_without_application:5})}/>)
    expect(html).toContain('5 jobs reached interview with no application date. They count as applications here')
    expect(html).not.toContain('left out')
  })
  it('states how many applications are waiting, and nothing when none are',()=>{
    expect(renderToStaticMarkup(<FunnelPanel stats={stats({waiting:12})}/>)).toContain('12 applications are still waiting for an answer')
    expect(renderToStaticMarkup(<FunnelPanel stats={stats({waiting:1})}/>)).toContain('1 application is still waiting')
    expect(renderToStaticMarkup(<FunnelPanel stats={stats({waiting:0})}/>)).not.toContain('waiting')
  })
  it('shows each fit band as a table row',()=>{
    const fit_bands=[{band:'80+',applications:6,interviews:1,rejections:2},{band:'No score',applications:3,interviews:2,rejections:0}]
    const html=renderToStaticMarkup(<FitBandTable stats={stats({waiting:4},{fit_bands})}/>)
    expect(html).toContain('<caption')
    expect(html).toContain('<th scope="row" class="py-1 text-left font-medium">No score</th>')
    expect(html).toContain('>Rejections</th>')
    expect(html).toContain('4 applications are still waiting')
    expect(renderToStaticMarkup(<FitBandTable stats={stats()}/>)).toBe('')
  })
})

describe('TASK-350 posting gaps on screen',()=>{
  const badge=(job:{posting_missing?:string[];status?:string})=>renderToStaticMarkup(<PostingIncomplete job={job}/>)
  it('a salary-only gap is a neutral note with no hold wording',()=>{
    const job={posting_missing:['salary'],status:'to_apply'}
    expect(postingHold(job)).toBe(false);expect(salaryNotStated(job)).toBe(true)
    expect(badge(job)).toContain('Salary not stated');expect(badge(job)).toContain('app-badge-slate')
    expect(badge(job)).not.toContain('Posting incomplete')
  })
  it('Ready to submit never shows hold wording, whatever is missing',()=>{
    const salary={posting_missing:['tasks','salary'],status:'ready_to_submit'},other={posting_missing:['tasks'],status:'ready_to_submit'}
    expect(postingHold(salary)).toBe(false);expect(postingHold(other)).toBe(false)
    expect(badge(salary)).toContain('Salary not stated');expect(badge(salary)).not.toContain('Posting incomplete')
    expect(badge(other)).toBe('')
  })
  it('any other gap keeps the existing hold wording',()=>{
    const job={posting_missing:['tasks','salary'],status:'to_apply'}
    expect(postingHold(job)).toBe(true)
    expect(badge(job)).toContain('>Posting incomplete<');expect(badge(job)).toContain('title="Missing: tasks, salary"')
    expect(appSource).toContain('Posting incomplete: missing {postingMissing(j)}. Paste the full posting here.')
  })
})
