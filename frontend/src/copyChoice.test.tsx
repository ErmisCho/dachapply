// TASK-405: the owner ticks which of the job's CVs and letters to adjust and, separately, which to copy as TeX.
// No DOM in this vitest run (see cvPopup.test.tsx), so the list is tested through static markup, the choice
// through the pure helpers, and the wiring through App.tsx's source.
import {describe,expect,it} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {CopyTexAction,CopyTextAction,DocumentTicks} from './App'
import appSource from './App.tsx?raw'
import {defaultDocuments,followRun,presentDocuments,runError,startedRuns,tickedDocuments,type GeneratedFile} from './cvModel'

const file=(kind:string,name:string,extra:Partial<GeneratedFile>={}):GeneratedFile=>({kind,language:'de',tex:`C:\\ws\\CVs\\${name}.tex`,pdf:`C:\\ws\\CVs\\${name}.pdf`,generated_at:'',missing:false,pdf_missing:false,...extra})
const files=[file('letter','Anschreiben'),file('cv','CV-EN',{language:'en'}),file('message','Message'),file('cv','CV-DE'),file('letter','Bewerbung'),file('cv','Deleted',{missing:true})]
const documents=presentDocuments(files)
const tex=(name:string)=>`C:\\ws\\CVs\\${name}.tex`
const noop=()=>{}

describe('which documents can be ticked',()=>{
  it('every document on disk, CVs first, a missing one never',()=>{
    expect(documents.map(x=>x.tex)).toEqual(['CV-EN','CV-DE','Anschreiben','Bewerbung','Message'].map(tex))
    expect(presentDocuments(undefined)).toEqual([])
  })
  it('starts on the current CV and the selected template\'s letter, else the newest of each',()=>{
    const preview={artifacts:{cv_tex:tex('CV-DE')},letter_artifacts:{bewerbungsschreiben:{letter_tex:tex('Bewerbung')},anschreiben:{}}}
    expect(defaultDocuments(documents,preview,'bewerbungsschreiben')).toEqual([tex('CV-DE'),tex('Bewerbung')])
    expect(defaultDocuments(documents,preview,'anschreiben')).toEqual([tex('CV-DE'),tex('Anschreiben')])
    expect(defaultDocuments(documents.filter(x=>x.kind==='cv'),null,'')).toEqual([tex('CV-EN')])
    expect(defaultDocuments([],null,'')).toEqual([])
  })
  it('keeps the owner\'s choice, nothing ticked included, and drops a document that is gone',()=>{
    expect(tickedDocuments(documents,null,[tex('CV-EN')])).toEqual([tex('CV-EN')])
    expect(tickedDocuments(documents,[],[tex('CV-EN')])).toEqual([])
    expect(tickedDocuments(documents,[tex('Message'),tex('CV-DE'),tex('Deleted')],[])).toEqual([tex('CV-DE'),tex('Message')])
  })
  it('a run per document is waited for; one that could not start is named',()=>{
    expect(startedRuns({task_id:'a'})).toEqual([{id:'a',documents:[]}])
    const tasks=[{id:'a',documents:['CV-EN.tex']},{id:'',documents:['CV-DE.tex']}]
    expect(startedRuns({task_id:'a',tasks})).toBe(tasks)
    expect(runError(tasks[1],'Failed')).toBe('CV-DE.tex: Failed');expect(runError({id:'a',documents:[]},'Failed')).toBe('Failed')
  })
})

describe('after a run',()=>{
  it('the copy follows a document whose run wrote a fresh file (a sent document)',()=>{
    const run={id:'a',documents:['CV-DE.tex'],paths:[tex('CV-DE')]}
    expect(followRun([tex('CV-DE'),tex('Anschreiben')],run,{artifacts:{cv_tex:tex('CV-DE-2')}})).toEqual([tex('CV-DE-2'),tex('Anschreiben')])
    expect(followRun([tex('Anschreiben')],run,{artifacts:{cv_tex:tex('CV-DE-2')}})).toEqual([tex('Anschreiben')])
    expect(followRun([tex('CV-DE')],run,{artifacts:{}})).toEqual([tex('CV-DE')])
  })
})

