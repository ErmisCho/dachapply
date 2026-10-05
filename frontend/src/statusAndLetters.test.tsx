// TASK-262 / TASK-265 wiring. No DOM here (see cvPopup.test.tsx), so the loaded selects are read from
// the source; the helpers themselves are tested in letterOptions.test.ts and appUtils.test.ts.
import {describe,expect,it} from 'vitest'
import appSource from './App.tsx?raw'
// @ts-expect-error -- this frontend ships no @types/node, but vitest runs this file on node
import {readFileSync} from 'node:fs'
const cssSource=readFileSync(new URL('./index.css',import.meta.url),'utf8')

describe('cross-language letters in the generators (TASK-262)',()=>{
  it('single popup lists every letter via letterOptions and warns on a mismatch',()=>{
    expect(appSource).toContain('const letters=letterOptions(preview?.letters||[],cv)')
    expect(appSource).toContain('setLetter(defaultLetter(preview.letters,next))')
    expect(appSource).toContain('letterMismatchWarning(preview?.letters||[],cv,letter)')
    expect(appSource).toContain('{letterWarning&&<p role="status" className="mt-1 text-xs text-amber-700 dark:text-amber-300">{letterWarning}</p>}')
    expect(appSource).not.toContain('.filter((x:any)=>x.language===cv)')
  })

  it('bulk rows do the same and keep the No letter option',()=>{
    expect(appSource).toContain('<option value="">No letter</option>{letterOptions(row.preview.letters,row.cv).map(')
    expect(appSource).toContain('letter:defaultLetter(row.preview.letters,cv)')
    expect(appSource).toContain('letterMismatchWarning(row.preview.letters,row.cv,row.letter)')
    expect(appSource).not.toContain('option.language===row.cv')
  })
})

describe('Ready to submit status (TASK-265)',()=>{
  it('is a selectable status between to_apply and applied, teal, and counted as unapplied',()=>{
    expect(appSource).toContain("const statuses=['new','reviewed','to_apply','ready_to_submit','applied'")
    expect(appSource).toContain("ready_to_submit:'teal'")
    expect(appSource).toContain("teal:'app-badge-teal'")
    expect(appSource).toContain("unapplied_statuses:['new','reviewed','to_apply','ready_to_submit']")
    expect(cssSource).toMatch(/\n\.app-badge-teal\{/)
    expect(cssSource).toMatch(/\n\.dark \.app-badge-teal\{/)
  })

  it('shows every status through jobStatusLabel, never the raw key or a first-underscore replace',()=>{
    expect(appSource).not.toContain("replace('_',' ')")
    expect(appSource).not.toContain('{statuses.map(x=><option key={x}>{x}</option>)}')
    expect(appSource.split('{statuses.map(x=><option key={x} value={x}>{jobStatusLabel(x)}</option>)}').length-1).toBe(4)
    expect(appSource).toContain('Job status: <b>{jobStatusLabel(job.status)}</b>')
  })
})
