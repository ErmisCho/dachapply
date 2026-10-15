// TASK-295: the board's actions (Analyze N new jobs, its picker, + Add job) render in the top navbar
// on desktop and in the account menu below that width -- one copy, never both. Dashboard publishes
// them through setNavActions; the click behaviour and the phone menu are checked in the browser.
import {afterEach,describe,expect,it,vi} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {MemoryRouter} from 'react-router-dom'
import {AnalyzeActions,Nav,setNavActions} from './App'

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

// TASK-298: Analyze N new jobs is gone at 0 (bar and menu); on desktop hover/focus opens the one-job list
// and a click still analyzes all; the phone menu keeps a tap path (<details>) to the one-job choice.
// No DOM in this suite, so the handlers are called straight off the returned element tree.
function props(phone:boolean,count=2,open=false){return {count,jobs:[{id:7,url:'https://a'},{id:9,url:''}],phone,open,setOpen:vi.fn(),close:vi.fn(),analyzeAll:vi.fn(),analyzeOne:vi.fn()}}
const html=(p:any)=>renderToStaticMarkup(<MemoryRouter><AnalyzeActions {...p}/></MemoryRouter>)
describe('TASK-298 analyze button',()=>{
  it('renders nothing at 0 new jobs, in the bar and in the menu',()=>{
    expect(html(props(false,0,true))).toBe('')
    expect(html(props(true,0))).toBe('')
    expect(html(props(false))).toContain('Analyze 2 new jobs')
  })
  it('desktop: no separate picker button; hover and focus open the list, leaving closes it after a delay',()=>{
    vi.useFakeTimers()
    const p=props(false);const el:any=AnalyzeActions(p)
    expect(html(p)).not.toContain('Choose one new job')
    expect(html(p)).not.toContain('data-analyze-one="list"')
    el.props.onMouseEnter();expect(p.setOpen).toHaveBeenLastCalledWith(true)
    el.props.onMouseLeave();expect(p.setOpen).toHaveBeenCalledTimes(1)
    el.props.onMouseEnter();vi.advanceTimersByTime(1000);expect(p.setOpen).toHaveBeenCalledTimes(2)
    el.props.onMouseLeave();vi.advanceTimersByTime(1000);expect(p.setOpen).toHaveBeenLastCalledWith(false)
    const q=props(false);(AnalyzeActions(q) as any).props.onFocus();expect(q.setOpen).toHaveBeenCalledWith(true)
    vi.useRealTimers()
  })
  it('desktop: the open list picks one job, the button click analyzes all',()=>{
    const p=props(false,2,true);expect(html(p)).toMatch(/data-analyze-one="list".*#7 https:\/\/a.*#9 No URL/)
    const el:any=AnalyzeActions(p);const[button,list]=el.props.children
    button.props.onClick();expect(p.analyzeAll).toHaveBeenCalledTimes(1);expect(p.analyzeOne).not.toHaveBeenCalled()
    list.props.children[1][1].props.onClick();expect(p.analyzeOne).toHaveBeenCalledWith(9)
  })
  it('phone: the one-job list is reachable by tap inside a <details>',()=>{
    const p=props(true);expect(html(p)).toMatch(/Analyze 2 new jobs.*<details><summary[^>]*>Analyze one new job.*#7 https:\/\/a.*#9 No URL.*<\/details>/)
  })
})
