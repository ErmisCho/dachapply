// TASK-230/231: the CV popup now has two independent model pickers and remembers both. The popup
// itself is not renderable in this vitest run (no DOM, so effects never run and `preview` stays
// null -- see cvPopup.test.tsx), so the rules that decide a selection live in cvModel.ts as pure
// functions and are tested here. What is NOT covered by any test: that the two pickers are wired to
// separate state in App.tsx, and every pixel claim -- both need a browser.
import {afterEach,describe,expect,it,vi} from 'vitest'
import {comboValid,cvPick,emptyCvPick,readCvPicks,writeCvPicks} from './cvModel'

const models=[
  {provider:'openai',key:'gpt-5-codex',label:'GPT-5 Codex',efforts:['low','medium','high','xhigh'],default_effort:'medium',fast_tier:true},
  {provider:'anthropic',key:'claude-opus',label:'Claude Opus',efforts:['medium','high'],default_effort:'medium',fast_tier:false},
  {provider:'lmstudio',key:'qwen3-8b',label:'Qwen3 8B',efforts:['low'],default_effort:'low',fast_tier:false},
]

const fakeStorage=(initial:Record<string,string>={})=>({
  store:{...initial},
  getItem(key:string){return Object.prototype.hasOwnProperty.call(this.store,key)?this.store[key]:null},
  setItem(key:string,value:string){this.store[key]=value},
  removeItem(key:string){delete this.store[key]},
})

afterEach(()=>vi.unstubAllGlobals())

describe('restoring a remembered selection (TASK-231)',()=>{
  it('gives back exactly what was remembered while the model is still offered',()=>{
    expect(cvPick(models,{provider:'openai',model:'gpt-5-codex',effort:'xhigh',speed:'fast'}))
      .toEqual({provider:'openai',model:'gpt-5-codex',effort:'xhigh',speed:'fast'})
  })

  it('falls back to a valid model when the remembered one is no longer offered',()=>{
    // AC2. LM Studio models come and go (TASK-221); a vanished one must not leave the popup unable
    // to send anything. The provider is kept if it still has any model at all...
    expect(cvPick(models,{provider:'lmstudio',model:'gone-1b',effort:'low',speed:'normal'}))
      .toEqual({provider:'lmstudio',model:'qwen3-8b',effort:'low',speed:'normal'})
    // ...and when the whole provider is gone, the first model offered is used, with its defaults.
    expect(cvPick(models,{provider:'ollama',model:'llama3',effort:'high',speed:'fast'}))
      .toEqual({provider:'openai',model:'gpt-5-codex',effort:'medium',speed:'fast'})
  })

  it('corrects a remembered effort or speed the model does not support rather than sending it',()=>{
    // AC3. `xhigh` is an OpenAI effort; Claude does not offer it, and offers no fast tier either.
    const corrected=cvPick(models,{provider:'anthropic',model:'claude-opus',effort:'xhigh',speed:'fast'})

    expect(corrected).toEqual({provider:'anthropic',model:'claude-opus',effort:'medium',speed:'normal'})
  })

  it('never returns a combination comboValid would reject',()=>{
    // comboValid is the gate on both Generate and Readjust, so a selection it rejects is a popup
    // with a dead button. Every reachable route into a selection goes through cvPick.
    const wants=[null,{},{provider:'anthropic',model:'claude-opus',effort:'xhigh',speed:'fast'},
                 {provider:'lmstudio',model:'gone-1b',effort:'nonsense',speed:'fast'},
                 {provider:'openai',model:'gpt-5-codex',effort:'low',speed:'normal'}]

    for(const want of wants){
      const pick=cvPick(models,want)
      const model=models.find(x=>x.provider===pick.provider&&x.key===pick.model)
      expect(comboValid(model,pick.effort,pick.speed)).toBe(true)
    }
  })

  it('switches model with the new provider defaults when the provider changes',()=>{
    const from={provider:'openai',model:'gpt-5-codex',effort:'xhigh',speed:'fast'}

    expect(cvPick(models,{...from,provider:'anthropic'}))
      .toEqual({provider:'anthropic',model:'claude-opus',effort:'medium',speed:'normal'})
  })

  it('stays usable when the server offers no models at all',()=>{
    expect(cvPick([],{provider:'openai',model:'gpt-5-codex',effort:'low',speed:'fast'})).toEqual(emptyCvPick)
  })
})

describe('where the remembered selection lives (TASK-231)',()=>{
  it('round-trips both pickers and scopes them to the account',()=>{
    // AC4: a second user on the same browser must not inherit the first one's model.
    const storage=fakeStorage()
    vi.stubGlobal('localStorage',storage)
    const picks={generate:{provider:'openai',model:'gpt-5-codex',effort:'low',speed:'fast'},
                 adjust:{provider:'anthropic',model:'claude-opus',effort:'high',speed:'normal'}}

    writeCvPicks('ermis',picks)

    expect(readCvPicks('ermis')).toEqual(picks)
    expect(readCvPicks('someone-else')).toEqual({})
    expect(Object.keys(storage.store)).toEqual(['dachapply_cv_picks_ermis'])
  })

  it('forgets instead of crashing when storage is unavailable',()=>{
    // Private mode and blocked site data make localStorage THROW, not return null. A popup that
    // will not open is worse than one that forgets the last model.
    vi.stubGlobal('localStorage',{getItem(){throw new Error('blocked')},setItem(){throw new Error('blocked')}})

    expect(readCvPicks('ermis')).toEqual({})
    expect(()=>writeCvPicks('ermis',{generate:emptyCvPick,adjust:emptyCvPick})).not.toThrow()
  })

  it('survives a corrupted entry',()=>{
    vi.stubGlobal('localStorage',fakeStorage({'dachapply_cv_picks_ermis':'{not json'}))

    expect(readCvPicks('ermis')).toEqual({})
  })
})
