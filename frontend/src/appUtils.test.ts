import {afterEach,describe,expect,it} from 'vitest'
import {applyDefaultHiddenPanels,BOARD_DESKTOP_QUERY,chronologicalMessages,copyToClipboard,deadlineBadge,decodeHtmlEntities,dedupeMailboxSuggestions,describeOrdering,formatAddressList,fromDateTimeLocal,germanSubmitError,groupFeedbackDueRows,groupMailboxSuggestions,groupSuggestionsByConversation,initPanelOrder,isActionableJobStatus,isDesktopWidth,mailboxAttachmentSize,mailboxCalendarWhen,mailboxEstimateWording,mailboxIndicatorState,messagePreviewLine,nextSortKeys,parseAddressList,parseSenderHeader,parseSortKeys,pathTitle,ratePercent,receivedDateLabels,selectGeneralNote,senderInitial,senderTone,sortOrderingString,sourceLabel,submitDe,toDateTimeLocal} from './appUtils'
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

// TASK-134 AC2/AC3: 44 of 598 real stored mailbox bodies contain raw entities like this exact
// snippet (quoted in the backlog task from the owner's real mail) - not a made-up string.
describe('decodeHtmlEntities',()=>{
  it('decodes a real recruiter-email fragment with &nbsp; to a space',()=>{
    expect(decodeHtmlEntities('the&nbsp;Senior Software Engineer')).toBe('the Senior Software Engineer')
  })

  it('decodes &amp; and &#39; to an ampersand and an apostrophe',()=>{
    expect(decodeHtmlEntities('Terms &amp; Conditions')).toBe('Terms & Conditions')
    expect(decodeHtmlEntities('We&#39;re hiring')).toBe("We're hiring")
    expect(decodeHtmlEntities('hex apostrophe: &#x27;')).toBe("hex apostrophe: '")
  })

  it('leaves undecorated text and null/undefined untouched',()=>{
    expect(decodeHtmlEntities('plain text, no entities')).toBe('plain text, no entities')
    expect(decodeHtmlEntities(null)).toBe('')
    expect(decodeHtmlEntities(undefined)).toBe('')
  })

  // AC3: the one place "make it look like email" and "never execute what a stranger sent me" pull
  // against each other. This is not an HTML parser - it only ever matches an "&...;" shape - so a
  // literal tag with no entity in it is returned byte-for-byte, never interpreted or stripped.
  it('never turns a literal tag into markup - the injection case',()=>{
    expect(decodeHtmlEntities('<script>alert(1)</script>')).toBe('<script>alert(1)</script>')
    expect(decodeHtmlEntities('<b>bold</b>')).toBe('<b>bold</b>')
  })

  it('decoding an escaped tag still yields plain text, never parsed markup',()=>{
    // A sender who escaped their own tag (&lt;script&gt;) gets the literal characters back - a
    // string, not DOM - so React renders it as visible text exactly like the unescaped case above.
    expect(decodeHtmlEntities('&lt;script&gt;alert(1)&lt;/script&gt;')).toBe('<script>alert(1)</script>')
  })
})

// TASK-134 AC13: real `From` headers come in several shapes - getting one wrong shows the owner a
// mangled name instead of a hidden address.
describe('parseSenderHeader',()=>{
  it('splits a plain "Name <addr>" header',()=>{
    expect(parseSenderHeader('Julia Barylak <notifications@join.zooplus.com>')).toEqual({name:'Julia Barylak',address:'notifications@join.zooplus.com'})
  })

  it('treats a bare address with no display name as address-only',()=>{
    expect(parseSenderHeader('recruiting@example.com')).toEqual({name:'',address:'recruiting@example.com'})
  })

  it('strips one layer of quotes from a quoted name containing a comma',()=>{
    expect(parseSenderHeader('"Barylak, Julia" <julia@example.com>')).toEqual({name:'Barylak, Julia',address:'julia@example.com'})
  })

  it('resolves the address from the LAST angle-bracket pair when a quoted name contains its own',()=>{
    expect(parseSenderHeader('"Weird <Name>" <addr@example.com>')).toEqual({name:'Weird <Name>',address:'addr@example.com'})
  })

  it('treats empty, null and undefined input as no sender at all',()=>{
    expect(parseSenderHeader('')).toEqual({name:'',address:''})
    expect(parseSenderHeader(null)).toEqual({name:'',address:''})
    expect(parseSenderHeader(undefined)).toEqual({name:'',address:''})
  })
})

