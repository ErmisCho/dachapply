// TASK-286. Rendered with react-dom/server like appPanels.test.tsx: no DOM in this vitest run (TASK-177).
import {afterEach,describe,expect,it,vi} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {MemoryRouter} from 'react-router-dom'
import {ApplicationPace,FunnelPanel,TileJobs,storedHiddenPanels,storedPanelOrder} from './App'

afterEach(()=>vi.unstubAllGlobals())
const counts={applications:4,interviews:1,offers:0,applied_to_interview_rate:25,interview_to_offer_rate:0}
const stats={funnel:{recent_window_days:90,recent_window_start:'2026-07-16',all_time:counts,recent:counts,interviews_without_application:0},month_week_applications:[{label:'1st week',range:'1-7 Oct',start:'2026-10-01',count:2}],workday_applications:[{label:'01 Oct',date:'2026-10-01',count:2}]}

describe('board vs Stats page split (TASK-286 AC2)',()=>{
  it('the board funnel is all-time only, the Stats one is the recent window only',()=>{
    const board=renderToStaticMarkup(<FunnelPanel stats={stats}/>),page=renderToStaticMarkup(<FunnelPanel stats={stats} recent/>)
    expect(board).toContain('All time');expect(board).not.toContain('Last 90 days')
    expect(page).toContain('Last 90 days');expect(page).not.toContain('All time')
  })
  it('the board pace panel has the workday chart only, the Stats one the weeks chart only',()=>{
    const board=renderToStaticMarkup(<ApplicationPace stats={stats}/>),page=renderToStaticMarkup(<ApplicationPace stats={stats} weeks/>)
    expect(board).toContain('Month by workday');expect(board).not.toContain('Weeks this month')
    expect(page).toContain('Weeks this month');expect(page).not.toContain('Month by workday')
  })
})

describe('tiles name their jobs (TASK-286 AC5)',()=>{
  const render=(rows:any[])=>renderToStaticMarkup(<MemoryRouter><TileJobs rows={rows}/></MemoryRouter>)
  it('lists an interview with its round, linking to the job',()=>{
    const html=render([{id:7,company:'Acme',title:'Engineer (m/w/d)',interview_stage:2,interview_total:4}])
    expect(html).toContain('href="/jobs/7"');expect(html).toContain('Acme');expect(html).toContain('Engineer');expect(html).toContain('round 2/4')
  })
  it('lists a due follow-up with job status and due date, linking to the job (not the follow-up)',()=>{
    const html=render([{job:9,company:'Beta',title:'Analyst',status:'applied',follow_up_date:'2026-10-10'}])
    expect(html).toContain('href="/jobs/9"');expect(html).toContain('Beta');expect(html).toContain('Applied, due 2026-10-10')
  })
  it('renders nothing for no rows',()=>{expect(render([])).toBe('')})
})

describe('saved panel state naming removed panels (TASK-286 AC6)',()=>{
  it('drops stall and source_effectiveness from a saved order and hidden list',()=>{
    const store:Record<string,string>={dachapply_dashboard_panel_order:JSON.stringify(['stall','funnel','source_effectiveness','total']),dachapply_dashboard_panel_hidden:JSON.stringify(['source_effectiveness','stall','total']),dachapply_dashboard_panel_defaults_seeded:JSON.stringify(['mailbox_unmatched'])}
    vi.stubGlobal('localStorage',{getItem:(k:string)=>store[k]??null,setItem:(k:string,v:string)=>{store[k]=v}})
    const order=storedPanelOrder()
    expect(order).not.toContain('stall');expect(order).not.toContain('source_effectiveness')
    expect(order.slice(-2)).toEqual(['funnel','total'])
    expect(storedHiddenPanels()).toEqual(['total'])
  })
})
