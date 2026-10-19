// TASK-315. Board table columns reorder from the Columns picker, saved in this browser only.
// Rendered with react-dom/server like boardDeclutter.test.tsx: no DOM in this vitest run (TASK-177).
import {afterEach,describe,expect,it,vi} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {BoardHeadRow,SkeletonTableRows,columnKeys,storedColumnOrder} from './App'
import {movePanelInOrder,reorderPanels} from './appUtils'

afterEach(()=>vi.unstubAllGlobals())
const stubStore=(store:Record<string,string>)=>vi.stubGlobal('localStorage',{getItem:(k:string)=>store[k]??null,setItem:(k:string,v:string)=>{store[k]=v}})
const colOrder=(html:string)=>[...html.matchAll(/class="col-(\w+)/g)].map(m=>m[1])

describe('saved column order (TASK-315)',()=>{
  it('drops unknown and duplicate keys and appends missing columns in default order',()=>{
    stubStore({dachapply_column_order:JSON.stringify(['skills','bogus','prio','skills'])})
    expect(storedColumnOrder()).toEqual(['skills','prio',...columnKeys.filter(k=>k!=='skills'&&k!=='prio')])
  })
  it('falls back to the default order for nothing saved or unreadable JSON',()=>{
    stubStore({})
    expect(storedColumnOrder()).toEqual(columnKeys)
    stubStore({dachapply_column_order:'{oops'})
    expect(storedColumnOrder()).toEqual(columnKeys)
  })
})

describe('reordering columns (TASK-315)',()=>{
  it('drag drops the column next to its target and the arrows swap neighbours',()=>{
    expect(reorderPanels(columnKeys,'addedby','prio').slice(0,2)).toEqual(['addedby','prio'])
    expect(reorderPanels(columnKeys,'prio','fit').slice(0,2)).toEqual(['fit','prio'])
    expect(movePanelInOrder(columnKeys,[],'fit',-1).slice(0,2)).toEqual(['fit','prio'])
    expect(movePanelInOrder(columnKeys,[],'prio',-1)).toBe(columnKeys)
  })
})

describe('board table follows the stored order (TASK-315)',()=>{
  it('renders the header and skeleton cells in the stored order, select column first',()=>{
    stubStore({dachapply_column_order:JSON.stringify(['skills','status','prio'])})
    const order=storedColumnOrder()
    const head=renderToStaticMarkup(<table><thead><BoardHeadRow order={order} sortInfo={()=>null} onSort={()=>{}}/></thead></table>)
    expect(colOrder(head)).toEqual(order)
    expect(order.slice(0,3)).toEqual(['skills','status','prio'])
    expect(head.indexOf('Select')).toBeLessThan(head.indexOf('Skills'))
    expect(head.indexOf('Skills')).toBeLessThan(head.indexOf('Status column'))
    const rows=renderToStaticMarkup(<table><tbody><SkeletonTableRows order={order}/></tbody></table>)
    expect(colOrder(rows).slice(0,order.length)).toEqual(order)
  })
})