describe('the list',()=>{
  const html=renderToStaticMarkup(<DocumentTicks documents={documents} adjust={[tex('CV-DE')]} copy={[tex('CV-EN'),tex('Anschreiben')]} onAdjust={noop} onCopy={noop} workspace="C:\ws"/>)
  const ticked=(label:string)=>new RegExp(`<input[^>]*aria-label="${label}"[^>]*checked=""`).test(html)
  it('has an Adjust and a Copy tick per document, with type, language and file name',()=>{
    expect(html.match(/type="checkbox"/g)?.length).toBe(10)
    for(const label of ['CV · EN · CV-EN.tex','CV · DE · CV-DE.tex','Letter · DE · Anschreiben.tex','Letter · DE · Bewerbung.tex','Short message · DE · Message.tex']){
      expect(html).toContain(`aria-label="Adjust ${label}"`);expect(html).toContain(`aria-label="Copy ${label}"`)
    }
    expect(html).not.toContain('Deleted')
  })
  it('keeps Adjust and Copy independent',()=>{
    expect(ticked('Adjust CV · DE · CV-DE.tex')).toBe(true);expect(ticked('Copy CV · DE · CV-DE.tex')).toBe(false)
    expect(ticked('Adjust CV · EN · CV-EN.tex')).toBe(false);expect(ticked('Copy CV · EN · CV-EN.tex')).toBe(true)
  })
  it('says so when there is nothing yet',()=>{
    expect(renderToStaticMarkup(<DocumentTicks documents={[]} adjust={[]} copy={[]} onAdjust={noop} onCopy={noop}/>)).toContain('No generated documents on disk')
  })
})

describe('Copy TeX',()=>{
  it('is off with a reason when nothing is ticked or a task runs',()=>{
    const button=(ticked:string[],busy=false)=>renderToStaticMarkup(<CopyTexAction documents={ticked} busy={busy} onCopy={async()=>true}/>)
    expect(button([])).toContain('disabled=""');expect(button([])).toContain('title="Tick a document to copy"')
    expect(button(['a'],true)).toContain('title="Wait for the running task to finish"')
    expect(button(['a'])).not.toContain('disabled=""');expect(button(['a'])).toContain('aria-label="Copy generated TeX files"')
  })
})

describe('Copy text (TASK-409)',()=>{
  const button=(copy:string[],busy=false)=>renderToStaticMarkup(<CopyTextAction documents={documents} copy={copy} busy={busy} onCopy={async()=>true}/>)
  it('needs a ticked letter or message; a ticked CV alone is not enough',()=>{
    for(const copy of [[],[tex('CV-DE')]]){expect(button(copy)).toContain('disabled=""');expect(button(copy)).toContain('title="Tick a letter or short message to copy"')}
    for(const name of ['Anschreiben','Message'])expect(button([tex('CV-DE'),tex(name)])).not.toContain('disabled=""')
    expect(button([tex('Anschreiben')],true)).toContain('title="Wait for the running task to finish"')
  })
})

describe('wiring',()=>{
  const gen=appSource.slice(appSource.indexOf('export function CvGenerator'),appSource.indexOf('function BatchCvGenerator'))
  const batch=appSource.slice(appSource.indexOf('function BatchCvGenerator'),appSource.indexOf('type NoteTable'))
  it('the single-job generator sends the ticked documents',()=>{
    expect(gen).toContain('presentDocuments(preview?.generated_files)')
    expect(gen).toContain('<DocumentTicks documents={documents} adjust={adjTicked} copy={copyTicked}')
    expect(gen.split('documents:adjTicked').length-1).toBe(2)
    expect(gen).toContain("/cv-generation/tex/`,{method:'POST',body:{documents:ticked}}")
    expect(gen).toContain('copyDocuments(ticked=copyTicked)')
    expect(gen).toContain('ticked=followRun(ticked,run,done)')
    expect(gen).toContain('<CopyTexAction documents={copyTicked} busy={loading||revisionLoading||compileLoading} onCopy={copyDocuments}/>')
    expect(gen).not.toContain('create_cv:adjCv')
  })
  it('both popups copy the ticked letters as text',()=>{
    expect(gen).toContain('body:{documents:copyTicked,plain:true}');expect(gen).toContain('onCopy={copyLetterText}/>')
    expect(batch).toContain('body:{documents:rowTicks(row).copy,plain:true}');expect(batch).toContain('onCopy={()=>copyRowText(row)}/>')
  })
  it('bulk rows offer the same choice',()=>{
    expect(batch).toContain('<DocumentTicks {...rowTicks(row)}')
    expect(batch.split('documents:rowTicks(row).adjust').length-1).toBe(2)
    expect(batch).toContain('copyRowDocuments(row:any,ticked=rowTicks(row).copy)')
    expect(batch).toContain('ticked=followRun(ticked,run,task)')
  })
  it('the automatic copy after a single run still copies everything it made',()=>{
    expect(gen).toContain('await copyTex(current.clipboard_tex)))flashTexCopied()')
  })
})
