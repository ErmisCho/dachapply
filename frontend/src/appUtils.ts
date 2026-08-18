// Non-component helpers used by App.tsx. They live here rather than in App.tsx because
// react-refresh disables Fast Refresh for any module that exports a non-component, and
// App.tsx is the whole app - measured: exporting copyToClipboard from it turned every
// edit into a full page reload ("Could not Fast Refresh ... export is incompatible").

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
const orderingKeyLabels:Record<string,string>={status:'Status',fit_score:'Fit score',priority:'Priority',created_at:'Newest',applied_at:'Applied date',updated_at:'Last update',feedback_due_date:'Feedback due'}
export function describeOrdering(ordering?:string|null):string{
  const keys=String(ordering||'').split(',').map(s=>s.trim()).filter(Boolean)
  if(!keys.length)return 'Sorted by: recommended'
  return 'Sorted by: '+keys.map(k=>{const desc=k.startsWith('-');const key=desc?k.slice(1):k;return (orderingKeyLabels[key]||key)+(desc?' (desc)':'')}).join(', then ')
}
