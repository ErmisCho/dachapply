// TASK-261/263/264: the bulk 'Generate selected applications' panel. No DOM in this vitest run
// (see cvPopup.test.tsx), so the copy payload is tested as a pure function, the small components
// through static markup, and the wiring inside the panel through App.tsx's source.
import {describe,expect,it,vi} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {MemoryRouter} from 'react-router-dom'
import {AppliedRowSummary,OriginalPostingLink} from './App'
import appSource from './App.tsx?raw'
import {BULK_COPY_SEPARATOR,combinedClipboardTex,readBulkAutoCopy,writeBulkAutoCopy} from './cvModel'

const jobA='% Job listing: https://a.example/jobs/1\n\n% ===== cv.tex =====\nCV A\n\n% ===== letter.tex =====\nLETTER A'
const jobB='% Job listing: https://b.example/jobs/2\n\n% ===== cv.tex =====\nCV B\n\n% ===== letter.tex =====\nLETTER B'

describe('Copy all payload (TASK-261 AC5)',()=>{
  it('joins every ready job, CV and letter, each block keeping its listing line',()=>{
    const {text,count}=combinedClipboardTex([
      {status:'ready',clipboard_tex:jobA},
      {status:'failed',clipboard_tex:'STALE'},
      {status:'running'},
      {status:'ready',clipboard_tex:jobB},
      {status:'ready',clipboard_tex:''},
    ])
    expect(count).toBe(2)
    expect(text).toBe(jobA+BULK_COPY_SEPARATOR+jobB)
    expect(text.split(BULK_COPY_SEPARATOR)).toEqual([jobA,jobB])
    for(const part of ['CV A','LETTER A','CV B','LETTER B'])expect(text).toContain(part)
    expect(text).not.toContain('STALE')
    expect(BULK_COPY_SEPARATOR.trim().startsWith('%')).toBe(true)   // stays a LaTeX comment
  })

  it('copies nothing when nothing is ready, and also accepts finished task objects',()=>{
    expect(combinedClipboardTex([{status:'failed'},undefined])).toEqual({text:'',count:0})
    expect(combinedClipboardTex([{status:'ready',clipboard_tex:jobA}])).toEqual({text:jobA,count:1})
  })
})

describe('auto-copy toggle storage (TASK-261 AC6/AC7)',()=>{
  it('defaults on, remembers off, and survives storage that throws',()=>{
    const store:Record<string,string>={}
    vi.stubGlobal('localStorage',{getItem:(k:string)=>store[k]??null,setItem:(k:string,v:string)=>{store[k]=v}})
    expect(readBulkAutoCopy()).toBe(true)
    writeBulkAutoCopy(false); expect(readBulkAutoCopy()).toBe(false)
    writeBulkAutoCopy(true); expect(readBulkAutoCopy()).toBe(true)
    vi.stubGlobal('localStorage',{getItem:()=>{throw new Error('blocked')},setItem:()=>{throw new Error('blocked')}})
    expect(readBulkAutoCopy()).toBe(true)
    expect(()=>writeBulkAutoCopy(false)).not.toThrow()
    vi.unstubAllGlobals()
  })
})

describe('bulk panel wiring (TASK-261 AC2/AC3/AC6)',()=>{
  const panel=appSource.slice(appSource.indexOf('function BatchCvGenerator'),appSource.indexOf('type NoteTable'))
  it('copies through the shared helper, never navigator.clipboard directly',()=>{
    expect(panel).toContain('async function copyRowTex(row:any){if(await copyToClipboard(row.clipboard_tex))')
    expect(panel).not.toContain('navigator.clipboard')
    expect(panel).not.toContain('Clipboard access was blocked')
  })
  it('opts generation out of per-task copies and copies the whole batch once at the end',()=>{
    expect(panel).toContain('replace_existing,auto_clipboard:false}')
    expect(panel).toContain('if(autoCopy)await autoCopyBatch(results)')
    expect(panel).toContain("api('/cv-generation/clipboard/',{method:'POST',body:{text}})")
  })
})

describe('original posting link (TASK-263)',()=>{
  it('opens job.url in a new tab without an opener, and renders nothing without a url',()=>{
    const html=renderToStaticMarkup(<OriginalPostingLink company="Acme" title="Engineer (m/w/d)" url="https://jobs.example.com/1"/>)
    expect(html).toContain('href="https://jobs.example.com/1"')
    expect(html).toContain('target="_blank"')
    expect(html).toContain('rel="noopener noreferrer"')
    expect(html).toContain('Original posting')
    expect(renderToStaticMarkup(<OriginalPostingLink company="Acme" title="Engineer" url=""/>)).toBe('')
  })
  it('is rendered on each bulk row and on the job page',()=>{
    expect(appSource).toContain('url={row.preview.job?.url||row.job.url}/>')
    expect(appSource).toContain('</select><OriginalPostingLink company={job.company} title={job.title} url={job.url}/>')
  })
})

describe('mark as applied from the bulk panel (TASK-264)',()=>{
  it('collapses an applied row to one line with the company, title, Applied badge and an expand toggle',()=>{
    const html=renderToStaticMarkup(<MemoryRouter><AppliedRowSummary job={{id:7,company:'Acme',title:'Engineer (m/w/d)'}} onExpand={()=>{}}/></MemoryRouter>)
    expect(html).toContain('Acme')
    expect(html).toContain('Engineer')
    expect(html).toContain('Applied')
    expect(html).toContain('aria-expanded="false"')
    expect(html).toContain('href="/jobs/7"')
  })
  it('uses the board job update API, disables while generating, and starts applied rows collapsed',()=>{
    const panel=appSource.slice(appSource.indexOf('function BatchCvGenerator'),appSource.indexOf('type NoteTable'))
    expect(panel).toContain("api('/jobs/'+row.job.id+'/',{method:'PATCH',body:feedbackStatusPatch('applied'")
    expect(panel).toContain('disabled={rowBusy(row)||row.applying}')
    expect(panel).toContain("collapsed:job.status==='applied'")
    expect(appSource).toContain('<BatchCvGenerator jobs={selectedJobs} onJobUpdated=')
  })
})

describe('bulk dialog adapts to the window (TASK-266, TASK-263, TASK-264)',()=>{
  const card=(url?:string)=>renderToStaticMarkup(<MemoryRouter><AppliedRowSummary job={{id:7,company:'Acme',title:'Engineer',url}} onExpand={()=>{}}/></MemoryRouter>)

  it('keeps the collapsed Applied card on one line, with the original posting link when there is a url',()=>{
    const html=card('https://jobs.example.com/7')
    expect(html).toContain('class="flex flex-nowrap items-center justify-between')
    expect(html).toContain('class="min-w-0 flex-1 truncate"')
    expect(html).toContain('class="flex shrink-0 items-center gap-2"')
    expect(html).toContain('href="https://jobs.example.com/7"')
    expect(card()).not.toContain('Original posting')
    expect(appSource).toContain('job={{...row.job,url:row.preview.job?.url||row.job.url}}')
  })

  it('sizes the dialog from the viewport and lets its height follow the content',()=>{
    const panel=appSource.slice(appSource.indexOf('function BatchCvGenerator'),appSource.indexOf('type NoteTable'))
    expect(panel).toContain('className="max-h-[calc(100dvh-1.5rem)] w-[min(72rem,calc(100vw-1.5rem))] overflow-y-auto overflow-x-hidden [overflow-wrap:anywhere] rounded-2xl')
    expect(panel).not.toContain('max-h-[90vh]')
    expect(panel).toContain('<label className="mr-auto flex items-center gap-2 text-sm sm:whitespace-nowrap">')
  })
})
