// Non-component helpers used by App.tsx. They live here rather than in App.tsx because
// react-refresh disables Fast Refresh for any module that exports a non-component, and
// App.tsx is the whole app - measured: exporting copyToClipboard from it turned every
// edit into a full page reload ("Could not Fast Refresh ... export is incompatible").

import {useEffect,useState} from 'react'

// TASK-147. The board mounts exactly one of its two row renderings (desktop <table> / mobile
// <article> list) instead of both at once CSS-hidden - this is what drives the choice. 1024px
// matches Tailwind's `lg:` prefix, which is what job-table's own `hidden ... lg:table` /
// `lg:hidden` split already used before this task - the mount decision has to agree with the CSS
// breakpoint or a resize could show neither (or both) briefly.
export const BOARD_DESKTOP_QUERY='(min-width: 1024px)'
// The pure half of the decision, tested directly with plain numbers - no DOM/jsdom matchMedia
// shim needed for this part.
export function isDesktopWidth(widthPx:number,breakpointPx=1024):boolean{return widthPx>=breakpointPx}
// The thin DOM-dependent wrapper: reads window.matchMedia(query).matches on mount and on every
// change (a resize across the breakpoint), unsubscribing on unmount/query change. Returns false
// outside a browser (e.g. this project's node-environment vitest run) rather than throwing.
export function useMatchMedia(query:string):boolean{
  const[matches,setMatches]=useState(()=>typeof window!=='undefined'&&typeof window.matchMedia==='function'?window.matchMedia(query).matches:false)
  useEffect(()=>{
    if(typeof window==='undefined'||typeof window.matchMedia!=='function')return
    const mql=window.matchMedia(query)
    const onChange=()=>setMatches(mql.matches)
    onChange()
    mql.addEventListener('change',onChange)
    // Measured 2026-08-19: Chrome evaluates mql.matches correctly on a viewport change but does not
    // deliver the 'change' event inside an iframe (matches flipped true->false on an iframe resize
    // across 1024px, zero events fired). A plain resize listener re-reading mql.matches covers that
    // delivery gap; in a toplevel window it is redundant and setMatches with an unchanged value is a
    // no-op re-render-wise.
    window.addEventListener('resize',onChange)
    return ()=>{mql.removeEventListener('change',onChange);window.removeEventListener('resize',onChange)}
  },[query])
  return matches
}

export async function copyToClipboard(text:string){try{if(!navigator.clipboard)return false;await navigator.clipboard.writeText(text);return true}catch{return false}}

