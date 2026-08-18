import {afterEach,describe,expect,it} from 'vitest'
import {copyToClipboard,deadlineBadge,describeOrdering,fromDateTimeLocal,germanSubmitError,initPanelOrder,nextSortKeys,pathTitle,ratePercent,sortOrderingString,sourceLabel,submitDe,toDateTimeLocal} from './appUtils'
import type {SortKey} from './appUtils'

// Every copy button in the app now goes through copyToClipboard, so a denied or
// missing clipboard must resolve to false instead of rejecting into the console.
const originalClipboard=Object.getOwnPropertyDescriptor(globalThis,'navigator')
function setClipboard(clipboard:any){Object.defineProperty(globalThis,'navigator',{value:{clipboard},configurable:true,writable:true})}
afterEach(()=>{originalClipboard?Object.defineProperty(globalThis,'navigator',originalClipboard):delete (globalThis as any).navigator})

describe('copyToClipboard',()=>{
  it('reports success when the browser accepts the write',async()=>{
    const written:string[]=[]
    setClipboard({writeText:async(text:string)=>{written.push(text)}})
    expect(await copyToClipboard('prompt text')).toBe(true)
    expect(written).toEqual(['prompt text'])
  })

  it('resolves false instead of rejecting when the clipboard is denied',async()=>{
    setClipboard({writeText:async()=>{throw new DOMException('Write permission denied.','NotAllowedError')}})
    await expect(copyToClipboard('prompt text')).resolves.toBe(false)
  })

  it('resolves false when the browser exposes no clipboard at all',async()=>{
    setClipboard(undefined)
    await expect(copyToClipboard('prompt text')).resolves.toBe(false)
  })
})

describe('interview date round trip',()=>{
  it('survives the datetime-local input without shifting the minute',()=>{
    expect(fromDateTimeLocal(toDateTimeLocal('2026-08-18T10:30:00Z'))).toBe('2026-08-18T10:30:00.000Z')
  })

  it('treats an empty input as clearing the date',()=>{
    expect(toDateTimeLocal(null)).toBe('')
    expect(toDateTimeLocal('')).toBe('')
    expect(fromDateTimeLocal('')).toBe(null)
    expect(fromDateTimeLocal(null)).toBe(null)
  })

  it('ignores a value the browser cannot parse instead of sending "Invalid Date"',()=>{
    expect(toDateTimeLocal('not a date')).toBe('')
    expect(fromDateTimeLocal('not a date')).toBe(null)
  })
})

// TASK-79 AC3: the backend ranks past and approaching deadlines identically (stale_rank -1),
// so a past deadline is only distinguishable from an approaching one - and from an evergreen
// lead with no deadline at all - by what this function returns.
describe('apply-by deadline badge',()=>{
  it('marks a past deadline differently from an approaching one',()=>{
    expect(deadlineBadge(-3,7)).toEqual({tone:'red',label:'Deadline passed 3d ago'})
    expect(deadlineBadge(3,7)).toEqual({tone:'yellow',label:'Apply in 3d'})
    expect(deadlineBadge(0,7)).toEqual({tone:'yellow',label:'Apply by today'})
  })

  it('leaves an evergreen lead unbadged',()=>{
    expect(deadlineBadge(null,7)).toBe(null)
    expect(deadlineBadge(8,7)).toBe(null)
    expect(deadlineBadge(7,7)).not.toBe(null)
  })

  it('follows the threshold the backend ships rather than a hardcoded 7',()=>{
    expect(deadlineBadge(10,14)).toEqual({tone:'yellow',label:'Apply in 10d'})
    expect(deadlineBadge(5,3)).toBe(null)
  })
})

