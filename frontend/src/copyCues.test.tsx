// TASK-272: completion chime and the small "Copied" cues. No DOM in this vitest run (see
// cvPopup.test.tsx), so the timing is tested through createFlash with fake timers, the cues
// through static markup, and the wiring through App.tsx's source.
import {afterEach,describe,expect,it,vi} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {CopiedChip,CopyTexButton} from './App'
import appSource from './App.tsx?raw'
import {createFlash} from './appUtils'
// playChime caches its AudioContext in module state, so each case loads a fresh copy.
const freshChime=async()=>{vi.resetModules();return (await import('./appUtils')).playChime}

afterEach(()=>{vi.useRealTimers();vi.unstubAllGlobals()})

describe('createFlash (AC3/AC4 auto-hide)',()=>{
  it('turns on, turns itself off after ms, and a re-flash restarts the clock',()=>{
    vi.useFakeTimers()
    const seen:boolean[]=[];const f=createFlash(3000,on=>seen.push(on))
    f.flash();expect(seen).toEqual([true])
    vi.advanceTimersByTime(2000);f.flash()
    vi.advanceTimersByTime(2999);expect(seen).toEqual([true,true])
    vi.advanceTimersByTime(1);expect(seen).toEqual([true,true,false])
    f.flash();f.cancel();vi.advanceTimersByTime(5000);expect(seen[seen.length-1]).toBe(true)
  })
})

describe('cue markup (AC3/AC4/AC5)',()=>{
  it('inline chip is a live region that shows Copied only while flashed',()=>{
    const on=renderToStaticMarkup(<CopiedChip show/>),off=renderToStaticMarkup(<CopiedChip show={false}/>)
    expect(on).toContain('role="status"');expect(on).toContain('Copied');expect(on).toContain('copied-fade')
    expect(off).toContain('role="status"');expect(off).not.toContain('Copied')
  })
  it('copy button swaps icon to a check with a Copied label, keeping its accessible name',()=>{
    const idle=renderToStaticMarkup(<CopyTexButton copied={false} onClick={()=>{}}/>)
    const done=renderToStaticMarkup(<CopyTexButton copied onClick={()=>{}}/>)
    for(const html of [idle,done])expect(html).toContain('aria-label="Copy generated TeX files"')
    expect(idle).not.toContain('Copied');expect(idle).toContain('<rect')
    expect(done).toContain('title="Copied"');expect(done).toContain('>Copied</span>');expect(done).toContain('m5 13 4 4 10-10');expect(done).not.toContain('<rect')
  })
})

describe('wiring (AC1/AC3/AC4/AC5)',()=>{
  const gen=appSource.slice(appSource.indexOf('export function CvGenerator'),appSource.indexOf('function BatchCvGenerator'))
  const batch=appSource.slice(appSource.indexOf('function BatchCvGenerator'),appSource.indexOf('type NoteTable'))
  it('copy cue fires only when the copy succeeded, in the generator and in every bulk row',()=>{
    expect(appSource).toContain('onClick={async()=>{if(await onCopy())flash()}}')
    expect(gen).toContain('<CopyTexAction disabled={loading||revisionLoading||compileLoading||!clipboardTex} onCopy={()=>copyTex()}/>')
    expect(batch).toContain('<CopyTexAction disabled={!row.clipboard_tex} onCopy={()=>copyRowTex(row)}/>')
    expect(gen).toContain("return false}async function waitForTask")
    expect(batch).toContain("update(row.job.id,{error:null});return true}")
  })
  it('the banner is gone and the chip sits next to Generate',()=>{
    expect(gen).not.toContain('SuccessMessage message={clipboardMessage}')
    expect(gen).toContain('onClick={generate}/><CopiedChip show={texCopied}/>')
    expect(gen).toContain('if(current.clipboard_copied||await copyTex(current.clipboard_tex))flashTexCopied()')
  })
  it('chimes after a successful Generate only, and once per bulk batch',()=>{
    expect(gen).toContain("if(current.status==='cancelled')return false;")
    expect(gen).toContain("flashTexCopied();return true}")
    expect(gen).toContain('if(await waitForTask(started.task_id))playChime()')
    expect(gen.split('playChime()').length-1).toBe(1)
    expect(batch).toContain("if(results.some(task=>task?.status==='ready'))playChime();")
    expect(batch.split('playChime()').length-1).toBe(1)
  })
})

describe('playChime (AC1/AC2)',()=>{
  it('plays two soft sine notes under one second on one shared context',async()=>{const playChime=await freshChime()
    const oscs:any[]=[],gains:any[]=[];let created=0
    class FakeCtx{state='suspended';currentTime=10;destination={};resume=vi.fn(()=>Promise.resolve());constructor(){created++}
      createOscillator(){const o={type:'',frequency:{value:0},connect:vi.fn(),start:vi.fn(),stop:vi.fn()};oscs.push(o);return o}
      createGain(){const g={gain:{setValueAtTime:vi.fn(),exponentialRampToValueAtTime:vi.fn()},connect:vi.fn()};gains.push(g);return g}}
    vi.stubGlobal('window',{AudioContext:FakeCtx})
    playChime()
    expect(created).toBe(1);expect(oscs).toHaveLength(2)
    for(const o of oscs){expect(o.type).toBe('sine');expect(o.stop.mock.calls[0][0]-10).toBeLessThan(1)}
    for(const g of gains){const peak=Math.max(...g.gain.exponentialRampToValueAtTime.mock.calls.map((c:any)=>c[0]));expect(peak).toBeGreaterThanOrEqual(.08);expect(peak).toBeLessThanOrEqual(.12)}
    playChime();expect(created).toBe(1);expect(oscs).toHaveLength(4)
  })
  it('is silent and never throws without Web Audio or when audio blows up',async()=>{const playChime=await freshChime()
    vi.stubGlobal('window',{})
    expect(()=>playChime()).not.toThrow()
    vi.stubGlobal('window',{AudioContext:class{constructor(){throw new Error('blocked')}}})
    expect(()=>playChime()).not.toThrow()
  })
})
