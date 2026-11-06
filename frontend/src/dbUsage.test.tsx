// TASK-356: the owner's database usage, as the Stats panel and the board's compact line show it.
import {describe,expect,it} from 'vitest'
import app from './App.tsx?raw'
import {renderToStaticMarkup} from 'react-dom/server'
import {DbUsageLineView,DbUsageView,type DbUsage} from './DbUsage'

const usage:DbUsage={configured:true,checked_at:'2026-11-06T10:00:00Z',error:'',period:{start:'2026-11-01',end:'2026-12-01'},metrics:{
  transfer:{label:'Transfer',used:1.2,limit:5,unit:'GB',percent:24},
  compute:{label:'Compute',used:null,limit:100,unit:'hours',percent:null},
  storage:{label:'Storage',used:.25,limit:1,unit:'GB',percent:25}}}

describe('database usage',()=>{
  it('shows used, limit and percent per metric, and when it was checked',()=>{
    for(const html of [renderToStaticMarkup(<DbUsageView usage={usage}/>),renderToStaticMarkup(<DbUsageLineView usage={usage}/>)]){
      expect(html).toContain('1.2 of 5 GB (24%)')
      expect(html).toContain('0.25 of 1 GB (25%)')
      expect(html).toContain('Last checked:')
    }
  })
  it('calls a field Neon did not send unknown',()=>{
    expect(renderToStaticMarkup(<DbUsageView usage={usage}/>)).toContain('unknown of 100 hours')
  })
  it('says plainly when it is not configured',()=>{
    for(const html of [renderToStaticMarkup(<DbUsageView usage={{configured:false}}/>),renderToStaticMarkup(<DbUsageLineView usage={{configured:false}}/>)])
      expect(html).toContain('not configured')
  })
  it('shows a failed check and before the first check says so',()=>{
    const html=renderToStaticMarkup(<DbUsageView usage={{configured:true,error:'Neon answered 401',checked_at:null,metrics:null}}/>)
    expect(html).toContain('Last check failed: Neon answered 401')
    expect(html).toContain('Last checked: not yet')
  })
  it('renders nothing on the board until the account has an answer',()=>{
    expect(renderToStaticMarkup(<DbUsageLineView usage={null}/>)).toBe('')
  })
  it('is gated on the flag only that account gets, on both surfaces',()=>{
    expect(app).toContain('currentUser?.can_view_db_usage&&<DbUsageLine/>')
    expect(app).toContain('storedUser()?.can_view_db_usage&&<DbUsagePanel/>')
  })
})
