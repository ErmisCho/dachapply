// TASK-309. The "N selected" action bar sticks below the nav while rows are selected, sits just under
// the filter card's layer (so its open dropdowns stay on top) and the desktop board box shrinks by the
// bar's measured height so the table's sticky header is never under the bar.
import {describe,expect,it} from 'vitest'
import appSource from './App.tsx?raw'
// @ts-expect-error -- this frontend ships no @types/node, but vitest runs this file on node
import {readFileSync} from 'node:fs'

const css=readFileSync(new URL('./index.css',import.meta.url),'utf8')   // ?raw is stubbed empty for CSS

describe('sticky selection bar (TASK-309)',()=>{
  it('pins the bar below the nav, under the filter card layer',()=>{
    expect(appSource).toContain('{selected.length>0&&<div ref={selectionBarRef} className="md:sticky md:top-[3.3rem] md:z-[calc(var(--z-raised)_-_1)] lg:top-[2.3rem] mb-4 flex flex-wrap')
  })
  it('shrinks the desktop board box by the measured bar height',()=>{
    expect(appSource).toContain("root.setProperty('--selection-bar-h',el.offsetHeight+'px')")
    expect(css).toContain('.job-table-scroll{max-height:calc(100vh - 7rem - var(--selection-bar-h, 0px));overflow-y:auto}')
  })
})
