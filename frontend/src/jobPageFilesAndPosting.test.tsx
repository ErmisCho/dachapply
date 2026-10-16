// TASK-301 (every generated file in the job's table) and TASK-302 (compact accepted text with the
// structured version beside it). No DOM in this vitest run (TASK-177): markup and source wiring only.
import {describe,expect,it} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {GeneratedFilesTable,PostingSource,StructuredPosting} from './App'
import {postingSections} from './appUtils'
import appSource from './App.tsx?raw'
import type {PostingJob} from './types'

const file=(extra:any)=>({kind:'cv',language:'de',tex:'C:\\ws\\CVs\\Owner-CV.tex',pdf:'C:\\ws\\CVs\\Owner-CV.pdf',generated_at:'2026-10-16T08:00:00+00:00',missing:false,pdf_missing:false,...extra})

describe('Generated files table (TASK-301)',()=>{
  it('lists every row in the order the server gives (newest first) with type and language',()=>{
    const html=renderToStaticMarkup(<GeneratedFilesTable workspace="C:\ws" files={[
      file({kind:'letter',tex:'C:\\ws\\output\\Owner-Anschreiben.tex',pdf:'C:\\ws\\output\\Owner-Anschreiben.pdf'}),
      file({kind:'message',language:'en',tex:'C:\\ws\\output\\Owner-Short-Message.tex',pdf:'C:\\ws\\output\\Owner-Short-Message.pdf'}),
      file({})]}/>)
    expect((html.match(/<tr class="border-t/g)||[]).length).toBe(3)
    expect(html.indexOf('Owner-Anschreiben.tex')).toBeLessThan(html.indexOf('Owner-Short-Message.tex'))
    expect(html.indexOf('Owner-Short-Message.tex')).toBeLessThan(html.indexOf('Owner-CV.tex'))
    expect(html).toContain('>Short message<')
    expect(html).toContain('>EN<')
    expect(html).toContain('aria-label="Copy full path for Letter TeX"')
  })

  it('shows a file deleted on disk as missing instead of dropping it',()=>{
    const html=renderToStaticMarkup(<GeneratedFilesTable workspace="C:\ws" files={[file({missing:true,pdf_missing:true})]}/>)
    expect(html).toContain('Missing on disk:')
    expect(html).not.toContain('Copy full path for CV TeX')
  })

  it('is fed from the preview on the job page and refreshed after a run and a rename',()=>{
    expect(appSource).toContain('{!compact&&<ArtifactPaths artifacts={selectedArtifacts} files={preview?.generated_files}')
    expect(appSource).toContain('generated_files:p.generated_files,clipboard_tex:p.clipboard_tex')
    expect(appSource).toContain("if(current.status==='ready'){api(`/jobs/${job.id}/cv-generation/`).then((p:any)=>setPreview((c:any)=>({...c,generated_files:p.generated_files})))")
  })
})

const headed=`Overview: Wienerberger builds AI tooling.
Required experience
- Python, 3+ years
Tasks / responsibilities
- Build RAG pipelines
Preferred qualifications
- Azure
Other details (benefits, application process)
Wir bieten: Gleitzeit`

describe('structured version of the posting (TASK-302)',()=>{
  it('reads the TASK-260 headings and common German ones, merging repeats and dropping bullets',()=>{
    expect(postingSections(headed)).toEqual([
      {title:'Overview',lines:['Wienerberger builds AI tooling.']},
      {title:'Requirements',lines:['Python, 3+ years']},
      {title:'Responsibilities',lines:['Build RAG pipelines']},
      {title:'Nice to have',lines:['Azure']},
      {title:'Benefits',lines:['Gleitzeit']},   // "Other details" got no lines of its own, so it is not shown
    ])
    expect(postingSections('Ihre Aufgaben:\n• Daten\nIhr Profil\n• Python\nIhre Aufgaben\n• Mehr')).toEqual([
      {title:'Responsibilities',lines:['Daten','Mehr']},{title:'Requirements',lines:['Python']}])
  })

  it('says there is no structured version for unheaded page text',()=>{
    expect(postingSections('We build things. Python is required. Apply now.')).toEqual([])
    expect(renderToStaticMarkup(<StructuredPosting text="Just a paragraph."/>)).toContain('No structured version yet')
  })

  const job:PostingJob={id:1823,company:'Wienerberger',title:'AI Engineer',url:'',source_text:headed,source_chars:headed.length,source_is_fallback:false,pending_source_text:'',pending_source_fetched_at:null,source_fetch_error:''}
  it('sits beside a height-bounded accepted text on the job page only',()=>{
    const page=renderToStaticMarkup(<PostingSource job={job} structured/>)
    expect(page).toContain('class="grid gap-2 md:grid-cols-2"')   // side by side from md, stacked below
    expect(page).toContain('class="mt-1 h-40 max-h-96 resize-y"')
    expect(page).toContain('<h4 class="font-semibold">Responsibilities</h4>')
    expect(page).toMatch(/role="region" aria-labelledby="structured-posting-heading" tabindex="0" class="mt-1 h-40 overflow-auto/)
    const popup=renderToStaticMarkup(<PostingSource job={job}/>)
    expect(popup).not.toContain('Structured version')
    expect(appSource).toContain('saveLabel="Save company and job text" structured={!compact}/>')
  })
})