// TASK-108 AC2/AC3/AC6/AC7: the board's sortable column headers cycle unsorted -> ascending ->
// descending -> unsorted, and a second header click appends a lower-precedence key instead of
// replacing the first - that append-not-replace step is the one a shift-click implementation would
// have skipped, so it is the one worth pinning down here rather than only in a browser.
describe('board header sort cycle',()=>{
  it('cycles a single column unsorted -> ascending -> descending -> unsorted',()=>{
    let keys:SortKey[]=[]
    keys=nextSortKeys(keys,'status')
    expect(keys).toEqual([{key:'status',dir:'asc'}])
    keys=nextSortKeys(keys,'status')
    expect(keys).toEqual([{key:'status',dir:'desc'}])
    keys=nextSortKeys(keys,'status')
    expect(keys).toEqual([])
  })

  it('appends a second header as a lower-precedence key instead of replacing the first',()=>{
    const withStatus=nextSortKeys([],'status')
    const withBoth=nextSortKeys(withStatus,'fit_score')
    expect(withBoth).toEqual([{key:'status',dir:'asc'},{key:'fit_score',dir:'asc'}])
    expect(sortOrderingString(withBoth)).toBe('status,fit_score')
  })

  it('toggles direction on the lower-precedence key in place, leaving precedence order alone',()=>{
    const twoKeys:SortKey[]=[{key:'status',dir:'asc'},{key:'fit_score',dir:'asc'}]
    const flipped=nextSortKeys(twoKeys,'fit_score')
    expect(flipped).toEqual([{key:'status',dir:'asc'},{key:'fit_score',dir:'desc'}])
    expect(sortOrderingString(flipped)).toBe('status,-fit_score')
  })

  it('drops the oldest (lowest-precedence) key once a 4th distinct column is activated, matching the server cap of 3',()=>{
    const three=['status','fit_score','priority'].reduce((acc,k)=>nextSortKeys(acc,k),[] as SortKey[])
    const four=nextSortKeys(three,'applied_at')
    expect(four).toEqual([{key:'fit_score',dir:'asc'},{key:'priority',dir:'asc'},{key:'applied_at',dir:'asc'}])
  })

  it('renders an empty ordering string once every header is cycled back to unsorted',()=>{
    expect(sortOrderingString([])).toBe('')
  })
})

// TASK-111 AC4: below 1024px the sortable headers do not render, so this description string is the
// only on-screen readout of the sort actually applied - it has to read back the exact wire string
// TASK-108 sends as `ordering`, including combinations no preset <option> spells out.
describe('describeOrdering (TASK-111 small-screen sort readout)',()=>{
  it('names the default when no ordering is applied',()=>{
    expect(describeOrdering('')).toBe('Sorted by: recommended')
    expect(describeOrdering(null)).toBe('Sorted by: recommended')
    expect(describeOrdering(undefined)).toBe('Sorted by: recommended')
  })

  it('describes a single ascending key by its column label',()=>{
    expect(describeOrdering('status')).toBe('Sorted by: Status')
  })

  it('marks a descending key and preserves comma precedence order',()=>{
    expect(describeOrdering('status,-fit_score')).toBe('Sorted by: Status, then Fit score (desc)')
  })

  it('falls back to the raw key for anything unmapped rather than dropping it silently',()=>{
    expect(describeOrdering('made_up_key')).toBe('Sorted by: made_up_key')
  })
})

// TASK-117 AC3: a panel id added after a user already has a saved order (mailbox_review, here)
// must render first, not last - measured against a pre-seeded localStorage value in a browser, but
// this is the pure reducer behind that, so it gets a unit test here too.
describe('dashboard panel order (TASK-117 AC3)',()=>{
  it('splices an id unknown to an existing saved order to the front instead of appending it',()=>{
    const saved=['total','new_high_priority','active_applied']
    const allIds=['mailbox_review','total','new_high_priority','active_applied']
    expect(initPanelOrder(saved,allIds)).toEqual(['mailbox_review','total','new_high_priority','active_applied'])
  })

  it('leaves a fully-known saved order untouched, in its saved order',()=>{
    expect(initPanelOrder(['b','a'],['a','b'])).toEqual(['b','a'])
  })

  it('falls back to the natural id order when nothing is saved yet',()=>{
    expect(initPanelOrder([],['a','b','c'])).toEqual(['a','b','c'])
  })

  it('drops a saved id no longer in the panel registry instead of keeping a dangling one',()=>{
    expect(initPanelOrder(['gone','a'],['a','b'])).toEqual(['b','a'])
  })
})

describe('per-route tab titles',()=>{
  it('gives each route its own title',()=>{
    // /public-submit is the one German route (TASK-98), so its tab title is German too.
    const titles=['/','/add','/public-submit','/prompts','/import','/followups','/export','/bookmarklet','/settings/profile','/settings/account'].map(pathTitle)
    expect(titles).toEqual(['Board','Add job','Jobangebot einreichen','Prompts','Import','Follow-ups','Export','Bookmarklet','Profile settings','Account settings'])
    expect(new Set(titles).size).toBe(titles.length)
  })

  it('titles parameterised routes and falls back to the bare app name',()=>{
    expect(pathTitle('/jobs/123')).toBe('Job')
    expect(pathTitle('/reset-password/abc/def')).toBe('Reset password')
    expect(pathTitle('/nope')).toBe('')
  })
})