describe('parseAddressList/formatAddressList (TASK-133)',()=>{
  it('splits on comma, semicolon, and newline, trimming each address',()=>{
    expect(parseAddressList('a@x.com, b@y.com;c@z.com\nd@w.com')).toEqual(['a@x.com','b@y.com','c@z.com','d@w.com'])
  })

  it('drops blank entries left by stray separators instead of keeping an empty address',()=>{
    expect(parseAddressList('a@x.com,,  ,b@y.com;')).toEqual(['a@x.com','b@y.com'])
  })

  it('treats empty or whitespace-only input as no addresses',()=>{
    expect(parseAddressList('')).toEqual([])
    expect(parseAddressList('   ')).toEqual([])
  })

  it('round-trips through formatAddressList as a comma-separated list',()=>{
    const addrs=['a@x.com','b@y.com']
    expect(formatAddressList(addrs)).toBe('a@x.com, b@y.com')
    expect(parseAddressList(formatAddressList(addrs))).toEqual(addrs)
  })

  it('formats an empty list as an empty string',()=>{
    expect(formatAddressList([])).toBe('')
  })
})

// TASK-134 AC9/AC14: within a thread, oldest at the top, newest at the bottom - and an
// undated message must not be mistaken for the one that started the conversation.
describe('chronologicalMessages',()=>{
  it('reverses a newest-first, all-dated list into oldest-first',()=>{
    const newestFirst=[{id:3,received_at:'2026-08-19T00:00:00Z'},{id:2,received_at:'2026-08-18T00:00:00Z'},{id:1,received_at:'2026-08-17T00:00:00Z'}]
    expect(chronologicalMessages(newestFirst).map(m=>m.id)).toEqual([1,2,3])
  })

  it('keeps a null-received_at message at the end instead of letting it jump to the start',()=>{
    // API order: newest-first with nulls last (id 1 has no received_at).
    const newestFirst=[{id:3,received_at:'2026-08-19T00:00:00Z'},{id:2,received_at:'2026-08-18T00:00:00Z'},{id:1,received_at:null}]
    expect(chronologicalMessages(newestFirst).map(m=>m.id)).toEqual([2,3,1])
  })
})

// TASK-135 AC2: fixed to Europe/Vienna and always names it, regardless of the machine running the
// test - the exact trap the AC exists to catch is a time that is right but unlabeled or wrong but
// unnoticed.
describe('mailboxCalendarWhen',()=>{
  it('names Europe/Vienna even for a same-day range',()=>{
    expect(mailboxCalendarWhen('2026-08-19T10:00:00Z','2026-08-19T11:00:00Z')).toBe('19 Aug 2026, 12:00–13:00 (Europe/Vienna)')
  })

  it('falls back to a full date+time for the end when it lands on a different Vienna day',()=>{
    expect(mailboxCalendarWhen('2026-08-19T10:00:00Z','2026-08-20T11:00:00Z')).toBe('19 Aug 2026, 12:00–20 Aug 2026, 13:00 (Europe/Vienna)')
  })

  it('shows a start-only invitation without a dangling dash',()=>{
    expect(mailboxCalendarWhen('2026-08-19T10:00:00Z',null)).toBe('19 Aug 2026, 12:00 (Europe/Vienna)')
  })

  it('is blank for a message with no invitation instead of "Invalid Date"',()=>{
    expect(mailboxCalendarWhen(null,null)).toBe('')
    expect(mailboxCalendarWhen('not a date',null)).toBe('')
  })
})

