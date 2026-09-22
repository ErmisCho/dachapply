// TASK-244. The bug was not a colour, it was a SURFACE: a panel inside the CV generation window
// painted its own light background and nothing darkened it, so in dark mode every `.dark` rule
// inside it coloured text for a dark background that was not there. Measured in headless Chrome
// against the built stylesheet, reading the painted pixel: an error on that panel was 1.43:1.
//
// What makes it a trap rather than a one-off is the mechanism. index.css keeps the whole app dark
// with blanket rules of the form `.dark .bg-white{...!important}`, which match a literal CLASS. An
// opacity-suffixed sibling -- `bg-white/70`, `bg-white/95`, `bg-slate-100/80` -- is a DIFFERENT
// class, so it slips past the blanket rule and stays light while the document carries `.dark`. You
// cannot see that by reading the element; you have to ask whether anything covers its class.
//
// So these tests do not assert a contrast number (no DOM here -- no jsdom, no @testing-library,
// TASK-177 forbids adding one; the ratios are measured in a browser and live in the task notes).
// They assert the invariant underneath it: every light surface in src/ is darkened by SOMETHING,
// and the ones that are not are a short, named list. Add a new white island anywhere in this app
// and the last test goes red with its file and line.
import {describe,expect,it} from 'vitest'
// @ts-expect-error -- this frontend ships no @types/node, but vitest runs this file on node
import {readFileSync,readdirSync,statSync} from 'node:fs'

const src=new URL('.',import.meta.url)
const css=readFileSync(new URL('index.css',src),'utf8')

const files:string[]=[]
;(function walk(dir:URL){
  for(const name of readdirSync(dir)){
    const child=new URL(name+(statSync(new URL(name,dir)).isDirectory()?'/':''),dir)
    if(child.href.endsWith('/'))walk(child)
    else if(/\.tsx?$/.test(name)&&!/\.test\./.test(name))files.push(child.href)
  }
})(src)

// A light surface: white, or a 50/100-level tint, with or without an opacity suffix.
const LIGHT=/^bg-(white|slate-50|slate-100|gray-50|gray-100|zinc-50|neutral-50|stone-50|(?:red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-(?:50|100))(\/\d+)?$/
const hasBlanketRule=(cls:string)=>
  new RegExp('\\.dark\\s+[^{}]*\\.'+cls.replace(/[/]/g,'\\\\/')+'[,{\\s]').test(css)

type Surface={file:string;line:number;cls:string;covered:boolean;snippet:string}
const surfaces:Surface[]=[]
for(const href of files){
  // Comments are blanked (not deleted, so line numbers still point at the real thing): this file's
  // own prose quotes class names like `bg-white/70`, and a scanner that read its own explanation
  // would report a surface nobody renders.
  const text=readFileSync(new URL(href),'utf8')
    .replace(/\/\*[\s\S]*?\*\//g,m=>m.replace(/[^\n]/g,' '))
    .split('\n').map((l:string)=>/^\s*\/\//.test(l)?'':l).join('\n')
  for(const m of text.matchAll(/["'`]([^"'`\n]*\bbg-[a-z0-9/-]+[^"'`\n]*)["'`]/g)){
    const classes=m[1].split(/\s+/)
    const light=classes.filter(c=>LIGHT.test(c))
    if(!light.length)continue
    // Two things can darken it: a `dark:bg-*` utility on the element itself (the house pattern --
    // see the Nav account menu and the guided-tour card), or a blanket `.dark .<class>` rule.
    const ownDark=classes.some(c=>/^dark:bg-/.test(c))
    const cls=(c:string)=>{
      // `.btn`/`.btn-primary`/`.btn-danger`/`.btn-muted` and `thead` carry their own `.dark` rules
      // with !important, which beat the utility regardless of the bg-* class the element also has.
      const viaComponent=classes.some(c2=>/^btn(-|$)/.test(c2))
      return ownDark||hasBlanketRule(c)||viaComponent
    }
    for(const c of light)surfaces.push({
      file:href.slice(href.indexOf('/src/')+1),line:text.slice(0,m.index).split('\n').length,
      cls:c,covered:cls(c),snippet:m[1].slice(0,90)})
  }
}

describe('light surfaces in dark mode (TASK-244)',()=>{
  it('found the surfaces at all, rather than an empty list that would pass by accident',()=>{
    expect(files.length).toBeGreaterThan(3)
    expect(surfaces.length).toBeGreaterThan(100)
    expect(surfaces.some(s=>s.cls==='bg-white')).toBe(true)
  })

  it('darkens the two panels inside the CV generation window that paint their own surface',()=>{
    // These are the regression. Both used a bare `bg-white/70`: CorrectionInput's drop zone (whose
    // image error renders as `text-red-700`, which `.dark` turns into #fecaca) and the Adjust-model
    // picker. Neither is matched by `.dark .bg-white`, so each needed its own dark variant.
    const app=readFileSync(new URL('App.tsx',src),'utf8')
    expect(app).toContain('border-dashed border-blue-200 bg-white/70 p-2 dark:bg-slate-950/70')
    expect(app).toContain('border border-blue-200 bg-white/70 px-2 py-1.5 dark:bg-slate-950/70')
    // ...and the fix is on the surface, not on the message: the error stays a plain text-red-700 <p>
    // with no popup-scoped colour override invented for it, and the shared .field-error-message
    // colour is still the app's single one rather than one colour per window.
    expect(app).toContain('<p className="mt-2 text-xs text-red-700">{imageError}</p>')
    expect(css.match(/\.field-error-message\{/g)?.length).toBe(2)        // the rule, and its .dark one
    expect(css.match(/\.dark \.field-error-message\{/g)?.length).toBe(1)
  })

  it('leaves the window shell alone, because the blanket rule already covers it',()=>{
    // The shell uses the literal `bg-white` class, so `.dark .bg-white{...!important}` darkens it
    // and an error on it measured 14.34:1 before this task changed anything. A `dark:` variant here
    // would be inert -- the blanket rule is !important and beats a utility of equal specificity --
    // so adding one would look like a fix while doing nothing.
    expect(css).toMatch(/\.dark \.bg-white\{background-color:[^}]*!important\}/)
    const shell=surfaces.filter(s=>s.snippet.includes('absolute left-0 top-10 z-40'))
    expect(shell.length).toBe(1)
    expect(shell[0].covered).toBe(true)
  })

  it('has no light surface left that nothing darkens, outside this named list',()=>{
    // Everything this scan cannot account for, with the reason. The first two are real open cases
    // reported for their own tasks rather than fixed here (TASK-244 is the CV window); the third is
    // covered by a rule keyed on an element, which a class-keyed scan cannot see. A class arriving
    // that is NOT on this list is a new white island: darken the surface, or add it here with a
    // reason someone can check.
    const known={
      'bg-white/95':'ExportChoice popup -- OPEN, measured 1.07:1 in dark mode (#fafafa on #f2f2f2)',
      'bg-slate-100/80':'archived board row -- OPEN, measured 1.20:1 dark and 2.28:1 light',
      'bg-slate-50/80':'the desktop job-table <thead>, already repainted by `.dark .job-table thead th`',
    }
    const open=[...new Set(surfaces.filter(s=>!s.covered).map(s=>s.cls))].sort()
    expect(open).toEqual(Object.keys(known).sort())
  })
})
