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

const luminance=(hex:string)=>{
  const channels=hex.match(/[\da-f]{2}/gi)!.map(value=>parseInt(value,16)/255)
    .map(value=>value<=.04045?value/12.92:((value+.055)/1.055)**2.4)
  return .2126*channels[0]+.7152*channels[1]+.0722*channels[2]
}
const contrast=(foreground:string,background:string)=>{
  const [lighter,darker]=[luminance(foreground),luminance(background)].sort((a,b)=>b-a)
  return (lighter+.05)/(darker+.05)
}

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
    // colour remains shared rather than one override per window; TASK-247 adds one page-level rule.
    expect(app).toContain('<p className="mt-2 text-xs text-red-700">{imageError}</p>')
    expect(css.match(/\.field-error-message\{/g)?.length).toBe(3)        // base, page-level, dark
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

  it('darkens the two light islands TASK-244 found and left open (TASK-245)',()=>{
    // The other two ends of the same mechanism, closed by TASK-245. Both were measured in headless
    // Chrome on the REAL ancestor chains (the export card / the `.job-table` inside `.premium-card`),
    // reading the painted pixel, never an assumed colour:
    //
    //   ExportChoice popup   its text-slate-900 (#fafafa) on the popup   1.07 -> 19.34  dark
    //                                                                   17.85 -> 17.85  light
    //   archived board row   its inherited row text on the row          1.48 -> 10.82  dark
    //                                                                   2.38 ->  7.05  light
    const app=readFileSync(new URL('App.tsx',src),'utf8')
    expect(app).toContain('bg-white/95 p-2 text-slate-900 shadow-2xl ring-1 ring-slate-900/5 backdrop-blur dark:bg-slate-950/95')
    expect(app).toContain('"bg-slate-100/80 text-slate-600 dark:bg-slate-800/80 "')

    // The row's `opacity-75` is gone deliberately, and the reason is a measurement, not taste. In the
    // live board it was INERT: `.job-table tbody tr` carries `animation:board-row-in .18s ease-out
    // both`, whose keyframes end at `opacity:1`, and an animation-origin value outranks a normal
    // declaration -- so every row is pinned at full opacity once the 180ms is up. It came back only
    // under `prefers-reduced-motion`, where that rule is `animation:none`, and there it made the row
    // WORSE (1.42:1 dark / 1.86:1 light, against 1.48 / 2.38 with motion). Re-adding it would put
    // reduced-motion users back under AA while looking like it does nothing to everyone else.
    expect(app).not.toContain('opacity-75')
  })

  it('keeps the two TASK-247 text pairs above AA without changing their passing siblings',()=>{
    const app=readFileSync(new URL('App.tsx',src),'utf8')

    // Only the stale branch changes shade. Its dark-mode values come from the existing blanket rules.
    expect(app).toContain('(isStaleStatus(j)||isStaleUnapplied(j))?"bg-slate-100 text-slate-600 ":""')
    expect(contrast('#475569','#f1f5f9')).toBeGreaterThanOrEqual(4.5)
    expect(contrast('#d4d4d8','#18181b')).toBeGreaterThanOrEqual(4.5)

    // Nested ErrorBoxes keep the shared brand red; only a bare page-level box gets the darker shade.
    expect(css).toContain('.field-error-message{display:flex;align-items:center;gap:.5rem;color:#e60023;')
    expect(css).toContain('main > .field-error-message{color:#dc0021}')
    expect(contrast('#dc0021','#f3f6fe')).toBeGreaterThanOrEqual(4.5)
    expect(contrast('#dc0021','#eef2ff')).toBeGreaterThanOrEqual(4.5)
    expect(contrast('#e60023','#ffffff')).toBeGreaterThanOrEqual(4.5)
    expect(contrast('#e60023','#f8fafc')).toBeGreaterThanOrEqual(4.5)
  })

  it('has no light surface left that nothing darkens, outside this named list',()=>{
    // Everything this scan cannot account for, with the reason. What is left is covered by a rule
    // keyed on an ELEMENT, which a class-keyed scan cannot see. A class arriving that is NOT on this
    // list is a new white island: darken the surface, or add it here with a reason someone can check.
    // (TASK-244 listed two more here as open-and-reported; TASK-245 fixed both, so they are gone.)
    const known={
      'bg-slate-50/80':'the desktop job-table <thead>, already repainted by `.dark .job-table thead th`',
    }
    const uncovered=surfaces.filter(s=>!s.covered)
    const open=[...new Set(uncovered.map(s=>s.cls))].sort()
    // The message matters as much as the assertion: an array diff of class names tells you WHAT
    // slipped past the blanket rules but not WHERE, and this scanner exists precisely because you
    // cannot find these by reading the element.
    const where=uncovered.map(s=>`  ${s.file}:${s.line}  ${s.cls}  in  ${s.snippet}`).join('\n')
    expect(open,`light surfaces nothing darkens:\n${where}`).toEqual(Object.keys(known).sort())
  })
})
