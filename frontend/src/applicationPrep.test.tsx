// TASK-280.2: the job page's view of automatically prepared documents. No DOM here (see
// postingSource.test.tsx), so the pure panel is rendered to markup; polling needs a browser.
import {describe,expect,it,vi} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {ApplicationPrepPanel,DailySlider,PrepBadge,TexPicker} from './App'
import appSource from './App.tsx?raw'
import {anyPreparing,defaultTex,isPreparing,prepAction,prepBadge,reviewText,texLabel,texOptions,variantLabel,variantStatusText,type PrepState,type PrepVariant} from './applicationPrep'

const rule='Letters the posting does not mention, or calls optional, are not prepared automatically.'
const v=(extra:Partial<PrepVariant>):PrepVariant=>({key:'cv-de',document:'cv',language:'de',status:'ready',files:{cv_pdf:'C:\\ws\\CVs\\Me-CV-Acme-DE.pdf'},...extra})
const state=(variants:PrepVariant[],reason='',extra:Partial<PrepState>={}):PrepState=>({reason,rule,model:{},variants,...extra})
const render=(s:PrepState|null,status='to_apply')=>renderToStaticMarkup(<ApplicationPrepPanel state={s} jobStatus={status}/>)

describe('prepared documents panel',()=>{
  it('lists each variant with its language, state and failure',()=>{
    const html=render(state([v({}),v({key:'letter-de',document:'letter',status:'failed',error:'provider down'}),v({key:'message-en',document:'message',language:'en',status:'running',progress:40,step_label:'Generating documents',estimated_seconds_remaining:120})]))
    expect(html).toContain('CV · German')
    expect(html).toContain('Me-CV-Acme-DE.pdf')
    expect(html).toContain('Failed: provider down')
    expect(html).toContain('Generating documents · 40% · about 2 min left')
    expect(html).toContain('Retry failed')
    expect(html).toContain(rule)   // AC4: the not-mentioned default is visible, not silent
  })

  it('says why nothing was prepared and offers to prepare now',()=>{
    const html=render(state([],'The job has no usable posting text yet.'))
    expect(html).toContain('no usable posting text')
    expect(html).toContain('Prepare now')
  })

  it('shows nothing for a job that was never prepared outside To apply, or for a non-generating account',()=>{
    expect(render(state([]),'reviewed')).toBe('')
    expect(render(null)).toBe('')
  })

  it('offers no action while everything is ready or running',()=>{
    expect(prepAction(state([v({}),v({key:'cv-en',language:'en',status:'running'})]),'to_apply')).toBe('')
    expect(prepAction(state([v({status:'failed'})]),'reviewed')).toBe('Retry failed')   // TASK-312: New/Reviewed are prepared too
    expect(prepAction(state([v({status:'cancelled'})]),'to_apply')).toBe('Retry failed')   // TASK-312: a cancelled variant can be re-queued
    expect(prepAction(state([v({status:'failed'})]),'applied')).toBe('')   // never Applied and later
    expect(isPreparing(state([v({status:'queued'})]))).toBe(true)
    expect(isPreparing(state([v({})]))).toBe(false)
    expect(isPreparing({...state([]),reason:'Analysing application requirements…'})).toBe(true)
  })

  it('flags a ready variant whose file is gone',()=>{
    expect(variantStatusText(v({missing:true}))).toContain('no longer on disk')
    expect(variantLabel(v({document:'message',language:'en'}))).toBe('Short message · English')
  })
})

