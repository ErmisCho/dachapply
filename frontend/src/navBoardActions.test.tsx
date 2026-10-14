// TASK-295: the board's actions (Analyze N new jobs, its picker, + Add job) render in the top navbar
// on desktop and in the account menu below that width -- one copy, never both. Dashboard publishes
// them through setNavActions; the click behaviour and the phone menu are checked in the browser.
import {afterEach,describe,expect,it,vi} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {MemoryRouter} from 'react-router-dom'
import {Nav,setNavActions} from './App'

function render(desktop:boolean){
  vi.stubGlobal('localStorage',{getItem:(k:string)=>k==='dachapply_user'?JSON.stringify({username:'owner'}):null,setItem:()=>{},removeItem:()=>{}})
  vi.stubGlobal('window',{matchMedia:()=>({matches:desktop,addEventListener:()=>{},removeEventListener:()=>{}})})
  return renderToStaticMarkup(<MemoryRouter><Nav/></MemoryRouter>)
}
afterEach(()=>{setNavActions(null);vi.unstubAllGlobals()})

describe('TASK-295 navbar board actions',()=>{
  it('shows the published actions in the desktop navbar',()=>{
    setNavActions(phone=><><button>Analyze 3 new jobs</button><a href="/add">+ Add job{phone?' (menu)':''}</a></>)
    const html=render(true)
    expect(html).toMatch(/data-board-actions="bar".*Analyze 3 new jobs.*\+ Add job</)
  })
  it('keeps them out of the bar below desktop (they live in the account menu) and when unpublished',()=>{
    setNavActions(()=><button>Analyze 3 new jobs</button>)
    expect(render(false)).not.toContain('Analyze 3 new jobs')
    setNavActions(null)
    expect(render(true)).not.toContain('data-board-actions')
  })
})
