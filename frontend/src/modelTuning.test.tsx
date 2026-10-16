import {describe,expect,it} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {ModelTuning} from './App'
import {draftEffort,expectedDuration} from './cvModel'

const noop=()=>{}
const render=(model:any)=>renderToStaticMarkup(<ModelTuning model={model} effort="low" speed="normal" onEffort={noop} onSpeed={noop}/>)

describe('per-model effort and speed controls (TASK-290)',()=>{
  it('offers exactly the efforts the model declares, and Fast only with a fast tier',()=>{
    const html=render({key:'gpt-6.1-sol',efforts:['low','xhigh','ultra'],fast_tier:'priority'})
    expect(html).toContain('Effort')
    expect(html).toContain('>ultra<')
    expect(html).not.toContain('>medium<')
    expect(html).toContain('>Fast<')
  })

  it('hides effort for a model with only "default" and speed without a fast tier',()=>{
    const html=render({key:'qwen',efforts:['default'],fast_tier:''})
    expect(html).not.toContain('Effort')
    expect(html).not.toContain('Speed')
  })

  it('says so when the list is the built-in fallback',()=>{
    expect(render({key:'gpt-5.6-sol',efforts:['low'],fast_tier:'',fallback:true})).toContain('built-in list')
    expect(render({key:'gpt-6.1-sol',efforts:['low'],fast_tier:''})).not.toContain('built-in list')
  })
})

describe('draft effort default (TASK-293)',()=>{
  it('is xhigh where declared, else the highest level below it',()=>{
    expect(draftEffort({efforts:['low','medium','xhigh','max','ultra'],default_effort:'low'})).toBe('xhigh')
    expect(draftEffort({efforts:['low','high','max'],default_effort:'low'})).toBe('high')
    expect(draftEffort({efforts:['default'],default_effort:'default'})).toBe('default')
  })
})

describe('expected duration in every model picker (TASK-303)',()=>{
  const timed={key:'gpt-6.1-sol',efforts:['medium','high'],fast_tier:'priority',expected_seconds:{
    generation:{both:{'high|fast':{seconds:118,history:'measured'},'medium|fast':{seconds:40,history:'other_effort'},'high|normal':{seconds:300,history:'none'}},cv:{'high|fast':{seconds:357,history:'measured'}}},
    revision:{cv:{'high|fast':{seconds:62,history:'measured'}}}}}
  it('shows the learned time for the exact effort, speed, route and documents',()=>{
    expect(expectedDuration(timed,'high','fast')).toBe('~2 min')
    expect(expectedDuration(timed,'high','fast',{documents:'cv'})).toBe('~6 min')
    expect(expectedDuration(timed,'high','fast',{route:'revision',documents:'cv'})).toBe('~60 s')
    expect(expectedDuration(timed,'medium','fast')).toBe('~40 s (from other effort levels)')
  })
  it('labels a rough guess and says when there is no timing at all',()=>{
    expect(expectedDuration(timed,'high','normal')).toBe('~5 min (rough guess: no runs of this model yet)')
    expect(expectedDuration({key:'draft-only',efforts:['low']},'low','normal')).toBe('no timing yet')
  })
  it('renders inside ModelTuning, also for a model with no effort choice',()=>{
    expect(renderToStaticMarkup(<ModelTuning model={timed} effort="high" speed="fast" onEffort={noop} onSpeed={noop}/>)).toContain('Expected duration: ~2 min')
    expect(render({key:'qwen',efforts:['default'],fast_tier:''})).toContain('Expected duration: no timing yet')
  })
})