// TASK-348: every generated letter, one dropdown. No DOM here, so TexPicker's element tree is read directly.
describe('choosing which TeX to copy',()=>{
  const letter=(template:string,extra:Partial<PrepVariant>={})=>v({key:`letter-de-${template}`,document:'letter',letter_template:template,letter_label:template,files:{letter_tex:`C:\\ws\\${template}.tex`},...extra})
  const letters=[v({key:'letter-de',document:'letter',letter_label:'Motivationsschreiben',recommended:true}),letter('Bewerbungsschreiben'),letter('Anschreiben')]
  const parts=(element:any,type:string):any[]=>[element].flat(9).flatMap(node=>!node||typeof node!=='object'?[]:[...(node.type===type?[node]:[]),...parts(node.props?.children,type)])
  const picker=(variants:PrepVariant[],value='',onCopy=(_:string)=>{},onChange=(_:string)=>{})=>TexPicker({state:state([v({}),...variants]),value,onChange,onCopy})

  it('lists every ready TeX by its readable name with the recommended one preselected',()=>{
    const html=renderToStaticMarkup(<ApplicationPrepPanel jobId={7} state={state([v({}),...letters])} jobStatus="to_apply"/>)
    expect(html).toContain('aria-label="TeX file to copy"')
    expect(html.match(/<option[^>]*>[^<]*<\/option>/g)).toEqual(['<option value="letter-de" selected="">Motivationsschreiben · German (recommended)</option>','<option value="letter-de-Bewerbungsschreiben">Bewerbungsschreiben · German</option>','<option value="letter-de-Anschreiben">Anschreiben · German</option>','<option value="cv-de">CV · German</option>'])
    expect(html).toContain('Full letter · German · Bewerbungsschreiben')   // the rows differ too
  })

  it('copies the selected key, and choosing only reports the choice: no request',()=>{
    const fetchSpy=vi.fn();vi.stubGlobal('fetch',fetchSpy)
    const onCopy=vi.fn(),onChange=vi.fn(),element=picker(letters,'letter-de-Anschreiben',onCopy,onChange)
    expect(parts(element,'select')[0].props.value).toBe('letter-de-Anschreiben')
    parts(element,'select')[0].props.onChange({target:{value:'letter-de-Bewerbungsschreiben'}})
    expect(onChange).toHaveBeenCalledWith('letter-de-Bewerbungsschreiben');expect(onCopy).not.toHaveBeenCalled()
    expect(fetchSpy).not.toHaveBeenCalled()
    parts(element,'button')[0].props.onClick()
    expect(onCopy).toHaveBeenCalledWith('letter-de-Anschreiben')
    vi.unstubAllGlobals()
  })

  it('the job page keeps the choice in local state and fetches the one chosen file only on Copy',()=>{
    expect(appSource).toContain('<TexPicker state={state} value={texKey} onChange={setTexKey} onCopy={onCopy}/>')
    expect(appSource).toContain('application-prep/export/?as=tex${key?`&key=${encodeURIComponent(key)}`')
  })

  it('shows a failed letter inline, keeps the rest selectable, and preselects the first ready one',()=>{
    const failed={...letters[0],status:'failed' as const,error:'provider down',files:{}}
    const html=renderToStaticMarkup(picker([failed,letters[1],letters[2]]))
    expect(html).toContain('Motivationsschreiben · German (recommended): Failed: provider down')
    expect(html).not.toContain('<option value="letter-de"')
    expect(html).toContain('<option value="letter-de-Bewerbungsschreiben" selected="">')
    expect(texOptions(state([failed]))).toEqual([]);expect(renderToStaticMarkup(TexPicker({state:state([failed]),value:'',onChange:()=>{}}))).not.toContain('<select')
  })

  it('leaves out discarded letters, and a job prepared before TASK-348 keeps its one label',()=>{
    expect(texOptions(state([{...letters[1],review:'discard'},letters[2]])).map(x=>x.key)).toEqual(['letter-de-Anschreiben'])
    expect(defaultTex(texOptions(state([v({key:'letter-de',document:'letter'})])))).toBe('letter-de')
    expect(texLabel(v({key:'letter-de',document:'letter'}))).toBe('Full letter · German')
    expect(render(state([v({})]))).not.toContain('<select')   // no letter wanted: nothing to choose between
  })
})