describe('funnel and source stats formatting',()=>{
  it('renders a null rate as an em dash and a zero rate as 0%',()=>{
    // /api/stats/ sends null when the denominator is zero. "0%" there would read as
    // "you convert nothing" instead of "nothing to measure yet" - the whole reason the
    // backend chose null over 0.0, so the two must never collapse to the same string.
    expect(ratePercent(null)).toBe('—')
    expect(ratePercent(undefined)).toBe('—')
    expect(ratePercent(0)).toBe('0%')
    expect(ratePercent(60)).toBe('60%')
    expect(ratePercent(33.3)).toBe('33.3%')
  })

  it('labels the empty source bucket the backend emits raw',()=>{
    expect(sourceLabel('')).toBe('Unknown source')
    expect(sourceLabel('   ')).toBe('Unknown source')
    expect(sourceLabel(null)).toBe('Unknown source')
    expect(sourceLabel('linkedin')).toBe('linkedin')
  })
})

// TASK-98 AC1: /public-submit is German including its error state, but /api/public/submit/ answers
// in English. Every message that endpoint can return has to come out German, and - the part worth
// a test - anything unmapped must fall back to German instead of leaking English onto the page.
describe('German errors on the public submit page',()=>{
  it('translates the messages /api/public/submit/ can actually return',()=>{
    expect(germanSubmitError('Invalid invite code')).toBe('Ungültiger Einladungscode.')
    expect(germanSubmitError('Your friend has not approved this submission link yet.')).toBe('Dein Kontakt hat diesen Einreiche-Link noch nicht freigegeben.')
    expect(germanSubmitError('Some links already exist in this dashboard. Choose which ones to duplicate or skip.')).toBe('Diese Links sind im Dashboard bereits vorhanden.')
    expect(germanSubmitError('Authentication credentials were not provided.')).toContain('Sitzung ist abgelaufen')
    expect(germanSubmitError('Failed to fetch')).toContain('Keine Verbindung zum Server')
  })

  it('keeps the wait time out of the throttle message instead of dropping it',()=>{
    expect(germanSubmitError('Request was throttled. Expected available in 47 seconds.')).toBe('Zu viele Einreichungen. Bitte versuche es in 47 Sekunden erneut.')
    expect(germanSubmitError('Request was throttled.')).toBe('Zu viele Einreichungen. Bitte versuche es später erneut.')
  })

  // The app does not send DRF's default throttle wording. jobradar/throttles.py returns
  // {detail:'Rate limit exceeded. Try again later.', available_in_seconds:N}, and messageText()
  // passes on only `detail` - so the seconds have to arrive as the second argument or they are lost.
  it('translates the throttle message this app actually sends, keeping the wait time',()=>{
    expect(germanSubmitError('Rate limit exceeded. Try again later.',47)).toBe('Zu viele Einreichungen. Bitte versuche es in 47 Sekunden erneut.')
    expect(germanSubmitError('Rate limit exceeded. Try again later.')).toBe('Zu viele Einreichungen. Bitte versuche es später erneut.')
    expect(germanSubmitError('Rate limit exceeded. Try again later.',0)).toBe('Zu viele Einreichungen. Bitte versuche es später erneut.')
  })

  it('never returns English for a message it does not know',()=>{
    for(const text of ['','   ',null as any,'Something exploded','{"url":["Enter a valid URL."]}'])
      expect(germanSubmitError(text)).toMatch(/^(Das Einreichen hat nicht geklappt|Bitte gib einen gültigen Link)/)
  })

  it('gives the German success and validation states their strings',()=>{
    expect(submitDe.empty).toMatch(/^Bitte füge/)
    expect(submitDe.summaryCounts(2,0,1)).toBe('2 angelegt, 0 aktualisiert, 1 übersprungen.')
    expect(submitDe.duplicates(1)).toBe('1 doppelter Link gefunden.')
    expect(submitDe.duplicates(3)).toBe('3 doppelte Links gefunden.')
    expect(submitDe.sentToFriend('Ermis')).toBe('Ermis sieht den Link jetzt im Dashboard.')
    expect([submitDe.unknownCompany,submitDe.untitledRole]).toEqual(['Unbekannte Firma','Unbenannte Position'])
  })
})
