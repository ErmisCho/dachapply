import {describe,expect,it,vi} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {CvGenerator} from './App'
import type {Job} from './types'

const storage={getItem:vi.fn(()=>JSON.stringify({can_generate_cv:true})),removeItem:vi.fn()}
vi.stubGlobal('localStorage',storage)

describe('compact CV generator popup (TASK-216)',()=>{
  it('opens at its final height with loading, close, and dialog semantics already present',()=>{
    const html=renderToStaticMarkup(<CvGenerator compact job={{id:216} as Job} onClose={()=>{}}/>)

    expect(html).toContain('role="dialog"')
    expect(html).toContain('aria-label="Generate CV and Motivation Letter"')
    expect(html).toContain('tabindex="-1"')
    expect(html).toContain('h-[80vh]')
    expect(html).toContain('Loading generator options…')
    expect(html).toContain('>Close</button>')
    expect(html).not.toContain('Detected language')
  })
})
