// TASK-219 AC4: the panel's whole reason to exist is that it must not print a misleading number.
// A median over an empty cohort is not 0 days, and a median over three applications is not the same
// claim as one over thirty. Both of those are one `??0` away from being silently wrong, and neither
// would fail a typecheck, so they are pinned here.
//
// Rendered with react-dom/server, the same way appPanels.test.tsx does it: this vitest run has no
// DOM (no jsdom, no @testing-library) and TASK-177 forbids adding one. Reading the emitted markup is
// enough to assert which branch was taken.
import {describe,expect,it} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {StallPanel} from './App'
import type {Stall} from './types'

const stall=(over:Partial<Stall>={}):Stall=>({median_days_to_applied:12,applied_sample:20,by_status:[],never_evaluated:0,...over})
const render=(stats:any)=>renderToStaticMarkup(<StallPanel stats={stats}/>)

describe('StallPanel never renders a misleading figure (TASK-219 AC4)',()=>{
  it('says there is no data rather than rendering zeros when the backend omits the key',()=>{
    const html=render({})
    expect(html).toContain('No stall data yet')
    expect(html).not.toContain('0 days')
  })

  // The defect this guards: `median ?? 0` renders "0 days", which reads as "you apply the same day
  // you find a role" -- the exact opposite of "nobody has applied to anything".
  it('says nothing has been applied to rather than showing 0 days on an empty cohort',()=>{
    const html=render({stall:stall({median_days_to_applied:null,applied_sample:0})})
    expect(html).toContain('No applications yet, so there is nothing to measure')
    expect(html).not.toContain('0 days')
  })

  it('marks a median over a thin sample as provisional and says how thin',()=>{
    const html=render({stall:stall({median_days_to_applied:12,applied_sample:3})})
    expect(html).toContain('12 days')
    expect(html).toContain('only 3 applications so far')
    expect(html).toContain('provisional')
  })

  it('states a median over a real sample without hedging it',()=>{
    const html=render({stall:stall({median_days_to_applied:12,applied_sample:20})})
    expect(html).toContain('12 days')
    expect(html).toContain('median across 20 applications')
    expect(html).not.toContain('provisional')
  })

  it('drops empty columns but still names an unmeasurable age in words',()=>{
    const html=render({stall:stall({by_status:[
      {status:'to_apply',count:2,median_age_days:7},
      {status:'applied',count:0,median_age_days:null},
      {status:'interview',count:1,median_age_days:null},
    ]})})
    expect(html).toContain('to apply')
    expect(html).not.toContain('applied<')      // the zero-count column is not rendered at all
    expect(html).toContain('7 days')
    expect(html).toContain('not measured yet')  // count 1 but no age -> words, never 0
  })

  it('reports the never-evaluated backlog as work waiting on the owner',()=>{
    expect(render({stall:stall({never_evaluated:4})})).toContain('4 leads got past new without an evaluation')
    expect(render({stall:stall({never_evaluated:0})})).toContain('Every lead past new has been evaluated')
  })
})
