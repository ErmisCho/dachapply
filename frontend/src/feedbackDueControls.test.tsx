import {describe,expect,it,vi} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {FeedbackDueRow,updateFeedbackDueJob} from './App'
import type {FeedbackDueRow as FeedbackRow} from './types'

const row:FeedbackRow={id:208,company:'Synthetic GmbH',title:'Backend Engineer',status:'interview',feedback_due_date:'2026-09-09'}
const props=()=>({row,overdue:false,followedUp:false,onGo:vi.fn(),onFollowedUp:vi.fn(),onReschedule:vi.fn(),onStatusChange:vi.fn()})
function elements(node:any,out:any[]=[]):any[]{if(Array.isArray(node)){node.forEach(x=>elements(x,out));return out}if(!node||typeof node!=='object')return out;if(node.type)out.push(node);elements(node.props?.children,out);return out}

describe('feedback deadline row controls (TASK-208)',()=>{
  it('renders reschedule and every real job status for this lead',()=>{
    const html=renderToStaticMarkup(<FeedbackDueRow {...props()}/>)
    expect(html).toContain('Reschedule feedback for Synthetic GmbH — Backend Engineer')
    expect(html).toContain('Change status for Synthetic GmbH — Backend Engineer')
    for(const status of ['new','reviewed','to_apply','applied','interview','offer','accepted','rejected','withdrawn','skipped','archived'])expect(html).toContain(`value="${status}"`)
  })

  it('uses the owner-scoped job PATCH and returns failures without pretending they saved',async()=>{
    const request=vi.fn().mockResolvedValueOnce({...row,status:'offer'}).mockRejectedValueOnce({detail:'synthetic refusal'})

    const success=await updateFeedbackDueJob(row.id,{status:'offer'},request)
    const failure=await updateFeedbackDueJob(row.id,{feedback_due_date:'2026-09-15'},request)

    expect(request).toHaveBeenNthCalledWith(1,'/jobs/208/',{method:'PATCH',body:{status:'offer'}})
    expect(request).toHaveBeenNthCalledWith(2,'/jobs/208/',{method:'PATCH',body:{feedback_due_date:'2026-09-15'}})
    expect(success.updated?.status).toBe('offer')
    expect(success.error).toBeNull()
    expect(failure.updated).toBeNull()
    expect(failure.error).toEqual({detail:'synthetic refusal'})
  })

  it('lets reschedule and status changes run independently or in sequence',()=>{
    const callbacks=props()
    const tree=FeedbackDueRow(callbacks)
    const all=elements(tree)
    const status=all.find(x=>x.type==='select')
    const date=all.find(x=>x.type==='input'&&x.props.type==='date')

    status.props.onChange({target:{value:'interview'}})
    expect(callbacks.onStatusChange).not.toHaveBeenCalled()
    date.props.onBlur({target:{value:'2026-09-15'}})
    status.props.onChange({target:{value:'rejected'}})

    expect(callbacks.onReschedule).toHaveBeenCalledWith('2026-09-15')
    expect(callbacks.onStatusChange).toHaveBeenCalledWith('rejected')
  })
})
