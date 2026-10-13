// TASK-285: interview rows live in exactly one board table, depending on the toggle.
import {describe,expect,it} from 'vitest'
import {splitInterviewRows} from './appUtils'

const rows=[{id:1,status:'new'},{id:2,status:'interview'},{id:3,status:'applied'},{id:4,status:'interview'}]
const ids=(r:{id:number}[])=>r.map(x=>x.id)

describe('splitInterviewRows (TASK-285)',()=>{
  it('shown: interview rows only in the Interviews table, main keeps the rest in order',()=>{
    const s=splitInterviewRows(rows,true)
    expect(ids(s.interviews)).toEqual([2,4])
    expect(ids(s.main)).toEqual([1,3])
  })
  it('hidden: no Interviews table, main is the board exactly as before',()=>{
    const s=splitInterviewRows(rows,false)
    expect(s.interviews).toEqual([])
    expect(ids(s.main)).toEqual([1,2,3,4])
  })
})
