// TASK-390 (no per-variant Keep / Copy TeX), TASK-391 (disabled reasons as titles), TASK-392 (Generate hides
// once variants exist; the two evaluation buttons say how they differ). Source assertions: no DOM here.
import {describe,expect,it} from 'vitest'
import appSource from './App.tsx?raw'

describe('prepared-documents cleanup (TASK-390/391/392)',()=>{
  it('drops per-variant Keep and Copy TeX',()=>{
    expect(appSource).not.toContain("action:'keep'")
    expect(appSource).not.toContain('onCopy?.(v.key)')
  })
  it('explains disabled buttons',()=>{
    expect(appSource).toContain('title={selectWhy}')
    expect(appSource).toContain("'Tick a document to compile'")
  })
  it('hides Generate when variants exist and labels the evaluations',()=>{
    expect(appSource).toContain('hideGenerate={hasPrep}')
    // Board toolbar: the ready count rides on the existing /application-prep/active/ payload (done), no new field.
    // TASK-411: with prepared documents the board keeps the popup as Adjust (no Generate), as the job page does.
    expect(appSource).toContain('const boardPrepared=(id:number)=>(prepActive[id]?.done||0)>0&&!prepActive[id]?.running;')
    expect(appSource).toContain("{boardPrepared(selected[0])?'Adjust CV and letters':'Generate CV and Motivation Letter'}")
    expect(appSource).toContain('<CvGenerator compact hideGenerate={boardPrepared(selected[0])} job={selectedJobs[0]}')
    expect(appSource).toContain('Analyze selected jobs (ChatGPT prompt)')
    expect(appSource).toContain('Evaluate with model (in app)')
  })
})
