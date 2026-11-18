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
    expect(appSource).toContain('Analyze selected jobs (ChatGPT prompt)')
    expect(appSource).toContain('Evaluate with model (in app)')
  })
})
