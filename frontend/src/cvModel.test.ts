import {describe,expect,it} from 'vitest'
import {comboValid,modelEffort,modelSpeed,shortPath,stepText} from './cvModel'

// Shapes mirror what available_model_options() returns from the backend.
const gpt={provider:'openai',key:'gpt-5.5',label:'GPT-5.5',efforts:['low','medium','high'],default_effort:'medium',fast_tier:'priority'}
const gptMini={provider:'openai',key:'gpt-5.4-mini',label:'GPT-5.4 mini',efforts:['low','medium'],default_effort:'low',fast_tier:''}
const claude={provider:'anthropic',key:'sonnet',label:'Claude Sonnet',efforts:['default'],default_effort:'default',fast_tier:''}

describe('model capability derivation',()=>{
  it('takes the default effort from the model, not a hard-coded provider assumption',()=>{
    expect(modelEffort(gpt)).toBe('medium')
    expect(modelEffort(claude)).toBe('default')
    expect(modelEffort({efforts:['xhigh']})).toBe('xhigh') // falls back to the first reported effort
    expect(modelEffort(undefined)).toBe('')
  })

  it('offers fast speed only to models that report a fast tier',()=>{
    expect(modelSpeed(gpt)).toBe('fast')
    expect(modelSpeed(gptMini)).toBe('normal')
    expect(modelSpeed(claude)).toBe('normal')
  })
})

describe('comboValid',()=>{
  it('accepts Anthropic at normal speed and rejects it at fast speed',()=>{
    expect(comboValid(claude,'default','normal')).toBe(true)
    expect(comboValid(claude,'default','fast')).toBe(false)
    expect(comboValid(claude,'high','normal')).toBe(false) // effort Anthropic never reported
  })

  it('allows fast only on a model with a fast tier',()=>{
    expect(comboValid(gpt,'medium','fast')).toBe(true)
    expect(comboValid(gptMini,'low','fast')).toBe(false)
    expect(comboValid(gptMini,'low','normal')).toBe(true)
  })

  it('rejects an effort the selected model does not report, so stale values cannot be submitted',()=>{
    expect(comboValid(gpt,'ultra','normal')).toBe(false)
    expect(comboValid(gptMini,'high','normal')).toBe(false) // stale value left over from gpt-5.5
    expect(comboValid(undefined,'medium','normal')).toBe(false)
  })
})

describe('shortPath',()=>{
  it('strips the workspace prefix for display',()=>{
    expect(shortPath('C:\\latex\\CVs\\English - AI Engineer (base)_v_1.4.tex','C:\\latex'))
      .toBe('CVs/English - AI Engineer (base)_v_1.4.tex')
    expect(shortPath('/srv/latex/output/Letter.pdf','/srv/latex')).toBe('output/Letter.pdf')
  })

  it('tolerates mixed separators and a trailing slash on the workspace',()=>{
    expect(shortPath('C:/latex/CVs/cv.tex','C:\\latex\\')).toBe('CVs/cv.tex')
    expect(shortPath('C:\\Latex\\CVs\\cv.tex','c:\\latex')).toBe('CVs/cv.tex')
  })

  it('leaves the path alone when it is outside the workspace or nothing is known',()=>{
    expect(shortPath('D:\\elsewhere\\cv.tex','C:\\latex')).toBe('D:\\elsewhere\\cv.tex')
    expect(shortPath('C:\\latex\\cv.tex')).toBe('C:\\latex\\cv.tex')
    expect(shortPath(undefined,'C:\\latex')).toBe('')
    // a workspace that is a string prefix but not a path boundary must not be chopped
    expect(shortPath('C:\\latex-old\\cv.tex','C:\\latex')).toBe('C:\\latex-old\\cv.tex')
  })
})

describe('stepText',()=>{
  it('renders the reported phase and step count',()=>{
    expect(stepText({step_label:'CV compiled',step_completed:3,step_total:5})).toBe('CV compiled · step 3/5')
  })

  it('survives a step_total that shrinks mid-run on a cache hit',()=>{
    expect(stepText({step_label:'Using saved package',step_completed:4,step_total:2})).toBe('Using saved package · step 2/2')
  })

  it('never emits NaN or a negative step for missing or junk fields',()=>{
    expect(stepText({step_label:'Preparing templates',step_completed:-3,step_total:4})).toBe('Preparing templates · step 0/4')
    expect(stepText({step_label:'Working',step_completed:undefined,step_total:4})).toBe('Working · step 0/4')
    expect(stepText({stage:'Queued'})).toBe('Queued') // no step data yet: fall back to the raw stage
    expect(stepText(undefined)).toBe('')
  })
})
