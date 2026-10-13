// TASK-277. The board's sort dropdown used to show "Sort: recommended" for any ordering no <option>
// matched (the browser falls back to the first option), so a header-click sort looked like recommended
// and picking recommended fired no change. These pin the decision logic and the rendered select.
// Rendered with react-dom/server like boardSkeleton.test.tsx: no DOM in this vitest run (TASK-177).
import {describe,expect,it} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {BoardSortSelect} from './App'
import {boardGroupedByStatus,boardJobsQuery,boardSortChoice,describeOrdering,effectiveOrdering,parseSortKeys} from './appUtils'

const selectedLabel=(html:string)=>html.match(/<option[^>]*selected=""[^>]*>([^<]*)</)?.[1]

describe('boardSortChoice (TASK-277)',()=>{
  it('shows a header-click ordering as a named custom option, not recommended',()=>{
    const c=boardSortChoice('-fit_score,priority','')
    expect(c.value).toBe('-fit_score,priority')
    expect(c.options.find(o=>o.value===c.value)?.label).toBe('Sort: custom — Fit score (desc), then Priority')
  })
  it('shows the saved account sort when no ordering is chosen',()=>{
    const c=boardSortChoice('','status,-fit_score')
    expect(c.value).toBe('')
    expect(c.options.find(o=>o.value==='')?.label).toBe('Sort: saved — Status, then Fit score (desc)')
  })
  it('keeps recommended selectable (a real change) while a saved sort is in effect',()=>{
    expect(boardSortChoice('','status').options.map(o=>o.value)).toContain('recommended')
  })
  it('shows recommended for the recommended token, and for empty with nothing saved',()=>{
    expect(boardSortChoice('recommended','status').value).toBe('recommended')
    expect(boardSortChoice('',undefined).value).toBe('recommended')
    expect(boardSortChoice(undefined,'').options.some(o=>o.label.startsWith('Sort: custom')||o.label.startsWith('Sort: saved'))).toBe(false)
  })
  it('selects a preset as itself with no extra option',()=>{
    const c=boardSortChoice('-created_at','')
    expect(c.value).toBe('-created_at')
    expect(c.options.filter(o=>o.value==='-created_at')).toHaveLength(1)
    expect(c.options).toHaveLength(6)
  })
})

describe('recommended token (TASK-277)',()=>{
  it('has no header arrows and reads "Sorted by: recommended"',()=>{
    expect(parseSortKeys('recommended')).toEqual([])
    expect(describeOrdering('recommended')).toBe('Sorted by: recommended')
  })
  it('effective ordering falls back to the saved keys, then recommended',()=>{
    expect(effectiveOrdering('-fit_score','status')).toBe('-fit_score')
    expect(effectiveOrdering('','status')).toBe('status')
    expect(effectiveOrdering('',undefined)).toBe('recommended')
  })
  it('sends ordering=recommended, and still omits an empty ordering',()=>{
    expect(new URLSearchParams(boardJobsQuery({ordering:'recommended',status:'new'})).get('ordering')).toBe('recommended')
    expect(new URLSearchParams(boardJobsQuery({ordering:'',status:'new'})).has('ordering')).toBe(false)
    expect(new URLSearchParams(boardJobsQuery({})).get('board')).toBe('1')
  })
})

describe('TASK-267 section headers under TASK-277',()=>{
  it('show for recommended and for empty with nothing saved',()=>{
    expect(boardGroupedByStatus('recommended','status')).toBe(true)
    expect(boardGroupedByStatus('','')).toBe(true)
    expect(boardGroupedByStatus(undefined,undefined)).toBe(true)
  })
  it('hide for presets, header-click sorts and a saved sort',()=>{
    expect(boardGroupedByStatus('status','')).toBe(false)
    expect(boardGroupedByStatus('-fit_score,priority','')).toBe(false)
    expect(boardGroupedByStatus('','status')).toBe(false)
  })
})

describe('BoardSortSelect render (TASK-277)',()=>{
  const html=(ordering?:string,savedKeys?:string)=>renderToStaticMarkup(<BoardSortSelect ordering={ordering} savedKeys={savedKeys} onChange={()=>{}}/>)
  it('selects the custom option for a header-click ordering restored from localStorage',()=>{
    const h=html('-fit_score,priority')
    expect(selectedLabel(h)).toBe('Sort: custom — Fit score (desc), then Priority')
    expect(h).toContain('Sorted by: Fit score (desc), then Priority')
  })
  it('selects the saved option when only the account sort applies',()=>{
    const h=html('','status,-fit_score')
    expect(selectedLabel(h)).toBe('Sort: saved — Status, then Fit score (desc)')
    expect(h).toContain('Sorted by: Status, then Fit score (desc)')
  })
  it('selects recommended and a preset honestly',()=>{
    expect(selectedLabel(html('recommended','status'))).toBe('Sort: recommended')
    expect(selectedLabel(html('-created_at'))).toBe('Sort: newest')
    expect(html('-created_at')).toContain('Sorted by: Newest (desc)')
  })
})