// TASK-280.3: review, final package and the status it earns.
describe('reviewing prepared documents',()=>{
  const four=()=>[v({}),v({key:'cv-en',language:'en',files:{cv_pdf:'C:\ws\CVs\Me-CV-Acme-EN.pdf'}}),v({key:'letter-de',document:'letter'}),v({key:'letter-en',document:'letter',language:'en'})]

  it('shows unreviewed documents visibly as drafts with preview, download, copy, keep, discard and adjust',()=>{
    const html=renderToStaticMarkup(<ApplicationPrepPanel jobId={7} state={state(four())} jobStatus="to_apply"/>)
    expect(html).toContain('Drafts: no final package is selected, so this job is not Ready to submit')
    expect(html.match(/>Draft</g)?.length).toBe(4)
    expect(html).toContain('/api/jobs/7/application-prep/export/?as=pdf&amp;key=cv-de')
    expect(html).toContain('/api/jobs/7/application-prep/export/?as=zip&amp;key=letter-en')
    for(const label of ['Preview PDF','Download','Copy TeX','Keep','Discard','Adjust','Select as final package'])expect(html).toContain(label)
    expect(html).toContain('aria-label="Include CV · German in the final package"')
  })

  it('shows the selected final package with package copy/download and marks its documents',()=>{
    const variants=four().map(x=>x.key==='cv-de'||x.key==='letter-de'?{...x,selected:true,review:'keep' as const}:x)
    const html=renderToStaticMarkup(<ApplicationPrepPanel jobId={7} state={state(variants,'',{selection:['cv-de','letter-de']})} jobStatus="ready_to_submit"/>)
    expect(html).toContain('Final package:</b> CV · German + Full letter · German')
    expect(html).toContain('/api/jobs/7/application-prep/export/?as=zip"')
    expect(html).toContain('Copy package TeX')
    expect(html.match(/In final package/g)?.length).toBe(2)
    expect(html).not.toContain('Drafts: no final package')
  })

  it('offers restore for a discarded document only while its files exist',()=>{
    const restorable=renderToStaticMarkup(<ApplicationPrepPanel state={state([v({review:'discard'})])} jobStatus="to_apply"/>)
    expect(restorable).toContain('Restore');expect(restorable).toContain('Discarded');expect(restorable).not.toContain('Preview PDF')
    const gone=renderToStaticMarkup(<ApplicationPrepPanel state={state([v({review:'discard',missing:true})])} jobStatus="to_apply"/>)
    expect(gone).not.toContain('>Restore<');expect(gone).toContain('cannot be restored')
  })

  it('says visibly why a stale package was cleared',()=>{
    const html=renderToStaticMarkup(<ApplicationPrepPanel state={state([v({missing:true})],'',{invalidated:'The final package was cleared: Me-CV-Acme-DE.pdf is no longer on disk (deleted or renamed). Select a package again.'})} jobStatus="to_apply"/>)
    expect(html).toContain('role="alert"');expect(html).toContain('Me-CV-Acme-DE.pdf is no longer on disk')
  })

  it('notes kept documents made before the posting changed (TASK-336)',()=>{
    expect(render(state([v({review:'keep'})],'',{outdated:'Posting changed since these documents were made'}))).toContain('Posting changed since these documents were made')
    expect(render(state([],'',{outdated:'Posting changed since these documents were made'}),'new')).toContain('Posting changed')   // owner-made files, nothing prepared
  })

  it('shows an adjustment in progress and one that failed',()=>{
    expect(variantStatusText(v({adjusting:true,progress:40,estimated_seconds_remaining:60}))).toBe('Adjusting · 40% · about 1 min left')
    expect(isPreparing(state([v({adjusting:true})]))).toBe(true)
    expect(renderToStaticMarkup(<ApplicationPrepPanel state={state([v({adjust_error:'model down'})])} jobStatus="to_apply"/>)).toContain('Adjustment failed: model down')
    expect(reviewText(v({review:'keep'}))).toBe('Kept')
    expect(prepAction(state([v({status:'failed',review:'discard'})]),'to_apply')).toBe('')   // discarded failures are not retried
  })
})

// TASK-299: the board row badge.
describe('board preparation badge',()=>{
  it('shows count, a five-step bar, percent and the slowest time left while running',()=>{
    expect(prepBadge({running:2,done:1,failed:0,progress:45,eta:120})?.text).toBe('Preparing 2 docs ▓▓░░░ 45% · ~2 min left')
    expect(prepBadge({running:1,done:0,failed:0,progress:100,eta:0})?.text).toBe('Preparing 1 doc ▓▓▓▓▓ 100%')
    expect(renderToStaticMarkup(<PrepBadge summary={{running:2,done:0,failed:0,progress:45,eta:300}}/>)).toContain('Preparing 2 docs ▓▓░░░ 45% · ~5 min left')
  })

  it('becomes ready or failed when done, and is absent without a preparation',()=>{
    expect(prepBadge({running:0,done:4,failed:0,progress:100,eta:0})).toMatchObject({text:'4 docs ready',tone:'green'})
    expect(prepBadge({running:0,done:3,failed:1,progress:100,eta:0})).toMatchObject({text:'1 doc failed',tone:'red'})
    expect(renderToStaticMarkup(<PrepBadge summary={undefined}/>)).toBe('')
  })

  it('polls only while something is running',()=>{
    expect(anyPreparing({'3':{running:0,done:2,failed:0,progress:100,eta:0}})).toBe(false)
    expect(anyPreparing({'3':{running:1,done:2,failed:0,progress:10,eta:60}})).toBe(true)
  })
})

// TASK-335/337: the Profile's daily-run sliders say their value, Off and Unlimited, to screen readers too.
describe('daily-run slider',()=>{
  const slider=(value:number|null,unlimited=true,unit='job')=>renderToStaticMarkup(<DailySlider id="s" label="Analyse waiting jobs per day" help="" unit={unit} max={50} unlimited={unlimited} value={value} onChange={()=>{}}/>)
  it('labels the value, Off and Unlimited',()=>{
    expect(slider(10)).toContain('aria-valuetext="10 jobs"');expect(slider(10)).toContain('for="s"')
    expect(slider(1)).toContain('aria-valuetext="1 job"')
    expect(slider(0)).toContain('aria-valuetext="Off"')
    const unlimited=slider(null);expect(unlimited).toContain('aria-valuetext="Unlimited"');expect(unlimited).toContain('max="51"');expect(unlimited).toContain('value="51"')
    const days=slider(7,false,'day');expect(days).toContain('max="50"');expect(days).toContain('7 days')
  })
})
