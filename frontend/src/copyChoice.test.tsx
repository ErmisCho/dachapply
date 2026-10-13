// TASK-279: Copy TeX lets the owner pick Both / CV only / Letter only when a run has both documents.
// No DOM in this vitest run (see cvPopup.test.tsx), so the control is tested through static markup,
// the choice through the pure helper plus a mocked clipboard, and the wiring through App.tsx's source.
import {afterEach,describe,expect,it,vi} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {CopyTexAction} from './App'
import appSource from './App.tsx?raw'
import {copyToClipboard} from './appUtils'
import {cvClipboardParts,hasTexChoice,texForChoice,type TexChoice} from './cvModel'

const cv='% Job listing: https://a.example/jobs/1\n\n% ===== cv.tex =====\nCV A'
const letter='% Job listing: https://a.example/jobs/1\n\n% ===== letter.tex =====\nLETTER A'
const all=`${cv}\n\n% ===== letter.tex =====\nLETTER A`
const parts={cv,letter}
const noop=async()=>true

afterEach(()=>vi.unstubAllGlobals())

describe('Copy TeX choice (AC1/AC2)',()=>{
  it('offers Both, CV only and Letter only next to the button when both documents exist',()=>{
    const html=renderToStaticMarkup(<CopyTexAction tex={all} parts={parts} onCopy={noop}/>)
    expect(html).toContain('<select')
    expect(html).toContain('aria-label="TeX to copy"')
    expect(html.match(/<option/g)?.length).toBe(3)
    for(const label of ['Both','CV only','Letter only'])expect(html).toContain(`>${label}</option>`)
    expect(html).toContain('aria-label="Copy generated TeX files"')
  })
  it('keeps the single button with one document, no parts field, or an empty part',()=>{
    for(const p of [{cv},{letter},undefined,{cv,letter:''}]){
      const html=renderToStaticMarkup(<CopyTexAction tex={all} parts={p} onCopy={noop}/>)
      expect(html).not.toContain('<select')
      expect(html).toContain('aria-label="Copy generated TeX files"')
    }
    expect(hasTexChoice({cv})).toBe(false);expect(hasTexChoice(parts)).toBe(true)
  })
  it('each choice copies exactly that TeX through the clipboard',async()=>{
    const writeText=vi.fn(async()=>{});vi.stubGlobal('navigator',{clipboard:{writeText}})
    const expected:Record<TexChoice,string>={both:all,cv,letter}
    for(const choice of ['both','cv','letter'] as TexChoice[]){
      expect(await copyToClipboard(texForChoice(all,parts,choice))).toBe(true)
      expect(writeText).toHaveBeenLastCalledWith(expected[choice])
    }
    expect(texForChoice(all,{cv},'letter')).toBe(all)
  })
  it('parts come from the same source as the full TeX',()=>{
    expect(cvClipboardParts({clipboard_tex:'T',clipboard_tex_parts:parts},{clipboard_tex_parts:{cv:'old'}})).toBe(parts)
    expect(cvClipboardParts({},{clipboard_tex:'P',clipboard_tex_parts:parts})).toBe(parts)
    expect(cvClipboardParts(null,null)).toBeUndefined()
  })
})

describe('wiring (AC1/AC3/AC4)',()=>{
  const gen=appSource.slice(appSource.indexOf('export function CvGenerator'),appSource.indexOf('function BatchCvGenerator'))
  const batch=appSource.slice(appSource.indexOf('function BatchCvGenerator'),appSource.indexOf('type NoteTable'))
  it('single-job panel passes the parts and keeps them on refresh',()=>{
    expect(gen).toContain('const clipboardParts=cvClipboardParts(task,preview)')
    expect(gen).toContain('<CopyTexAction tex={clipboardTex} parts={clipboardParts}')
    expect(gen).toContain('clipboard_tex_parts:p.clipboard_tex_parts')
  })
  it('bulk rows offer the same choice',()=>{
    expect(batch).toContain('<CopyTexAction tex={row.clipboard_tex} parts={row.clipboard_tex_parts} disabled={!row.clipboard_tex} onCopy={text=>copyRowTex(row,text)}/>')
  })
  it('the automatic copy after a run still copies everything',()=>{
    expect(gen).toContain('await copyTex(current.clipboard_tex))flashTexCopied()')
  })
})
