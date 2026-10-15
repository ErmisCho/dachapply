// TASK-280.2: the job page's view of automatically prepared documents. No DOM here (see
// postingSource.test.tsx), so the pure panel is rendered to markup; polling needs a browser.
import {describe,expect,it} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {ApplicationPrepPanel} from './App'
import {isPreparing,prepAction,variantLabel,variantStatusText,type PrepState,type PrepVariant} from './applicationPrep'

const rule='Letters the posting does not mention, or calls optional, are not prepared automatically.'
const v=(extra:Partial<PrepVariant>):PrepVariant=>({key:'cv-de',document:'cv',language:'de',status:'ready',files:{cv_pdf:'C:\\ws\\CVs\\Me-CV-Acme-DE.pdf'},...extra})
const state=(variants:PrepVariant[],reason=''):PrepState=>({reason,rule,model:{},variants})
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
    expect(prepAction(state([v({status:'failed'})]),'reviewed')).toBe('')   // retry is refused outside To apply
    expect(isPreparing(state([v({status:'queued'})]))).toBe(true)
    expect(isPreparing(state([v({})]))).toBe(false)
  })

  it('flags a ready variant whose file is gone',()=>{
    expect(variantStatusText(v({missing:true}))).toContain('no longer on disk')
    expect(variantLabel(v({document:'message',language:'en'}))).toBe('Short message · English')
  })
})
