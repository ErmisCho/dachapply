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

const routeTitles:Record<string,string>={'/':'Board','/add':'Add job','/public-submit':submitDe.title,'/prompts':'Prompts','/import':'Import','/followups':'Follow-ups','/export':'Export','/bookmarklet':'Bookmarklet','/login':'Sign in','/onboarding':'Setup','/privacy':'Privacy','/terms':'Terms','/settings/profile':'Profile settings','/settings/account':'Account settings'};
export function pathTitle(pathname:string){return routeTitles[pathname]||(pathname.startsWith('/jobs/')?'Job':pathname.startsWith('/reset-password/')?'Reset password':pathname.startsWith('/verify-email/')?'Confirm email':'')}
