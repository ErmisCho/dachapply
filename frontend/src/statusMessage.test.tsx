// TASK-243. The status banners were a second visual language: a gradient card, a 0 10px 30px drop
// shadow and a 1.55rem FILLED disc with its own coloured glow, while the same app already showed
// field errors as flat text with a 1.35rem OUTLINED glyph. These tests pin the quieting so it cannot
// drift back: the glyph is the thing that carries meaning without colour, and the stylesheet rules
// below are the ones that made a one-line message look like a card.
//
// This vitest run has no DOM (no jsdom, no @testing-library) and TASK-177 forbids adding one, so
// these read the emitted markup and the stylesheet text. Rendered heights are measured in a browser
// against the built CSS; those numbers live in the task notes, not here.
import {describe,expect,it} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {StatusMessage,SuccessMessage,LearnedPreferenceNote} from './App'
// @ts-expect-error -- this frontend ships no @types/node, but vitest runs this file on node
import {readFileSync} from 'node:fs'

// `./index.css?raw` is not usable here: vitest stubs CSS imports and hands back an empty string, so
// the stylesheet is read off disk instead. The test environment is node, which makes that free.
const css=readFileSync(new URL('./index.css',import.meta.url),'utf8')

const rules=new Map<string,string[]>()
for(const[,selector,body]of css.replace(/\/\*[\s\S]*?\*\//g,'').matchAll(/([^{}]+)\{([^{}]*)\}/g)){
  for(const one of selector.split(','))rules.set(one.trim(),body.split(';').map(d=>d.trim()).filter(Boolean))
}
const statusRules=[...rules].filter(([selector])=>selector.includes('status-message'))
const declarations=(selector:string)=>rules.get(selector)??[]

describe('status message stylesheet (TASK-243)',()=>{
  it('lifts nothing off the page: no drop shadow and no gradient on any status rule',()=>{
    expect(statusRules.length).toBeGreaterThan(8)   // the filter found the block, not nothing
    const loud=statusRules.filter(([,body])=>body.some(d=>/^(box-shadow|filter)\b/.test(d)||/gradient/.test(d)))
    expect(loud.map(([selector])=>selector)).toEqual([])
  })

  it('draws the icon exactly like the field-error glyph the app already uses',()=>{
    // AC2. Identical declarations, not merely "similar": if the disc and its glow come back, this
    // fails. .field-error-icon is the house pattern (index.css:13) and stays the reference.
    expect([...declarations('.status-message-icon')].sort()).toEqual([...declarations('.field-error-icon')].sort())
    expect(declarations('.status-message-icon')).toContain('border:1.8px solid currentColor')
    expect(declarations('.status-message-icon')).toContain('height:1.35rem')
  })

  it('keeps no accent or glow variables to re-fill the disc from',()=>{
    expect(css).not.toContain('--status-glow')
    expect(css).not.toContain('--status-accent')
  })

  it('still gives every tone its own colour in both modes',()=>{
    // AC3/AC5. Quieting must not collapse the tones into one another, in either theme.
    for(const tone of['error','success','info']){
      expect(declarations('.status-message-'+tone).join(';')).toMatch(/color:#/)
      expect(declarations('.dark .status-message-'+tone).join(';')).toMatch(/color:#/)
    }
  })
})

describe('status message markup (TASK-243)',()=>{
  const html=(node:any)=>renderToStaticMarkup(node)

  it('distinguishes the three tones by glyph, not only by colour',()=>{
    // AC3. A screen reader gets the role; a colour-blind reader gets the glyph.
    expect(html(<StatusMessage tone="success">done</StatusMessage>)).toContain('>✓</span>')
    expect(html(<StatusMessage tone="info">note</StatusMessage>)).toContain('>i</span>')
    expect(html(<StatusMessage tone="error">bad</StatusMessage>)).toContain('>!</span>')
  })

  it('leaves the announcement semantics alone',()=>{
    expect(html(<StatusMessage tone="error">bad</StatusMessage>)).toContain('role="alert"')
    expect(html(<StatusMessage tone="success">done</StatusMessage>)).toContain('role="status"')
    expect(html(<StatusMessage tone="info">note</StatusMessage>)).toContain('role="status"')
    expect(html(<StatusMessage tone="success">done</StatusMessage>)).toContain('aria-hidden="true"')
  })

  it('renders every call-site shape: compact, title, list and pre children',()=>{
    // AC4. These are the distinct shapes the 54 call sites use; each keeps its icon and its body
    // wrapper, which is what the padding and min-width rules hang off.
    expect(html(<SuccessMessage message="Notes saved." compact/>)).toContain('class="status-message-compact status-message status-message-success"')
    expect(html(<SuccessMessage message="Notes saved."/>)).toContain('class="status-message status-message-success"')
    const titled=html(<SuccessMessage title="Import successful"><ol><li>one</li></ol></SuccessMessage>)
    expect(titled).toContain('<div class="status-message-title">Import successful</div>')
    expect(titled).toContain('<div class="status-message-body"><ol><li>one</li></ol></div>')
    expect(html(<SuccessMessage title="Import summary"><pre>{'{}'}</pre></SuccessMessage>)).toContain('<div class="status-message-body"><pre>{}</pre></div>')
    expect(html(<SuccessMessage message=""/>)).toBe('')   // empty message still renders nothing
  })

  it('renders the CV window pair the owner complained about as two compact messages',()=>{
    // The screenshot: a success above an info, stacked inside the popup. Both compact, both flat.
    const both=html(<><SuccessMessage message="Generated TeX files copied to clipboard." compact/><LearnedPreferenceNote task={{learned_preference:true,learned_preference_exclusion:true}}/></>)
    expect(both).toContain('status-message-compact status-message status-message-success')
    expect(both).toContain('status-message-compact status-message status-message-info')
    expect(declarations('.status-message-compact')).toContain('width:fit-content')   // each on its own line, hugging its text
    expect(declarations('.status-message+.status-message')).toContain('margin-top:.4rem')
  })
})