// <input type="datetime-local"> speaks local "YYYY-MM-DDTHH:mm"; the API speaks ISO-8601 UTC.
export function toDateTimeLocal(iso?:string|null){if(!iso)return '';const d=new Date(iso);if(isNaN(d.getTime()))return '';const p=(n:number)=>String(n).padStart(2,'0');return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`}
export function fromDateTimeLocal(value?:string|null){if(!value)return null;const d=new Date(value);return isNaN(d.getTime())?null:d.toISOString()}

// Board apply-by badge. Past deadlines are red and worded differently from approaching ones -
// the backend ranks both at stale_rank -1, so the past/approaching split is only visible here.
export function deadlineBadge(daysLeft:number|null,soonDays:number){if(daysLeft===null)return null;if(daysLeft<0)return {tone:'red',label:`Deadline passed ${Math.abs(daysLeft)}d ago`};if(daysLeft>soonDays)return null;return {tone:'yellow',label:daysLeft===0?'Apply by today':`Apply in ${daysLeft}d`}}

// Funnel/source rates. `null` from /api/stats/ means the denominator was zero - nothing to measure
// yet - so it renders as an em dash. Rendering it as "0%" would claim the user converts nothing.
export function ratePercent(rate:number|null|undefined){return rate===null||rate===undefined?'—':`${rate}%`}
// The stats endpoint emits `source` raw and '' is a real bucket: jobs added without a source.
export function sourceLabel(source:string|null|undefined){return String(source||'').trim()||'Unknown source'}

// TASK-98. The audience is Austria/Germany but the owner-facing app stays English on purpose:
// only /public-submit - the one flow someone without an account is pointed at - is German.
// A strings object beats an i18n framework until a second locale or a second page needs one.
// German-only keys have no English twin here because publicMode is now always German; the
// strings /add still shows stay inline in App.tsx, so nothing below is dead copy.
export const submitDe={
  title:'Jobangebot einreichen',
  intro:'Füge einfach einen Link ein – weitere Details sind optional.',
  friendNote:(name:string)=>`Was du hier einreichst, landet direkt im Dashboard von ${name}. ${name} hat diese Verbindung einmal bestätigt, sie bleibt in deinem Konto gespeichert – du musst also nicht erneut fragen und keinen Code eingeben. Zugang zum privaten Dashboard erhältst du dadurch nicht.`,
  openNote:'Hier kannst du Job-Links einreichen. Zugang zum privaten Dashboard erhältst du dadurch nicht.',
  // TASK-101 AC3. Only shown to a visitor with no account at all - an approved friend's own login
  // already skips the invite-code check server-side (views.public_submit), so this field would be
  // noise for them.
  inviteCode:'Einladungscode',
  inviteCodePlaceholder:'Code von deinem Kontakt',
  linksLabel:'Links einfügen',
  linksPlaceholder:'Füge hier einen Job-Link ein. Du kannst auch mehrere Links einfügen, getrennt durch Leerzeichen oder Zeilenumbrüche.',
  advanced:'Erweitert / optionale Angaben',
  company:'Firma (optional)',
  jobTitle:'Position (optional)',
  location:'Ort',
  workMode:'Arbeitsform',
  workModes:{unknown:'unbekannt',onsite:'vor Ort',hybrid:'hybrid',remote:'remote'} as Record<string,string>,
  salary:'Gehaltsangabe',
  languages:'Sprachanforderungen',
  yourName:'Dein Name',
  reason:'Warum passt dieser Job deiner Meinung nach?',
  notes:'Beschreibung / Notizen',
  notesPlaceholder:'Beschreibung / Notizen – du kannst hier auch mehrere Links einfügen',
  normalizeHint:'Links wie https-www.karriere.at-jobs-7794074 werden erkannt und automatisch korrigiert.',
  submit:'Jobangebot senden',
  submitting:'Wird gesendet…',
  // Client-side check: every field on the public endpoint is optional, so an empty form used to
  // post successfully and create a nameless row instead of telling the visitor anything was wrong.
  empty:'Bitte füge mindestens einen Job-Link oder eine Beschreibung ein.',
  summaryTitle:'Zusammenfassung',
  summaryCounts:(created:number,updated:number,skipped:number)=>`${created} angelegt, ${updated} aktualisiert, ${skipped} übersprungen.`,
  created:'Angelegt',
  updated:'Aktualisiert',
  skipped:'Übersprungen',
  // views.public_submit stores a bare link as "Unknown company"/"Untitled role", so the German
  // summary of the most common submission - a link and nothing else - echoes two English
  // placeholders back unless they are swapped here on the way to the screen.
  unknownCompany:'Unbekannte Firma',
  untitledRole:'Unbenannte Position',
  linkNumber:(n:number)=>`Link Nr. ${n}`,
  sentTitle:'Gesendet ✓',
  sentToFriend:(name:string)=>`${name} sieht den Link jetzt im Dashboard.`,
  sentGeneric:'Dein Kontakt sieht den Link in Kürze.',
  sendAnother:'Weiteren Link einreichen',
  duplicates:(n:number)=>n===1?'1 doppelter Link gefunden.':`${n} doppelte Links gefunden.`,
  duplicatesBody:'Diese Links sind bereits vorhanden. Du kannst sie trotzdem einreichen oder überspringen.',
  duplicateAll:'Alle trotzdem einreichen',
  skipAll:'Alle überspringen',
  cancel:'Abbrechen',
  skipOne:'Überspringen',
  duplicateOne:'Trotzdem einreichen',
};

// The API is not localized (TASK-98 covers one page, not the backend), so every message
// /api/public/submit/ can answer with is mapped here. Anything unmapped falls back to a German
// sentence rather than leaking an English string - or a raw DRF JSON dump - into a German page.
const submitErrorsDe:[RegExp,string][]=[
  [/invalid invite code/i,'Ungültiger Einladungscode.'],
  [/has not approved this submission link/i,'Dein Kontakt hat diesen Einreiche-Link noch nicht freigegeben.'],
  [/already exist/i,'Diese Links sind im Dashboard bereits vorhanden.'],
  [/(?:throttled|rate limit exceeded)[^]*?(\d+)\s*(?:seconds?|Sekunden)/i,'Zu viele Einreichungen. Bitte versuche es in {s} Sekunden erneut.'],[/rate limit exceeded/i,'Zu viele Einreichungen. Bitte versuche es später erneut.'],[/throttled[^]*?(\d+)\s*seconds?/i,'Zu viele Einreichungen. Bitte versuche es in {s} Sekunden erneut.'],
  [/throttled/i,'Zu viele Einreichungen. Bitte versuche es später erneut.'],
  [/authentication credentials|not authenticated|invalid token/i,'Deine Sitzung ist abgelaufen. Bitte melde dich erneut an und sende den Link noch einmal.'],
  [/enter a valid url|valid job link/i,'Bitte gib einen gültigen Link ein (z. B. https://…).'],
  [/spam rejected/i,'Die Einreichung wurde als Spam abgelehnt.'],
  [/server encountered an error/i,'Auf dem Server ist ein Fehler aufgetreten. Bitte versuche es später erneut.'],
  [/failed to fetch|networkerror|load failed/i,'Keine Verbindung zum Server. Bitte prüfe deine Internetverbindung und versuche es erneut.'],
];
// waitSeconds comes from the response body, not the message: jobradar/throttles.py returns
// {detail:'Rate limit exceeded. Try again later.', available_in_seconds:N}, so the number is
// never inside the text the way DRF's own default phrasing puts it.
export function germanSubmitError(text:string,waitSeconds?:number|null){const t=String(text||'').trim();for(const[pattern,german] of submitErrorsDe){const m=t.match(pattern);if(m){const s=m[1]||(typeof waitSeconds==='number'&&waitSeconds>0?String(Math.ceil(waitSeconds)):'');return s?german.replace('Bitte versuche es später erneut.','Bitte versuche es in {s} Sekunden erneut.').replace('{s}',s):german.replace('{s}','')}}return 'Das Einreichen hat nicht geklappt. Bitte versuche es erneut.'}

// TASK-134 AC2/AC3. 44 of 598 stored mailbox bodies contain raw HTML entities (measured) - e.g.
// "the&nbsp;Senior Software Engineer" - because the source was an HTML email read as plain text.
// This decodes the entity SHAPE ("&name;" / "&#NNN;" / "&#xHEX;") to the character it stands for and
// nothing else - it is not an HTML parser, so a literal "<script>" or "<b>" (no "&...;" anywhere in
// it) passes straight through untouched as visible text (AC3). That is what makes it safe to use on
// mail from a stranger: the deliberately-NOT-supported alternative, `el.innerHTML=raw` then reading
// `.textContent`, would parse and silently strip "<b>bold</b>" down to "bold" instead of showing it
// literally, and needs `document` (fails outside a browser, e.g. this project's node-environment
// vitest run) - a plain regex needs neither. Callers must render the result as a React text child
// (the default - never dangerouslySetInnerHTML), which escapes it again on the way to the DOM.
const ASCII_SPACE=String.fromCharCode(32)
const namedHtmlEntities:Record<string,string>={
  nbsp:ASCII_SPACE,amp:'&',lt:'<',gt:'>',quot:'"',apos:"'",
  mdash:'—',ndash:'–',hellip:'…',
  lsquo:'‘',rsquo:'’',ldquo:'“',rdquo:'”',
  copy:'©',reg:'®',trade:'™',euro:'€',
  eacute:'é',egrave:'è',ecirc:'ê',uuml:'ü',ouml:'ö',auml:'ä',szlig:'ß',
}
export function decodeHtmlEntities(text:string|null|undefined):string{
  return String(text||'').replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi,(match,body)=>{
    if(body[0]==='#'){
      const codePoint=body[1]==='x'||body[1]==='X'?parseInt(body.slice(2),16):parseInt(body.slice(1),10)
      return Number.isFinite(codePoint)?String.fromCodePoint(codePoint):match
    }
    const decoded=namedHtmlEntities[body.toLowerCase()]
    return decoded===undefined?match:decoded
  })
}

// TASK-134 AC13. `sender` is the raw From header (services/mailbox.py: `parsed.get('From', '')`),
// which shows up in three shapes on real mail: `Name <addr>`, a bare `addr` with no display name at
// all, and `"Quoted, Name" <addr>` where a quoted name can itself contain commas or angle brackets.
// The regex anchors on the LAST `<...>` pair at the end of the string as the address (a quoted name
// earlier in the string is never allowed to contain an unescaped `<`/`>` of its own per RFC 5322, so
// this cannot be fooled by one) and treats everything before it as the name, stripping one layer of
// surrounding quotes. No trailing `<...>` at all -> the whole trimmed string is the address and there
// is no display name. Pure and decode-free on purpose: callers already run every stranger-supplied
// string through decodeHtmlEntities (this file) before rendering it as text, same as subject/body.
export type ParsedSender={name:string;address:string}
export function parseSenderHeader(raw:string|null|undefined):ParsedSender{
  const s=String(raw||'').trim()
  if(!s)return {name:'',address:''}
  const m=s.match(/^(.*)<([^<>]*)>\s*$/)
  if(!m)return {name:'',address:s}
  const address=m[2].trim()
  let name=m[1].trim()
  if(name.length>=2&&name.startsWith('"')&&name.endsWith('"'))name=name.slice(1,-1)
  return {name,address}
}

// TASK-177 AC1/AC2. A collapsed conversation message used to render its header row and literally
// nothing else (body bubble, calendar invite and attachment list were all gated behind `expanded`),
// so 14 of a 15-row thread read as empty rows and the owner reported the messages as missing. The
// collapsed row now renders this one-line snippet where its bubble would be. Whitespace is squeezed
// to single spaces first because a mail body's first line is often blank or a lone greeting - taking
// `slice(0,max)` off the raw text would show an empty preview and look exactly like the bug being
// fixed. The cap is on CHARACTERS, not on CSS ellipsis alone, so the preview is bounded in the DOM
// too (a screen reader reads a snippet, not the whole 909-character body of a collapsed message).
export function messagePreviewLine(text:string|null|undefined,max=140):string{
  const line=String(text||'').replace(/\s+/g,' ').trim()
  return line.length>max?line.slice(0,max).trimEnd()+'…':line
}

// TASK-180. The conversation header (MailboxConversationMessage, App.tsx) is a flex row whose avatar
// badge, date, `n/m` counter and state cue are all `shrink-0`; the sender name is the only child that
// can absorb pressure, and once it has truncated to nothing the row still overflowed 360px by up to
// 15px (measured, 8 of 15 rows of a real thread). The date is the largest compressible contributor,
// so a narrow viewport gets a year-less, locale-ordered numeric date and the wide one is kept from
// `sm:` (640px) up. Both strings are rendered and CSS picks one - the same trick TASK-177 used for
// its 'Show'/'Hide' word - because the alternative is a resize listener for a purely visual choice.
//
//                     wide (>=640px)              narrow (<640px)
//   en-US   "Sep 16, 2025, 8:36 AM"       "9/16, 8:36 AM"
//   de-AT   "16.09.2025, 08:36"           "16.9., 8:36"
//
// `month:'numeric'` rather than `'short'` because the German short month name is no shorter than the
// numeric date it replaces ("16. Sep., 8:36" saves 3 characters against de-AT's wide form, "16.9.,
// 8:36" saves 6). The exact instant stays one hover away: the header keeps `title` on the full
// `toLocaleString()`, and `sm:` and up still show the year, so nothing is only ever abbreviated.
export function receivedDateLabels(iso:string|null|undefined,locale?:string):{wide:string;narrow:string}{
  const d=iso?new Date(iso):null
  if(!d||isNaN(d.getTime()))return {wide:'received date unknown',narrow:'received date unknown'}
  return {wide:d.toLocaleString(locale,{dateStyle:'medium',timeStyle:'short'}),
    narrow:d.toLocaleString(locale,{month:'numeric',day:'numeric',hour:'numeric',minute:'2-digit'})}
}

// TASK-133 AC3. The reply/reply-all compose dialog (App.tsx) edits To/Cc as one comma-separated
// text input per field rather than a token-per-address widget - no new dependency, and it keeps
// AC3's "shown verbatim" literal: whatever text sits in the box IS what gets parsed and POSTed to
// /mailbox-messages/{id}/reply/, nothing hidden behind chips. Splits on comma, semicolon OR newline
// (all three appear as real mail clients' own address-list separators, and a newline covers a
// pasted one-per-line list); blank entries between separators are dropped rather than becoming an
// empty '' address the backend's invalid_email_addresses would then reject.
export function parseAddressList(text:string):string[]{
  return String(text||'').split(/[,;\n]+/).map(s=>s.trim()).filter(Boolean)
}
export function formatAddressList(addresses:string[]):string{
  return (addresses||[]).join(', ')
}

// TASK-134 AC9/AC14. A thread reads top-to-bottom oldest-to-newest, chat style. The API
// (`GET /jobs/{id}/mailbox/`) deliberately keeps returning newest-first with nulls LAST (other
// consumers - the board popup, the pending-decision card, the latest-run digest - rely on that
// order, so the reversal for display belongs here, not on the endpoint). Blindly `.reverse()`-ing
// that array would put the null-received_at messages (forced to the end regardless of their real
// date) at the very TOP, mislabelling an undated message as the one that started the conversation.
// Dated messages get reversed into true chronological order; a message with no known date has no
// known chronological position, so it stays at the END (closest to "now") rather than jumping to the
// START - the less misleading of the two guesses, and it keeps index 0 meaning "earliest known".
export function chronologicalMessages<T extends {received_at:string|null}>(newestFirst:T[]):T[]{
  const dated=newestFirst.filter(m=>m.received_at)
  const undated=newestFirst.filter(m=>!m.received_at)
  return [...dated].reverse().concat(undated)
}

// TASK-135 AC2: fixed to Europe/Vienna - the SAME clock the settings page already documents for
// quiet hours ("Interpreted in Europe/Vienna time (the server's own clock)") - rather than the
// browser's local timezone, and the name is always appended to the output because an unnamed local
// time is exactly the "an hour out" trap this AC exists to avoid. `calendar_end` is optional (an
// invitation can lack DTEND); when present and on the same Vienna calendar day as the start, only
// its time is shown to keep a same-day meeting on one line.
export function mailboxCalendarWhen(start:string|null|undefined,end:string|null|undefined):string{
  if(!start)return ''
  const s=new Date(start)
  if(Number.isNaN(s.getTime()))return ''
  const dtOpts:Intl.DateTimeFormatOptions={timeZone:'Europe/Vienna',dateStyle:'medium',timeStyle:'short'}
  const startLabel=s.toLocaleString('en-GB',dtOpts)
  const e=end?new Date(end):null
  if(!e||Number.isNaN(e.getTime()))return `${startLabel} (Europe/Vienna)`
  const dateOpts:Intl.DateTimeFormatOptions={timeZone:'Europe/Vienna'}
  const sameDay=s.toLocaleDateString('en-GB',dateOpts)===e.toLocaleDateString('en-GB',dateOpts)
  const endLabel=sameDay?e.toLocaleTimeString('en-GB',{timeZone:'Europe/Vienna',hour:'2-digit',minute:'2-digit'}):e.toLocaleString('en-GB',dtOpts)
  return `${startLabel}–${endLabel} (Europe/Vienna)`
}

// TASK-135 AC3: metadata-only attachment size (bytes, from services.mailbox - see MailboxMessage's
// docstring for why there is no file content behind it) formatted the way a file manager would.
export function mailboxAttachmentSize(bytes:number|null|undefined):string{
  if(!bytes||bytes<=0)return '0 B'
  const units=['B','KB','MB','GB']
  let n=bytes,i=0
  while(n>=1024&&i<units.length-1){n/=1024;i++}
  return `${i===0?n:n.toFixed(1)} ${units[i]}`
}

// TASK-108. Pure cycle for the board's sortable column headers: unsorted -> ascending ->
// descending -> unsorted, appending a newly-activated column as the lowest-precedence key rather
// than replacing what is already sorted (that append-not-replace behaviour is the one thing worth
// a test - everything else here is a straight lookup). Capped at 3 client-side too, dropping the
// oldest (lowest-precedence) key first, matching the server's own cap so the UI never implies a
// 4th key does anything.
export type SortKey={key:string;dir:'asc'|'desc'}
export function nextSortKeys(current:SortKey[],key:string,max=3):SortKey[]{
  const i=current.findIndex(k=>k.key===key)
  const next=[...current]
  if(i<0){next.push({key,dir:'asc'});return next.length>max?next.slice(next.length-max):next}
  if(next[i].dir==='asc'){next[i]={key,dir:'desc'};return next}
  next.splice(i,1)
  return next
}
export function sortOrderingString(keys:SortKey[]):string{return keys.map(k=>(k.dir==='desc'?'-':'')+k.key).join(',')}
// TASK-145 AC6/AC9. Inverse of sortOrderingString: turns the wire string ("status,-fit_score") back
// into SortKey[]. This is what lets the board's header arrows be DERIVED from `f.ordering` instead of
// tracked in a second `useState` that can drift from it - today's bug is exactly that drift (sortKeys
// resets to [] on reload while f.ordering survives via localStorage, so the two disagree). Extra keys
// beyond `max` are dropped, the same 3-key cap nextSortKeys already enforces when building the string,
// so a saved value with more keys (e.g. tampered or from an older cap) is truncated rather than honoured.
export function parseSortKeys(ordering?:string|null,max=3):SortKey[]{
  const keys=String(ordering||'').split(',').map(s=>s.trim()).filter(Boolean).map(k=>k.startsWith('-')?{key:k.slice(1),dir:'desc' as const}:{key:k,dir:'asc' as const})
  return keys.slice(0,max)
}

// TASK-117 AC3. The dashboard's saved panel order puts known ids first and appends anything the
// saved list does not know about at the END - so a panel id added after a user already has a saved
// order (e.g. mailbox_review, shipped after most users had already dragged panels around) lands
// LAST for every one of them, never first. This puts unknown ids at the FRONT instead; a user with
// no saved order yet gets allIds back unchanged.
export function initPanelOrder(saved:string[],allIds:string[]):string[]{
  const known=saved.filter(x=>allIds.includes(x))
  const unknown=allIds.filter(x=>!saved.includes(x))
  return [...unknown,...known]
}

// TASK-174 AC2/AC5. A panel that is hidden BY DEFAULT needs a distinction the board's storage does
// not have: `dachapply_dashboard_panel_hidden` records only the hidden SET, so "the owner never
// chose" and "the owner deliberately switched it on" are the same absence. Re-applying the default
// on every load would therefore re-hide a panel the owner had just turned on; applying it never
// would mean it is only off for someone whose localStorage is empty.
// `seeded` is the second list that resolves it - the panel ids whose default has already been
// applied once:
//   id NOT in seeded -> never chose -> the default applies, and the id is recorded as seeded.
//   id IN seeded     -> whatever `hidden` says is the owner's own decision -> left exactly alone.
// So an existing owner who had hidden (or shown) any panel keeps that choice untouched, and a
// brand-new account gets the default once. Pure: the caller does the two localStorage writes, and
// only when `changed` - the point of the flag is that a load which decides nothing writes nothing.
export function applyDefaultHiddenPanels(hidden:string[],seeded:string[],defaultHidden:string[]):{hidden:string[];seeded:string[];changed:boolean}{
  const unseeded=defaultHidden.filter(id=>!seeded.includes(id))
  if(!unseeded.length)return {hidden,seeded,changed:false}
  return {hidden:[...new Set([...hidden,...unseeded])],seeded:[...seeded,...unseeded],changed:true}
}

// TASK-181. The per-panel `⋮` menu is gone, so these two are the whole of "rearrange the board":
// reorderPanels backs the pointer path (drag one panel onto another) and movePanelInOrder backs the
// keyboard path (the Move left / Move right buttons in the Panels menu). Both are pure and live here
// because this vitest run has no DOM, so the ordering rules get a test even though the gestures
// themselves can only be measured in a browser.
//
// movePanelInOrder steps to the next VISIBLE neighbour rather than to index i±1. `order` holds hidden
// panels too (that is how a panel keeps its place while switched off), so a plain swap can trade
// places with a panel nobody can see - the board would not move and the button would read as broken.
// TASK-174 makes that the default state, not an edge case: mailbox_unmatched sits hidden at the end
// of a fresh order, so a bare i+1 on source_effectiveness would visibly do nothing on day one.
export function movePanelInOrder(order:string[],hidden:string[],id:string,dir:number):string[]{
  const i=order.indexOf(id)
  if(i<0)return order
  const visible=order.filter(x=>!hidden.includes(x))
  const vj=visible.indexOf(id)+dir
  if(visible.indexOf(id)<0||vj<0||vj>=visible.length)return order
  const j=order.indexOf(visible[vj])
  const next=[...order]
  ;[next[i],next[j]]=[next[j],next[i]]
  return next
}

// Drop semantics, unchanged from the inline version this replaces: the dragged panel is lifted out
// and re-inserted BEFORE the panel it was dropped on. Dropping a panel on itself, or either id being
// unknown, returns the order untouched rather than throwing - a drag can end on anything.
export function reorderPanels(order:string[],dragged:string|null,target:string):string[]{
  if(!dragged||dragged===target||!order.includes(dragged)||!order.includes(target))return order
  // Direction matters, and getting it wrong makes the commonest gesture do nothing. Inserting
  // ALWAYS before the target is a no-op for a forward drag onto the very next panel: removing the
  // dragged id shifts the target left into the slot just vacated, so "before the target" is where
  // the panel already was. Measured on the owner's board - dragging `total` onto its right-hand
  // neighbour left the order byte-identical. Dragging one slot right is the first thing anyone
  // tries, so it has to land: moving FORWARD inserts after the target, moving BACKWARD before it.
  const forward=order.indexOf(dragged)<order.indexOf(target)
  const next=order.filter(x=>x!==dragged)
  next.splice(next.indexOf(target)+(forward?1:0),0,dragged)
  return next
}

// TASK-183 AC1/AC2/AC5. The live arrangement shown WHILE a panel is being dragged. There is exactly
// one ordering computation in the whole gesture and it is this one: `drop` saves `order` verbatim
// instead of calling reorderPanels a second time, so what the owner released over is byte-identical
// to what is stored. That is not just tidiness - a second call would DISAGREE. The preview is a
// CHAIN of moves applied to what is currently on screen, and one step recomputed from the saved
// order gives a different answer as soon as the cursor has visited more than one panel: from
// ['a','b','c','d'], dragging 'c' over 'b' and then over 'b' again returns the original order,
// while a single step from the saved order would put 'c' in front of 'b'.
//
// Chaining off what is on screen is also what keeps it still. The grid rearranges under the cursor,
// so the panel now sitting under the pointer is usually the DRAGGED one; measured against the saved
// order that would undo the move, re-run on the next dragover, and oscillate at pointer speed.
// Against the current preview it is dragged===target, which reorderPanels already returns unchanged.
//
// `over` is why this is a struct rather than a bare array. reorderPanels is deliberately NOT
// idempotent (applying the same target twice moves the panel back past it), and dragover fires
// continuously - tens of times a second - on whichever element the pointer is over. Repeating a
// target therefore returns the SAME OBJECT, which skips the second application and lets React's
// setState bail out without re-rendering the grid, instead of needing a throttle.
//
// `moved` is AC5: a drag that changes nothing (dropped back on itself, or dragged out and back)
// must not signal a move. Compared by content, not by reference, because the chain can return to
// the saved arrangement through a fresh array.
export type PanelDragPreview={order:string[];over:string;moved:boolean}
export function previewPanelDrag(current:PanelDragPreview|null,saved:string[],dragged:string|null,target:string,hidden:string[]=[]):PanelDragPreview|null{
  if(!dragged)return current
  if(current&&current.over===target)return current
  const order=reorderPanels(current?current.order:saved,dragged,target)
  // `moved` drives the "Drops here" badge and the outline, so it has to answer "will the owner SEE
  // anything change", not "did the array change". Those differ: the saved order carries hidden
  // panels too (TASK-174 leaves mailbox_unmatched in it), so a chain of drags can land the visible
  // panels exactly where they started while a hidden id sits at a different index. Measured on the
  // owner's board - dragging a panel out and back restored the visible arrangement, and the badge
  // still promised a move that could not happen. Compare the visible projection only.
  const seen=(list:string[])=>list.filter(x=>!hidden.includes(x)).join(',')
  return {order,over:target,moved:seen(order)!==seen(saved)}
}

// TASK-119 AC2/AC6/AC7. build_suggestions (mailbox.py) can emit more than one MailboxSuggestion for
// the same inbound email (e.g. a status_change alongside a feedback_clear whenever the job has a
// feedback clock running), and MailboxSuggestion.message is a full nested copy per suggestion - so
// grouping client-side by s.message.id turns N suggestion rows sharing one email into ONE card, with
// no backend change. Order is first-seen message order (whatever order the flat list already arrived
// in) and suggestions keep their own order within a group; nothing here re-sorts either.
export type MailboxSuggestionGroup<S extends {message:{id:number}}>={message:S['message'];suggestions:S[]}
export function groupMailboxSuggestions<S extends {message:{id:number}}>(suggestions:S[]):MailboxSuggestionGroup<S>[]{
  const groups:MailboxSuggestionGroup<S>[]=[]
  const byMessageId=new Map<number,MailboxSuggestionGroup<S>>()
  for(const s of suggestions){
    let group=byMessageId.get(s.message.id)
    if(!group){group={message:s.message,suggestions:[]};byMessageId.set(s.message.id,group);groups.push(group)}
    group.suggestions.push(s)
  }
  return groups
}

// TASK-127 AC1/AC6. The dashboard panel and /mailbox page work off the FLAT /mailbox-suggestions/
// list (one row per suggestion, each carrying its own message and job), so several emails about one
// application render as several separate cards unless something groups them first - the owner's
// mental unit is the exchange with a company about a role (`matched_job`), not the individual email
// TASK-119's groupMailboxSuggestions already collapses duplicate suggestions on top of.
// Keyed by a caller-supplied function rather than a hardcoded `s.job`, so swapping in Gmail's
// `thread_id` once it is backfilled onto the historic rows (5 of 653 today - see TASK-121) is a
// one-line change at the call site, not a rewrite here. Order is first-seen conversation order;
// suggestion order within a conversation is preserved too - nothing here re-sorts either.
export type MailboxConversationGroup<S>={key:number|string;suggestions:S[]}
export function groupSuggestionsByConversation<S>(suggestions:S[],keyOf:(s:S)=>number|string):MailboxConversationGroup<S>[]{
  const groups:MailboxConversationGroup<S>[]=[]
  const byKey=new Map<number|string,MailboxConversationGroup<S>>()
  for(const s of suggestions){
    const key=keyOf(s)
    let group=byKey.get(key)
    if(!group){group={key,suggestions:[]};byKey.set(key,group);groups.push(group)}
    group.suggestions.push(s)
  }
  return groups
}

// TASK-130 AC6/AC7. build_suggestions (backend) got a "does a pending one already exist for this
// (job, type)" guard so it stops CREATING duplicates - but the conversation card still has to cope
// with whatever is already in the database (the pre-cleanup rows AC2 removes) or any edge case that
// slips past that guard, so the display side gets the same dedupe as a safety net: every pending
// suggestion in a conversation with the same suggestion_type AND payload collapses into ONE group,
// keyed on that pair (not on message, which is the whole point - three messages, one control).
// AC7: this only groups for DISPLAY. Confirming/dismissing a group is the caller's job (not this
// function's) - it must still fire one confirm/dismiss call per suggestion id in the group, never a
// single batched call, so a partial failure never silently leaves some rows pending.
export type MailboxSuggestionDedupGroup<S extends {suggestion_type:string;payload:Record<string,any>}>={key:string;suggestions:S[]}
export function dedupeMailboxSuggestions<S extends {suggestion_type:string;payload:Record<string,any>}>(suggestions:S[]):MailboxSuggestionDedupGroup<S>[]{
  const groups:MailboxSuggestionDedupGroup<S>[]=[]
  const byKey=new Map<string,MailboxSuggestionDedupGroup<S>>()
  for(const s of suggestions){
    const key=s.suggestion_type+'|'+JSON.stringify(s.payload||{})
    let group=byKey.get(key)
    if(!group){group={key,suggestions:[]};byKey.set(key,group);groups.push(group)}
    group.suggestions.push(s)
  }
  return groups
}

// TASK-123. The board's note button must only ever load/edit/delete a note it created itself - a
// `general` note - never adopt a note of a different type (e.g. the `recruiter_message` audit note
// apply_suggestion has written on every confirmed email suggestion since TASK-117) just because it
// happens to be the newest note on the job (ApplicationNote.Meta.ordering is newest-first). Returns
// null when there is no general note yet, so the modal starts a fresh one instead of silently
// retyping - and, on an empty save, deleting - a note it never wrote.
// `any` return rather than a generic: the one real caller passes an untyped API response
// (App.tsx's `api()` has no typed return), and TypeScript substitutes a generic's constraint - not
// `any` - for a type parameter it cannot infer, which would wrongly narrow the result to
// {note_type:string} and reject reading `.note`/`.id` off it.
export function selectGeneralNote(notes:{note_type:string}[]|null|undefined):any{
  return (notes||[]).find(n=>n.note_type==='general')||null
}

// TASK-126 AC1/AC2/AC3: the board's mail trigger has three states -- a pending decision (unchanged
// from TASK-117), history with nothing pending (new: TASK-120's per-job view was otherwise only
// reachable while a decision was waiting), or no mailbox history at all (render nothing, AC3 --
// the board must not grow an inert icon on every row). Pulled out as its own pure branch, with its
// own test, because AC2 is explicit that collapsing 'pending' and 'history' into one look dilutes
// the actionable signal -- a regression here should fail a test, not wait for a browser check.
export type MailboxIndicatorState='pending'|'history'|null
export function mailboxIndicatorState(hasPendingSuggestion:boolean,hasMailboxHistory?:boolean):MailboxIndicatorState{
  return hasPendingSuggestion?'pending':hasMailboxHistory?'history':null
}

const routeTitles:Record<string,string>={'/':'Board','/add':'Add job','/public-submit':submitDe.title,'/prompts':'Prompts','/import':'Import','/followups':'Follow-ups','/export':'Export','/bookmarklet':'Bookmarklet','/practice':'Practice','/mailbox':'Mailbox','/login':'Sign in','/onboarding':'Setup','/privacy':'Privacy','/terms':'Terms','/settings/profile':'Profile settings','/settings/account':'Account settings'};
export function pathTitle(pathname:string){return routeTitles[pathname]||(pathname.startsWith('/jobs/')?'Job':pathname.startsWith('/reset-password/')?'Reset password':pathname.startsWith('/verify-email/')?'Confirm email':'')}

// TASK-143 AC1 (frontend mirror). JobLead.STATUSES (backend) splits into "still worth acting on"
// and not; this is the single frontend copy of that split - the Dashboard panel and the /mailbox
// page both import it rather than re-typing the list, so it can only be wrong in one place. Mirrors
// the backend's own actionable-status constant (models.py); if that ever changes, this drifts until
// someone updates it too, same as every other cross-language constant in this app (see
// board_thresholds for the pattern of shipping such a value from the server instead, not done here
// because this list is small and rarely-changing enough that TASK-143 chose not to wire a new field
// for it - see that task for the reasoning).
export const mailboxActionableJobStatuses=['new','reviewed','to_apply','applied','interview','offer','accepted']
// TASK-143 AC1: the list has one home, JobLead.ACTIONABLE_STATUSES, and reaches the client through
// /api/auth/me/'s board_thresholds like unapplied_statuses already does. `known` is that shipped
// list; the export above stays only as the pre-auth fallback the threshold merge needs, never as a
// second source of truth to drift from.
export function isActionableJobStatus(status?:string|null,known:string[]=mailboxActionableJobStatuses):boolean{return known.includes(status||'')}

// TASK-144. Nine of the twelve busiest conversations have zero owner-sent messages (see that task),
// so the left/right alignment carries no information for them - everything is on the left. The
// sender name text already disambiguates who wrote a given message; this adds a cheap, purely visual
// second cue (a colored initial, Badge's own six tones, never a new color) so a column of same-side
// bubbles from different correspondents (a recruiter, then an ATS no-reply, then a hiring manager)
// still reads as more than one voice. Deterministic per address so it never flickers between renders
// or reloads. 'blue' is reserved for the owner (matches their own bubble color) and 'slate' for a
// blank/unknown sender; only four tones are hashed across everyone else, so an occasional collision
// between two strangers is possible and harmless - it is a legibility aid, not an identity system.
const senderToneOrder=['green','purple','yellow','red'] as const
export function senderTone(senderKey:string,isOwner:boolean):string{
  if(isOwner)return 'blue'
  const key=(senderKey||'').trim().toLowerCase()
  if(!key)return 'slate'
  let hash=0
  for(let i=0;i<key.length;i++)hash=(hash*31+key.charCodeAt(i))|0
  return senderToneOrder[Math.abs(hash)%senderToneOrder.length]
}
export function senderInitial(displayName:string):string{
  const t=(displayName||'').trim()
  return t?t[0].toUpperCase():'?'
}

// TASK-124 AC7/AC8. The one place estimate wording is decided, so a UI change can never silently
// invent a countdown that goes negative or keep counting down past the estimate.
// `takingLonger` is /api/mailbox-runs/status/'s own `taking_longer_than_usual` -- computed
// server-side and passed through verbatim, never re-derived here (a client clock a poll-interval
// behind the server could otherwise flip it back to a countdown one tick before the server does).
function formatDurationSeconds(seconds:number):string{
  const total=Math.max(0,Math.round(seconds))
  if(total<60)return `${total}s`
  const minutes=Math.floor(total/60),rest=total%60
  return rest===0?`${minutes}m`:`${minutes}m ${rest}s`
}
export function mailboxEstimateWording(elapsedSeconds:number|null,estimatedSeconds:number|null,takingLonger:boolean):string{
  if(takingLonger)return 'Taking longer than usual — hang tight.'
  if(estimatedSeconds===null||estimatedSeconds===undefined)
    return elapsedSeconds===null?'No time estimate yet — this will be the first tracked run of its kind.':'Running — no history yet to estimate how long this takes.'
  if(elapsedSeconds===null)return `Usually takes about ${formatDurationSeconds(estimatedSeconds)}.`
  const remaining=estimatedSeconds-elapsedSeconds
  return remaining<1?'Finishing up…':`About ${formatDurationSeconds(remaining)} remaining.`
}

// TASK-111 AC4. Below 1024px the sortable column headers do not render at all (hidden ... lg:table),
// so the board's only sort control is the preset <select> -- but a select's own displayed label only
// matches the applied sort when the value happens to equal one of its hardcoded <option>s. Sorting
// via the (desktop-only) headers and then narrowing the viewport can leave `f.ordering` on a
// combination no preset spells out. This reads the same comma-separated `-key` wire string TASK-108
// both writes and sends as `ordering`, so what is on screen cannot drift from what the request says.
// Exported (not just used by describeOrdering below) so TASK-145 AC5's settings-menu sort editor can
// build its own column buttons from this SAME key/label map instead of retyping the list a third time
// (the board's own <select> options are the second, already-existing, copy).
export const orderingKeyLabels:Record<string,string>={status:'Status',fit_score:'Fit score',priority:'Priority',created_at:'Newest',applied_at:'Applied date',updated_at:'Last update',feedback_due_date:'Feedback due'}
export function describeOrdering(ordering?:string|null):string{
  const keys=String(ordering||'').split(',').map(s=>s.trim()).filter(Boolean)
  if(!keys.length)return 'Sorted by: recommended'
  return 'Sorted by: '+keys.map(k=>{const desc=k.startsWith('-');const key=desc?k.slice(1):k;return (orderingKeyLabels[key]||key)+(desc?' (desc)':'')}).join(', then ')
}

// TASK-146 AC1/AC2/AC3. Splits GET /jobs/feedback-due/'s rows into overdue (< today) and
// today-or-later, in the two groups the pane renders - a pure function so the grouping has a test
// independent of any browser measurement. Deliberately does NOT trust whatever marker key the backend
// sends to distinguish the two (the exact field name is not nailed down in the contract) - comparing
// feedback_due_date to todayIso is unambiguous and needs no coordination with the backend's naming.
// Relative order within each group is preserved as returned (the endpoint is already sorted
// overdue-group-first then soonest-first), so a job 23 days overdue never gets re-sorted as if it were
// due soonest just because this function ran. `includeOverdue=false` (AC3's toggle) drops the group
// entirely rather than only hiding it visually, so turning it off really means zero overdue rows shown.
export function groupFeedbackDueRows<T extends {feedback_due_date:string}>(rows:T[],todayIso:string,includeOverdue=true):{overdue:T[];upcoming:T[]}{
  const overdue=includeOverdue?rows.filter(r=>r.feedback_due_date<todayIso):[]
  const upcoming=rows.filter(r=>r.feedback_due_date>=todayIso)
  return {overdue,upcoming}
}

// TASK-173. Viewport coordinates for a popup laid out below its trigger - the row feedback editor,
// and TASK-178's note preview. The popup is portalled to <body> and laid out `position:fixed` now,
// so it is no longer positioned by the table wrapper that used to be its offset parent - the clamping that ancestor gave it for free has to be arithmetic here. Pure on
// purpose: this vitest run has no DOM, so the clamping is tested with plain numbers.
// 352px is `w-[22rem]`, the width the popup has always had; the trigger's rect supplies the rest, so
// `left` is the trigger's left edge and `top` its bottom edge + 8px - what `left-0 top-full mt-2`
// resolved to while it was an absolutely-positioned child.
// 300 is the popup's approximate height (heading + three labelled inputs + Done). It is only used to
// stop the bottom edge falling off a short viewport; being a little wrong shifts the popup by a few
// pixels near the bottom of the screen and nothing else, and `overflow-auto` on the popup handles the
// case where its real content is taller.
// TASK-178 reuses this for the note preview rather than copying the clamp: same box-below-an-anchor
// geometry, different box (320x96 instead of 352x300), so the size became two defaulted parameters
// and the name stopped naming one caller. The defaults are the feedback popup's original constants,
// so its behaviour is unchanged.
export const FEEDBACK_POPUP_WIDTH=352
export const NOTE_PREVIEW_WIDTH=320
export function popupBelowAnchor(rect:{left:number;bottom:number},viewportW:number,viewportH:number,boxW=FEEDBACK_POPUP_WIDTH,boxH=300){
  const width=Math.min(boxW,viewportW-32)
  return {
    left:Math.max(16,Math.min(rect.left,viewportW-width-16)),
    top:Math.max(16,Math.min(rect.bottom+8,viewportH-boxH-16)),
    width,
  }
}

// TASK-178. `note_preview` is the list API's first line of a job's non-empty `general` note, already
// truncated at 140 characters server-side; it is the empty string when the job has no note, and the
// board derives "this row has a note" from that emptiness - there is deliberately no second boolean.
// Run through messagePreviewLine anyway (same 140 cap, TASK-177) so a note whose first line is
// whitespace, or a response from a backend that has not shipped the truncation yet, still yields one
// bounded line rather than a blank tooltip or a wall of text. Missing field -> '' -> no indicator,
// which is what an older backend should produce: the pre-TASK-178 board showed the button on all 69
// rows while only 12 of 83 jobs had a note, so silence is the safer of the two wrong answers.
export function jobNotePreview(job:{note_preview?:string|null}):string{
  return messagePreviewLine(job.note_preview)
}
