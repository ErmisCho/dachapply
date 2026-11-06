// TASK-355: the job page's prep notes, the option on the Interview row, and the run's place in the queue.
import {describe,expect,it} from 'vitest'
import app from './App.tsx?raw'
import {renderToStaticMarkup} from 'react-dom/server'
import {MemoryRouter} from 'react-router-dom'
import {PrepNotesView,prepNotesAvailable,type PrepNotes} from './InterviewPrep'
import {QueueView,type QueueItem} from './PrepQueue'

const note={id:4,note:'What to study\n- Django\n\nLikely questions\n- Why us?',created_at:'2026-11-06T10:00:00Z'}
const view=(state:PrepNotes|null)=>renderToStaticMarkup(<PrepNotesView state={state} onRun={()=>{}}/>)
const buttons=(html:string)=>[...html.matchAll(/<button[^>]*>([^<]*)<\/button>/g)].map(m=>m[1])

describe('prep notes on the job page',()=>{
  it('offers Prep notes on a job with none',()=>{
    expect(buttons(view({status:'idle',error:'',note:null}))).toEqual(['Prep notes'])
  })
  it('shows the note, both parts, with Regenerate as the only way to replace it',()=>{
    const html=view({status:'ready',error:'',note})
    expect(html).toContain('What to study')
    expect(html).toContain('Likely questions')
    expect(buttons(html)).toEqual(['Regenerate'])
  })
  it.each(['queued','running'] as const)('offers nothing to press while a run is %s',status=>{
    const html=view({status,error:'',note})
    expect(buttons(html)).toEqual([])
    expect(html).toContain('role="status"')
  })
  it('shows a failure inline with Retry, and keeps a note a failed Regenerate did not replace',()=>{
    const html=view({status:'failed',error:'provider down',note})
    expect(html).toContain('role="alert"')
    expect(html).toContain('provider down')
    expect(html).toContain('Likely questions')
    expect(buttons(html)).toEqual(['Retry'])
  })
  it('sends regenerate on Retry only when there is a note to replace',()=>{
    const pressed:boolean[]=[]
    for(const current of [note,null]){
      const element=PrepNotesView({state:{status:'failed',error:'x',note:current},onRun:r=>pressed.push(r)})
      const find=(node:any):any=>node?.type==='button'?node:node?.props?.children&&[node.props.children].flat(9).map(find).find(Boolean)
      find(element).props.onClick()
    }
    expect(pressed).toEqual([true,false])
  })
})

describe('where the option shows',()=>{
  it('is only for a job in Interview on an account that can run a model',()=>{
    expect(prepNotesAvailable({status:'interview'},{can_generate_cv:true})).toBe(true)
    expect(prepNotesAvailable({status:'interview'},{can_generate_cv:false})).toBe(false)  // the deployed site
    expect(prepNotesAvailable({status:'applied'},{can_generate_cv:true})).toBe(false)
    expect(prepNotesAvailable({status:'interview'},null)).toBe(false)
  })
  it('is on both forms of the Interview row',()=>{
    expect(app.match(/prepNotesAvailable\(j,currentUser\)&&<Link/g)).toHaveLength(2)
  })
})

describe('the queue',()=>{
  it('lists a run under Running, linked to its job, with no document controls',()=>{
    const item:QueueItem={job_id:9,company:'ACME',title:'Engineer',job_status:'interview',key:'interview-prep',label:'Writing prep notes',document:null,language:null,status:'running',position:null,progress:0,eta_seconds:null,error:'',files:[],queued_at:null,started_at:null,finished_at:null,retry_at:null,incomplete:false}
    const html=renderToStaticMarkup(<MemoryRouter><QueueView snap={{data:{concurrency:1,items:[item]},error:'',busy:[],failed:null}}/></MemoryRouter>)
    expect(html).toContain('Writing prep notes')
    expect(html).toContain('/jobs/9')
    expect(html).not.toContain('Cancel')
  })
})
