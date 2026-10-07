// TASK-271: the rename control on each generated CV and letter. This vitest has no DOM (TASK-177), so
// it reads the emitted markup of both states and the wiring in the source; the click-through is
// verified in the browser.
import {describe,expect,it} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {RenameArtifact} from './App'
import appSource from './App.tsx?raw'
import {artifactStem} from './cvModel'

const save=async()=>{}

describe('rename generated files (TASK-271)',()=>{
  it('starts from the file name without folder or extension',()=>{
    expect(artifactStem('C:\\latex\\CVs\\Owner-CV-Accenture-AI-Engineer.tex')).toBe('Owner-CV-Accenture-AI-Engineer')
    expect(artifactStem('/srv/latex/output/Owner-Anschreiben.v2.PDF')).toBe('Owner-Anschreiben.v2')
    expect(artifactStem(undefined)).toBe('')
  })

  it('is a labelled pencil button until opened',()=>{
    const html=renderToStaticMarkup(<RenameArtifact path="C:\latex\CVs\Owner-CV.tex" label="CV" onRename={save}/>)
    expect(html).toContain('aria-label="Rename CV"')
    expect(html).toContain('title="Rename CV"')
    expect(html).not.toContain('<input')
  })

  it('opens as an input holding the current name with Save and Cancel',()=>{
    const html=renderToStaticMarkup(<RenameArtifact path="C:\latex\output\Owner-Letter-Acme.tex" label="Letter" onRename={save} startEditing/>)
    expect(html).toContain('aria-label="New name for Letter"')
    expect(html).toContain('value="Owner-Letter-Acme"')
    expect(html).toMatch(/<button type="submit"[^>]*>Save<\/button>/)
    expect(html).toContain('>Cancel</button>')
  })

  it('is offered on the CV and the letter in the single-job panel and in every bulk row',()=>{
    expect(appSource).toContain('<CopyPath label="CV TeX" path={artifacts.cv_tex} workspace={workspace} taskId={taskId} artifactKey="cv_tex" onRename={rename(\'cv\')}/>')
    expect(appSource).toContain('<CopyPath label="Letter TeX" path={artifacts.letter_tex} workspace={workspace} taskId={taskId} artifactKey="letter_tex" onRename={rename(\'letter\')}/>')
    expect(appSource.match(/<ArtifactPaths artifacts=\{selectedArtifacts\}[^>]*jobId=\{job\.id\} letterKey=\{letter\} onRenamed=\{refreshArtifacts\}\/>/g)).toHaveLength(2)
    expect(appSource).toMatch(/<ArtifactPaths artifacts=\{row\.artifacts\|\|row\.preview\?\.artifacts\}[^>]*jobId=\{row\.job\.id\}[^>]*onRenamed=\{\(\)=>refreshArtifacts\(row\)\}\/>/)
    // Only the new name goes to the server, never a path; Escape closes the editor, not the popup.
    expect(appSource).toContain("body:{artifact,letter_template:letterKey||'',name}")
    expect(appSource).toContain("if(e.key==='Escape'){e.preventDefault();e.stopPropagation();setEditing(false)}")
  })
})