describe('mailboxAttachmentSize',()=>{
  it('formats bytes, KB and MB the way a file manager would',()=>{
    expect(mailboxAttachmentSize(512)).toBe('512 B')
    expect(mailboxAttachmentSize(2048)).toBe('2.0 KB')
    expect(mailboxAttachmentSize(5*1024*1024)).toBe('5.0 MB')
  })

  it('treats missing or zero size as empty rather than "NaN B"',()=>{
    expect(mailboxAttachmentSize(null)).toBe('0 B')
    expect(mailboxAttachmentSize(undefined)).toBe('0 B')
    expect(mailboxAttachmentSize(0)).toBe('0 B')
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

// TASK-145 AC6/AC9: the round trip a saved sort must survive, plus the truncation a value with more
// than 3 keys (e.g. a stale/tampered profile field) must get instead of silently being honoured.
describe('parseSortKeys (TASK-145)',()=>{
  it('round-trips through sortOrderingString',()=>{
    expect(parseSortKeys('status,-fit_score')).toEqual([{key:'status',dir:'asc'},{key:'fit_score',dir:'desc'}])
    expect(sortOrderingString(parseSortKeys('status,-fit_score'))).toBe('status,-fit_score')
  })

  it('treats empty, null and undefined as no sort at all',()=>{
    expect(parseSortKeys('')).toEqual([])
    expect(parseSortKeys(null)).toEqual([])
    expect(parseSortKeys(undefined)).toEqual([])
  })

  it('truncates a saved value with more than the 3-key max instead of honouring every key',()=>{
    expect(parseSortKeys('status,-fit_score,priority,-created_at')).toEqual([
      {key:'status',dir:'asc'},{key:'fit_score',dir:'desc'},{key:'priority',dir:'asc'},
    ])
  })
})

// TASK-146 AC1/AC2/AC3: the pane's grouping, tested against the shape actually measured in the task
// (an oldest-overdue job at -23d that must not sort as if it were due soonest) and the toggle that
// drops the overdue group entirely rather than only hiding it.
describe('groupFeedbackDueRows (TASK-146)',()=>{
  const rows=[
    {id:1,feedback_due_date:'2026-07-27'}, // -23d, overdue, listed first by the (already-sorted) API
    {id:2,feedback_due_date:'2026-08-18'}, // -1d, overdue
    {id:3,feedback_due_date:'2026-08-19'}, // today
    {id:4,feedback_due_date:'2026-08-21'}, // +2d
  ]

  it('splits overdue from today-or-later without re-sorting either group',()=>{
    expect(groupFeedbackDueRows(rows,'2026-08-19')).toEqual({
      overdue:[rows[0],rows[1]],
      upcoming:[rows[2],rows[3]],
    })
  })

  it('drops the overdue group entirely when the toggle is off, rather than only hiding it',()=>{
    expect(groupFeedbackDueRows(rows,'2026-08-19',false)).toEqual({overdue:[],upcoming:[rows[2],rows[3]]})
  })

  it('returns two empty groups for no rows',()=>{
    expect(groupFeedbackDueRows([],'2026-08-19')).toEqual({overdue:[],upcoming:[]})
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

// TASK-174 AC2/AC5. The board stores only the HIDDEN set, so "never chose" and "chose to show" look
// identical; the seeded list is what separates them. These are the two rules that decide it, and the
// reason they live here and not in App.tsx: no DOM is needed to test either (this vitest run has no
// jsdom), so a regression fails a test instead of waiting for someone to notice their panel came back.
describe('default-hidden dashboard panels (TASK-174 AC2/AC5)',()=>{
  it('hides a default-hidden panel for an owner who never chose, and records that it did',()=>{
    const r=applyDefaultHiddenPanels([],[],['mailbox_unmatched'])
    expect(r.hidden).toEqual(['mailbox_unmatched'])
    expect(r.seeded).toEqual(['mailbox_unmatched'])
    expect(r.changed).toBe(true)
  })

  it('leaves an owner who switched it back on switched on, instead of re-hiding it every load',()=>{
    const r=applyDefaultHiddenPanels([],['mailbox_unmatched'],['mailbox_unmatched'])
    expect(r.hidden).toEqual([])
    expect(r.changed).toBe(false)
  })

  it('keeps it hidden for an owner who hid it themselves',()=>{
    const r=applyDefaultHiddenPanels(['mailbox_unmatched'],['mailbox_unmatched'],['mailbox_unmatched'])
    expect(r.hidden).toEqual(['mailbox_unmatched'])
    expect(r.changed).toBe(false)
  })

  it('never disturbs the choices an owner already made about other panels',()=>{
    const r=applyDefaultHiddenPanels(['funnel','source_effectiveness'],[],['mailbox_unmatched'])
    expect(r.hidden).toEqual(['funnel','source_effectiveness','mailbox_unmatched'])
    expect(r.changed).toBe(true)
  })

  it('is idempotent: the second load after seeding decides nothing and writes nothing',()=>{
    const first=applyDefaultHiddenPanels([],[],['mailbox_unmatched'])
    const second=applyDefaultHiddenPanels(first.hidden,first.seeded,['mailbox_unmatched'])
    expect(second.hidden).toEqual(first.hidden)
    expect(second.seeded).toEqual(first.seeded)
    expect(second.changed).toBe(false)
  })

  it('does not duplicate an id that is somehow already in the hidden set but not seeded',()=>{
    const r=applyDefaultHiddenPanels(['mailbox_unmatched'],[],['mailbox_unmatched'])
    expect(r.hidden).toEqual(['mailbox_unmatched'])
    expect(r.changed).toBe(true)
  })

  it('does nothing at all when no panel is hidden by default',()=>{
    const r=applyDefaultHiddenPanels(['funnel'],[],[])
    expect(r.hidden).toEqual(['funnel'])
    expect(r.seeded).toEqual([])
    expect(r.changed).toBe(false)
  })
})

// TASK-119 AC1/AC2/AC7: build_suggestions can emit two rows (status_change + feedback_clear) for one
// inbound email, which is what regressed into two identical-looking cards - this is the pure grouping
// step behind the fix, so a future regression fails here instead of only being noticed in a browser.
describe('groupMailboxSuggestions (TASK-119)',()=>{
  it('groups suggestions that share one email into a single card, preserving suggestion order',()=>{
    const rejection={id:1,subject:'Absage'}
    const interview={id:2,subject:'Interview invite'}
    const s0={id:10,message:interview,suggestion_type:'interview_date'}
    const s1={id:11,message:interview,suggestion_type:'feedback_clear'}
    const s2={id:12,message:rejection,suggestion_type:'status_change'}
    expect(groupMailboxSuggestions([s0,s1,s2])).toEqual([
      {message:interview,suggestions:[s0,s1]},
      {message:rejection,suggestions:[s2]},
    ])
  })

  it('keeps a single-suggestion email as its own one-item group',()=>{
    const m={id:5}
    const s={id:20,message:m}
    expect(groupMailboxSuggestions([s])).toEqual([{message:m,suggestions:[s]}])
  })

  it('returns an empty list for no suggestions',()=>{
    expect(groupMailboxSuggestions([])).toEqual([])
  })
})

// TASK-127 AC1/AC6: nine pending suggestions across four jobs (the owner's real production numbers,
// measured 2026-08-18) is the exact case this groups for - several emails about ONE application must
// collapse into one conversation, keyed generically so the call site (not this function) decides
// whether that key is matched_job today or thread_id once history has it.
describe('groupSuggestionsByConversation (TASK-127)',()=>{
  it('groups suggestions from different emails that share one job into a single conversation, in first-seen order',()=>{
    const s0={id:1,job:10}
    const s1={id:2,job:11}
    const s2={id:3,job:10}
    expect(groupSuggestionsByConversation([s0,s1,s2],s=>s.job)).toEqual([
      {key:10,suggestions:[s0,s2]},
      {key:11,suggestions:[s1]},
    ])
  })

  it('keeps a single-suggestion job as its own one-item conversation',()=>{
    const s={id:1,job:5}
    expect(groupSuggestionsByConversation([s],s=>s.job)).toEqual([{key:5,suggestions:[s]}])
  })

  it('returns an empty list for no suggestions',()=>{
    expect(groupSuggestionsByConversation([] as {job:number}[],s=>s.job)).toEqual([])
  })

  it('keys off whatever the caller passes, so swapping matched_job for thread_id later is a one-line change at the call site',()=>{
    const s0={id:1,job:10,threadId:'t1'}
    const s1={id:2,job:11,threadId:'t1'}
    expect(groupSuggestionsByConversation([s0,s1],s=>s.threadId)).toEqual([{key:'t1',suggestions:[s0,s1]}])
  })
})

// TASK-130 AC6/AC7: job 37's real production shape - three identical feedback_clear rows (one per
// message) that must collapse into one displayed control, without merging a genuinely different
// proposal (a status_change alongside it) into that same control.
describe('dedupeMailboxSuggestions (TASK-130)',()=>{
  it('collapses duplicate (type, payload) rows from different messages into one group',()=>{
    const s0={id:653,suggestion_type:'feedback_clear',payload:{}}
    const s1={id:393,suggestion_type:'feedback_clear',payload:{}}
    const s2={id:391,suggestion_type:'feedback_clear',payload:{}}
    expect(dedupeMailboxSuggestions([s0,s1,s2])).toEqual([{key:'feedback_clear|{}',suggestions:[s0,s1,s2]}])
  })

  it('keeps a different suggestion_type as its own group even on the same job',()=>{
    const clear={id:1,suggestion_type:'feedback_clear',payload:{}}
    const status={id:2,suggestion_type:'status_change',payload:{status:'interview'}}
    expect(dedupeMailboxSuggestions([clear,status])).toEqual([
      {key:'feedback_clear|{}',suggestions:[clear]},
      {key:'status_change|{"status":"interview"}',suggestions:[status]},
    ])
  })

  it('keeps the same suggestion_type separate when the payload actually differs (two different interview dates)',()=>{
    const a={id:1,suggestion_type:'interview_date',payload:{interview_at:'2026-08-20T10:00:00Z'}}
    const b={id:2,suggestion_type:'interview_date',payload:{interview_at:'2026-08-21T10:00:00Z'}}
    expect(dedupeMailboxSuggestions([a,b])).toEqual([
      {key:'interview_date|{"interview_at":"2026-08-20T10:00:00Z"}',suggestions:[a]},
      {key:'interview_date|{"interview_at":"2026-08-21T10:00:00Z"}',suggestions:[b]},
    ])
  })

  it('keeps a single suggestion as its own one-item group, and returns an empty list for none',()=>{
    const s={id:1,suggestion_type:'feedback_clear',payload:{}}
    expect(dedupeMailboxSuggestions([s])).toEqual([{key:'feedback_clear|{}',suggestions:[s]}])
    expect(dedupeMailboxSuggestions([])).toEqual([])
  })
})

// TASK-123 AC1/AC6: the exact defect - a job with no general note must never have the board's note
// button silently adopt a differently-typed note (here, the recruiter_message audit trail
// apply_suggestion writes) as if it were the one the modal itself is editing.
describe('selectGeneralNote (TASK-123)',()=>{
  it('picks the general note even when it is not the newest',()=>{
    const notes=[{id:1,note_type:'recruiter_message'},{id:2,note_type:'general'}]
    expect(selectGeneralNote(notes)).toEqual({id:2,note_type:'general'})
  })

  it('returns null - never the newest note of another type - when no general note exists yet',()=>{
    const notes=[{id:3,note_type:'recruiter_message'}]
    expect(selectGeneralNote(notes)).toBe(null)
  })

  it('returns null for an empty or missing note list',()=>{
    expect(selectGeneralNote([])).toBe(null)
    expect(selectGeneralNote(null)).toBe(null)
    expect(selectGeneralNote(undefined)).toBe(null)
  })
})

// TASK-126: the exact defect was a job with mail history but no pending suggestion showing no
// board indicator at all -- these three cases are the whole bug, plus AC2's requirement that
// 'pending' wins even when history is also true (both can be true on a job with older decided
// suggestions and one fresh undecided one).
describe('mailboxIndicatorState (TASK-126 AC1/AC2/AC3)',()=>{
  it('is pending when a decision is waiting, regardless of older history',()=>{
    expect(mailboxIndicatorState(true,true)).toBe('pending')
    expect(mailboxIndicatorState(true,false)).toBe('pending')
    expect(mailboxIndicatorState(true,undefined)).toBe('pending')
  })

  it('is history when there is mail but every suggestion on it is decided',()=>{
    expect(mailboxIndicatorState(false,true)).toBe('history')
  })

  it('is null (no indicator) when the job has no mailbox history at all',()=>{
    expect(mailboxIndicatorState(false,false)).toBe(null)
    expect(mailboxIndicatorState(false,undefined)).toBe(null)
  })
})

// TASK-124 AC7/AC8: the wording most likely to silently drift. taking_longer_than_usual comes from
// the server and must win over every other case, including a race where elapsed has technically
// passed the estimate but the server has not flipped the flag yet - never a negative countdown.
describe('mailboxEstimateWording (TASK-124 AC7/AC8)',()=>{
  it('says so instead of inventing a number when there is no history of this kind yet',()=>{
    expect(mailboxEstimateWording(null,null,false)).toBe('No time estimate yet — this will be the first tracked run of its kind.')
    expect(mailboxEstimateWording(12,null,false)).toBe('Running — no history yet to estimate how long this takes.')
  })

  it('shows the up-front estimate before the run starts',()=>{
    expect(mailboxEstimateWording(null,245,false)).toBe('Usually takes about 4m 5s.')
    expect(mailboxEstimateWording(null,10,false)).toBe('Usually takes about 10s.')
  })

  it('counts down a live estimate while running',()=>{
    expect(mailboxEstimateWording(30,245,false)).toBe('About 3m 35s remaining.')
    expect(mailboxEstimateWording(290,300,false)).toBe('About 10s remaining.')
  })

  it('stops counting down and says it is taking longer than usual once the server says so, never a negative figure',()=>{
    expect(mailboxEstimateWording(600,245,true)).toBe('Taking longer than usual — hang tight.')
    // takingLonger wins even with numbers that would otherwise still look "in progress"
    expect(mailboxEstimateWording(1,245,true)).toBe('Taking longer than usual — hang tight.')
  })

  it('reads "finishing up" rather than a negative countdown for a close-but-not-yet-flagged race',()=>{
    expect(mailboxEstimateWording(299.5,300,false)).toBe('Finishing up…')
    expect(mailboxEstimateWording(305,300,false)).toBe('Finishing up…')
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

// TASK-143 AC1/AC2: job 760 (rejected) is the measured case this exists to hide from the mailbox
// panel, and accepted is deliberately actionable (an accepted offer still produces mail worth
// reading) - see the task's own implementation notes for why.
describe('isActionableJobStatus (TASK-143)',()=>{
  it('is actionable for every status the owner can still do something about',()=>{
    for(const s of ['new','reviewed','to_apply','applied','interview','offer','accepted'])
      expect(isActionableJobStatus(s)).toBe(true)
  })

  it('is not actionable once the application is over',()=>{
    for(const s of ['rejected','withdrawn','skipped','archived'])
      expect(isActionableJobStatus(s)).toBe(false)
  })

  it('treats an unknown or missing status as not actionable rather than guessing yes',()=>{
    expect(isActionableJobStatus(undefined)).toBe(false)
    expect(isActionableJobStatus(null)).toBe(false)
    expect(isActionableJobStatus('')).toBe(false)
  })
})

// TASK-144: a one-sided conversation needs a stable, non-owner-colliding cue per correspondent.
describe('senderTone/senderInitial (TASK-144)',()=>{
  it('always colors the owner blue, regardless of address',()=>{
    expect(senderTone('owner@example.com',true)).toBe('blue')
    expect(senderTone('',true)).toBe('blue')
  })

  it('is deterministic for the same address',()=>{
    const a=senderTone('recruiter@ashbyhq.com',false)
    const b=senderTone('recruiter@ashbyhq.com',false)
    expect(a).toBe(b)
  })

  it('falls back to slate for a blank sender instead of hashing an empty string',()=>{
    expect(senderTone('',false)).toBe('slate')
    expect(senderTone('   ',false)).toBe('slate')
  })

  it('never picks blue or slate for a real non-owner sender, so it cannot be confused with the owner',()=>{
    for(const addr of ['a@x.com','recruiter@ashbyhq.com','hiring.manager@company.io','no-reply@greenhouse.io'])
      expect(['green','purple','yellow','red']).toContain(senderTone(addr,false))
  })

  it('takes the first letter, uppercased, or a fallback for a blank name',()=>{
    expect(senderInitial('You')).toBe('Y')
    expect(senderInitial('jane doe')).toBe('J')
    expect(senderInitial('')).toBe('?')
    expect(senderInitial('   ')).toBe('?')
  })
})

// TASK-147. isDesktopWidth is the pure half of useMatchMedia's board-breakpoint decision (the DOM
// half - window.matchMedia + its change listener - needs a real browser, not this suite). The
// default breakpoint has to stay 1024px: that is the Tailwind `lg:` prefix job-table's own
// `hidden ... lg:table` / `lg:hidden` split already used, and BOARD_DESKTOP_QUERY (what App.tsx
// actually calls useMatchMedia with) has to agree with it, or the JS mount decision and the CSS
// would disagree mid-resize.
describe('isDesktopWidth (TASK-147)',()=>{
  it('treats exactly the breakpoint width as desktop, matching a min-width media query',()=>{
    expect(isDesktopWidth(1024)).toBe(true)
    expect(isDesktopWidth(1023)).toBe(false)
  })

  it('handles a narrow phone and a wide desktop viewport',()=>{
    expect(isDesktopWidth(360)).toBe(false)
    expect(isDesktopWidth(430)).toBe(false)
    expect(isDesktopWidth(1280)).toBe(true)
  })

  it('honours a custom breakpoint instead of hardcoding 1024', ()=>{
    expect(isDesktopWidth(800,768)).toBe(true)
    expect(isDesktopWidth(767,768)).toBe(false)
  })

  it('ships the same 1024px breakpoint the CSS lg: prefix uses', ()=>{
    expect(BOARD_DESKTOP_QUERY).toBe('(min-width: 1024px)')
  })
})

// TASK-177: the one-line snippet a COLLAPSED conversation message shows where its bubble would be.
describe('messagePreviewLine',()=>{
  it('squeezes the blank first line and the newlines a mail body is full of',()=>{
    expect(messagePreviewLine('\n\nSehr geehrte Damen und Herren,\n\nvielen Dank.')).toBe('Sehr geehrte Damen und Herren, vielen Dank.')
  })

  it('caps a long body and marks that it was cut',()=>{
    const out=messagePreviewLine('x'.repeat(909))
    expect(out.length).toBe(141)
    expect(out.endsWith('…')).toBe(true)
  })

  it('leaves a short body alone, with no ellipsis to decode',()=>{
    expect(messagePreviewLine('Danke, bis Montag.')).toBe('Danke, bis Montag.')
  })

  it('returns an empty string for a message with no text, so the caller can fall back',()=>{
    expect(messagePreviewLine('')).toBe('')
    expect(messagePreviewLine(null)).toBe('')
    expect(messagePreviewLine('   \n  ')).toBe('')
  })
})

// TASK-180: the conversation header overflowed 360px by up to 15px with the date at its full
// `dateStyle:'medium'` form, so a narrow viewport gets a year-less numeric date instead. These pin
// BOTH strings: a future change that quietly renders one format at every width fails here.
// Constructed in LOCAL time so the assertion holds whatever TZ the machine or CI runner is in, and
// the space before AM/PM is matched with \s because ICU 72+ emits U+202F there.
describe('receivedDateLabels',()=>{
  const at=new Date(2025,8,16,8,36).toISOString()

  it('keeps the full, year-carrying date for sm: and up',()=>{
    expect(receivedDateLabels(at,'en-US').wide).toMatch(/^Sep 16, 2025, 8:36\sAM$/)
    expect(receivedDateLabels(at,'de-AT').wide).toContain('2025')
  })

  it('drops the year below sm: and keeps the locale own day/month order',()=>{
    expect(receivedDateLabels(at,'en-US').narrow).toMatch(/^9\/16, 8:36\sAM$/)   // month-first
    expect(receivedDateLabels(at,'de-AT').narrow).toMatch(/^16\.9\., 8:36$/)      // day-first, 24h
  })

  it('is shorter narrow than wide in every locale the app is used in',()=>{
    // The reason `month:'numeric'` was chosen over `'short'`: "16. Sep., 8:36" would have saved
    // almost nothing against de-AT's "16.09.2025, 08:36".
    for(const locale of ['en-US','en-GB','de-DE','de-AT']){
      const {wide,narrow}=receivedDateLabels(at,locale)
      expect(narrow.length).toBeLessThan(wide.length)
      expect(narrow).not.toContain('2025')
    }
  })

  it('says so rather than rendering "Invalid Date" when there is no usable timestamp',()=>{
    expect(receivedDateLabels(null)).toEqual({wide:'received date unknown',narrow:'received date unknown'})
    expect(receivedDateLabels('')).toEqual({wide:'received date unknown',narrow:'received date unknown'})
    expect(receivedDateLabels('not a date')).toEqual({wide:'received date unknown',narrow:'received date unknown'})
  })
})
