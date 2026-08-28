import {describe,expect,it,vi} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {JobNoteRow,jobNoteEditable,noteEditState,patchJobNote,replaceEditedNote} from './App'
import type {ApplicationNote} from './types'

const note:ApplicationNote={id:7,job:3,note:'Call the recruiter',note_type:'general',created_by:1,created_at:'2026-08-27T12:00:00Z'}
const statuses=['new','reviewed','to_apply','applied','interview','offer','accepted','rejected','withdrawn','skipped','archived']

describe('job note editing (TASK-196)',()=>{
  it('offers Edit for a general note at every job status, including every terminal status',()=>{
    for(const status of statuses){
      expect(jobNoteEditable(note,status)).toBe(true)
      expect(renderToStaticMarkup(<JobNoteRow item={note} jobStatus={status} onSaved={()=>{}}/>)).toContain('>Edit</button>')
    }
    for(const terminal of ['rejected','withdrawn','skipped','archived'])expect(jobNoteEditable(note,terminal)).toBe(true)
  })

  it('does not offer editing for auto-recorded note types',()=>{
    const automatic={...note,note_type:'recruiter_message'}
    expect(jobNoteEditable(automatic,'applied')).toBe(false)
    expect(renderToStaticMarkup(<JobNoteRow item={automatic} jobStatus="applied" onSaved={()=>{}}/>)).not.toContain('>Edit</button>')
  })

  it('PATCHes the existing note and replaces that row without adding a duplicate',async()=>{
    const saved={...note,note:'Call after Friday'}
    const request=vi.fn().mockResolvedValue(saved)

    const result=await patchJobNote(note.id,'  Call after Friday  ',request)
    const notes=replaceEditedNote([note,{...note,id:8}],result)

    expect(request).toHaveBeenCalledOnce()
    expect(request).toHaveBeenCalledWith('/notes/7/',{method:'PATCH',body:{note:'Call after Friday'}})
    expect(notes).toHaveLength(2)
    expect(notes.map(item=>item.id)).toEqual([7,8])
    expect(notes[0].note).toBe('Call after Friday')
  })

  it('cancels a changed draft back to the stored note',()=>{
    let editor=noteEditState({editing:false,draft:note.note},{type:'edit',note:note.note})
    editor=noteEditState(editor,{type:'change',value:'Unsaved replacement'})
    editor=noteEditState(editor,{type:'cancel',note:note.note})

    expect(editor).toEqual({editing:false,draft:'Call the recruiter'})
    expect(note.note).toBe('Call the recruiter')
  })
})
