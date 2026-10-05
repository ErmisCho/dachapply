// TASK-268. The filter card (z-50) painted over the CV popup (z-40): both sat in the root stacking
// context and the page surface simply had the bigger number. One named scale in index.css fixes the
// order once; these tests pin it and stop a raw z-index from sneaking back in beside it.
import {describe,expect,it} from 'vitest'
import appSource from './App.tsx?raw'
// @ts-expect-error -- this frontend ships no @types/node, but vitest runs this file on node
import {readFileSync} from 'node:fs'

const css=readFileSync(new URL('./index.css',import.meta.url),'utf8')   // ?raw is stubbed empty for CSS

const scale=Object.fromEntries([...css.matchAll(/--z-([a-z-]+):(-?\d+)/g)].map(m=>[m[1],Number(m[2])]))

describe('layering scale (TASK-268)',()=>{
  it('orders page < raised < sticky < dropdown < popup < popup-menu < toast < tour',()=>{
    const order=['base','raised','sticky','dropdown','popup','popup-menu','toast','tour']
    expect(Object.keys(scale).sort()).toEqual([...order].sort())
    order.slice(1).forEach((k,i)=>expect(scale[k]).toBeGreaterThan(scale[order[i]]))
  })

  it('uses only the scale in App.tsx and index.css',()=>{
    expect(appSource.match(/\bz-(?:\d+|\[\d+\])(?=[\s"'`])/g)).toBeNull()
    const used=[...appSource.matchAll(/z-\[var\(--z-([a-z-]+)\)\]/g)].map(m=>m[1])
    expect(used.length).toBeGreaterThan(20)
    used.forEach(k=>expect(scale).toHaveProperty(k))
    // the only literal left is the -1 page backdrop behind everything
    expect([...css.matchAll(/z-index:\s*(-?\d+)/g)].map(m=>m[1])).toEqual(['-1'])
  })

  it('puts every dialog on the popup layer and the filter card below it',()=>{
    const dialogs=appSource.match(/fixed inset-[^"]*?z-\[var\(--z-[a-z-]+\)\]/g)||[]
    expect(dialogs.length).toBeGreaterThanOrEqual(10)
    const off=dialogs.filter(d=>!/--z-(popup|toast|tour)\)/.test(d))
    expect(off).toEqual([])
    expect(appSource).toContain('premium-card relative z-[var(--z-raised)] mb-4')
    expect(appSource).toContain('fixed inset-x-0 top-3 z-[var(--z-popup)]')
  })
})
