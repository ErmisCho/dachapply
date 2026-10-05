import {describe,expect,it} from 'vitest'
import {defaultLetter,letterMismatchWarning,letterOptions} from './letterOptions'

const letters=[
  {key:'de_anschreiben',language:'de',label:'Anschreiben'},
  {key:'en_cover',language:'en',label:'Cover letter'},
  {key:'en_short',language:'en',label:'Short cover letter'},
]

describe('letterOptions',()=>{
  it('lists every language, same-language first, cross-language labelled not recommended',()=>{
    expect(letterOptions(letters,'de')).toEqual([
      {key:'de_anschreiben',label:'Anschreiben',recommended:true},
      {key:'en_cover',label:'Cover letter (not recommended)',recommended:false},
      {key:'en_short',label:'Short cover letter (not recommended)',recommended:false},
    ])
    expect(letterOptions(letters,'en').map(x=>x.key)).toEqual(['en_cover','en_short','de_anschreiben'])
    expect(letterOptions(letters,'en')[2].label).toBe('Anschreiben (not recommended)')
  })
  it('defaults to the first letter in the CV language, or none',()=>{
    expect(defaultLetter(letters,'en')).toBe('en_cover')
    expect(defaultLetter(letters,'de')).toBe('de_anschreiben')
    expect(defaultLetter(letters,'fr')).toBe('')
    expect(defaultLetter([],'en')).toBe('')
  })
  it('warns only for a mismatched pair',()=>{
    expect(letterMismatchWarning(letters,'en','de_anschreiben')).toContain('Not recommended')
    expect(letterMismatchWarning(letters,'en','en_short')).toBe('')
    expect(letterMismatchWarning(letters,'en','')).toBe('')
    expect(letterMismatchWarning(letters,'en','missing')).toBe('')
  })
})
