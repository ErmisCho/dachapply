import {describe,expect,it} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {ModelTuning} from './App'
import {draftEffort} from './cvModel'

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
