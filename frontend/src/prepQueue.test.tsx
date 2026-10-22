// TASK-312: the document queue page. No DOM here (TASK-177), so the page is read as emitted markup from a
// store snapshot, and the store (polling, actions) is driven directly with a mocked fetch and fake timers.
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {MemoryRouter} from 'react-router-dom'
import {Nav} from './App'
import {about,timeLeft} from './applicationPrep'
import {QueueView,queueAction,queueProgress,queueSnapshot,watchQueue,type QueueData,type QueueItem,type QueueSnapshot} from './PrepQueue'

const item=(extra:Partial<QueueItem>):QueueItem=>({job_id:7,company:'Acme GmbH',title:'Backend Developer',job_status:'to_apply',key:'cv-de',label:'German CV',document:'cv',language:'de',status:'queued',position:1,progress:0,eta_seconds:null,error:'',files:[],queued_at:'2026-10-19T08:00:00Z',started_at:null,finished_at:null,retry_at:null,...extra})
const fixture=():QueueData=>({concurrency:2,summary:{done:1,total:4,analyses_left:0,documents_left:3,seconds_left:1500},items:[
  item({key:'cv-de',status:'running',position:null,progress:45,eta_seconds:120}),
  item({job_id:9,company:'Beta AG',title:'Data Engineer',key:'letter-en',label:'English letter',document:'letter',language:'en',status:'queued',position:1}),
  item({job_id:9,company:'Beta AG',title:'Data Engineer',key:'message-en',label:'English message',document:'message',language:'en',status:'queued',position:2}),
  item({job_id:11,company:'Gamma',title:'SRE',key:'cv-en',label:'English CV',language:'en',status:'ready',position:null,progress:100,files:['Me-CV-Gamma-EN.pdf','Me-CV-Gamma-EN.tex'],finished_at:'2026-10-19T09:00:00Z'}),
  item({job_id:12,company:'Delta',title:'QA',key:'letter-de',label:'German letter',document:'letter',status:'failed',position:null,error:'provider down'}),
  item({job_id:13,company:'Epsilon',title:'PM',key:'cv-de',status:'cancelled',position:null}),
]})
const view=(s:Partial<QueueSnapshot>)=>renderToStaticMarkup(<MemoryRouter><QueueView snap={{data:null,error:'',busy:[],failed:null,...s}}/></MemoryRouter>)
const section=(html:string,title:string)=>html.match(new RegExp(`<section[^>]*aria-label="${title}".*?</section>`))?.[0]||''

let calls:{method:string;url:string;body:any}[]=[]
let reply:()=>{status:number;body:any}=()=>({status:200,body:fixture()})
const originalFetch=Object.getOwnPropertyDescriptor(globalThis,'fetch')
const originalDocument=Object.getOwnPropertyDescriptor(globalThis,'document')
beforeEach(()=>{
  calls=[];reply=()=>({status:200,body:fixture()})
  Object.defineProperty(globalThis,'document',{value:{cookie:''},configurable:true,writable:true})
  Object.defineProperty(globalThis,'fetch',{value:async(url:string,init:any)=>{calls.push({method:init?.method||'GET',url,body:init?.body?JSON.parse(init.body):undefined});const r=reply()
    return {ok:r.status<400,status:r.status,statusText:'',headers:{get:()=>'application/json'},json:async()=>r.body,text:async()=>JSON.stringify(r.body)}},configurable:true,writable:true})
})
afterEach(()=>{
  vi.useRealTimers()
  originalFetch?Object.defineProperty(globalThis,'fetch',originalFetch):delete (globalThis as any).fetch
  originalDocument?Object.defineProperty(globalThis,'document',originalDocument):delete (globalThis as any).document
})

describe('queue page sections',()=>{
  it('renders running, queued, done and failed/cancelled from the payload',()=>{
    const html=view({data:fixture()})
    const running=section(html,'Running')
    expect(running).toContain('German CV')
    expect(running).toContain('href="/jobs/7"')
    expect(running).toContain('Acme GmbH — Backend Developer')
    expect(running).toMatch(/<progress[^>]*value="45"/)
    expect(running).toContain('45% · about 2 min left')
    const queued=section(html,'Queued')
    expect(queued).toMatch(/#1 English letter.*#2 English message/)
    expect(queued.match(/Move to front/g)?.length).toBe(2)
    expect(queued.match(/>Cancel</g)?.length).toBe(2)
    expect(queued).not.toContain('German CV')
    const done=section(html,'Done')
    expect(done).toContain('English CV')
    expect(done).toContain('Me-CV-Gamma-EN.pdf')
    expect(done).toContain('Me-CV-Gamma-EN.tex')
    expect(done).toContain('Finished ')
    expect(done).toMatch(/href="\/jobs\/11"[^>]*>Review</)
    const failed=section(html,'Failed / cancelled')
    expect(failed).toContain('Failed: provider down')
    expect(failed).toContain('Cancelled')
    expect(failed.match(/>Retry</g)?.length).toBe(2)
    expect(html).toContain('Up to 2 documents are prepared at a time.')
  })

  it('hides empty sections and explains an empty queue',()=>{
    const html=view({data:{concurrency:1,items:[]}})
    expect(html).toContain('queued automatically once a job is analysed as apply or maybe')
    expect(html).not.toContain('<section')
    const onlyDone=view({data:{concurrency:1,items:[fixture().items[3]]}})
    expect(onlyDone).toContain('aria-label="Done"')
    for(const title of ['Running','Queued','Failed / cancelled'])expect(onlyDone).not.toContain(`aria-label="${title}"`)
    expect(onlyDone).not.toContain('queued automatically')
  })
})

describe('queue actions',()=>{
  const queued=fixture().items[1]
  for(const action of ['first','cancel','retry'] as const)it(`posts ${action} for the item and renders the returned list`,async()=>{
    const after:QueueData={concurrency:2,items:[item({job_id:99,company:'Returned Co',key:'cv-en',label:'Returned CV',status:'queued',position:1})]}
    reply=()=>({status:200,body:after})
    await queueAction(queued,action)
    expect(calls).toEqual([{method:'POST',url:'/api/jobs/application-prep/queue/action/',body:{job_id:9,key:'letter-en',action}}])
    expect(queueSnapshot().data).toEqual(after)
    expect(view(queueSnapshot())).toContain('Returned Co')
  })

  it('disables the clicked button while its request is in flight',async()=>{
    let release:()=>void=()=>{}
    const gate=new Promise<void>(resolve=>{release=resolve})
    const slow=globalThis.fetch;(globalThis as any).fetch=async(...args:any[])=>{await gate;return (slow as any)(...args)}
    const pending=queueAction(queued,'cancel')
    const during=section(view({...queueSnapshot(),data:fixture()}),'Queued')
    expect(during).toMatch(/<button[^>]*disabled=""[^>]*aria-busy="true"[^>]*>Cancel</)
    expect(during.match(/disabled=""/g)?.length).toBe(2)   // that Cancel, plus Move to front on position 1
    release();await pending
    expect(section(view({...queueSnapshot(),data:fixture()}),'Queued').match(/disabled=""/g)?.length).toBe(1)
  })

  it('shows the server detail inline on a 400 and keeps the list',async()=>{
    reply=()=>({status:200,body:fixture()})
    const stop=watchQueue(()=>{});await vi.waitFor(()=>expect(queueSnapshot().data).toEqual(fixture()));stop()
    reply=()=>({status:400,body:{detail:'That document is already running.'}})
    await queueAction(queued,'first')
    const html=view(queueSnapshot())
    expect(section(html,'Queued')).toMatch(/role="alert".*That document is already running\./)
    expect(section(html,'Done')).toContain('Me-CV-Gamma-EN.pdf')
  })
})

// TASK-313: a job whose documents cannot be prepared yet (e.g. no posting text) is listed once with its reason.
describe('usage-limit retries (TASK-317)',()=>{
  it('says when a usage-limited failed or blocked item retries by itself, and nothing for any other',()=>{
    const at=new Date(2026,9,19,18,52).toISOString()   // local 18:52, whatever the runner's timezone
    const data=fixture();data.items[4]={...data.items[4],error:'Usage limit reached; resets at 18:51.',retry_at:at}
    data.items.push(item({job_id:30,company:'Iota',key:'',label:'Documents',status:'blocked',position:null,error:'Requirements analysis failed: Usage limit reached; resets at 18:51. Press Prepare to retry.',retry_at:at}))
    const html=view({data})
    expect(section(html,'Failed / cancelled')).toContain('Failed: Usage limit reached; resets at 18:51.</p><p class="text-xs text-slate-600">Retries automatically at 18:52</p>')
    expect(section(html,'Blocked')).toContain('Retries automatically at 18:52')
    expect(view({data:fixture()})).not.toContain('Retries automatically')
  })
})

const blocked=item({job_id:21,company:'Zeta',title:'Ops Engineer',key:'',label:'Documents',document:null,language:null,status:'blocked',position:null,error:'The job has no usable posting text yet.',queued_at:null})
const withBlocked=():QueueData=>{const d=fixture();d.items.splice(3,0,blocked);return d}

describe('blocked jobs',()=>{
  it('lists a blocked job under Blocked, between Queued and Done, with its reason and a Retry button',()=>{
    const html=view({data:withBlocked()})
    const listed=section(html,'Blocked')
    expect(listed).toContain('href="/jobs/21"')
    expect(listed).toContain('Zeta — Ops Engineer')
    expect(listed).toContain('The job has no usable posting text yet.')
    expect(listed.match(/>Retry</g)?.length).toBe(1)
    expect(html.indexOf('aria-label="Queued"')).toBeLessThan(html.indexOf('aria-label="Blocked"'))
    expect(html.indexOf('aria-label="Blocked"')).toBeLessThan(html.indexOf('aria-label="Done"'))
    for(const title of ['Running','Queued','Done','Failed / cancelled'])expect(section(html,title)).not.toContain('Zeta')
  })

  it('posts retry with an empty key and renders the returned list',async()=>{
    const after:QueueData={concurrency:2,items:[item({job_id:21,company:'Zeta',title:'Ops Engineer',status:'queued',position:1})]}
    reply=()=>({status:200,body:after})
    await queueAction(blocked,'retry')
    expect(calls).toEqual([{method:'POST',url:'/api/jobs/application-prep/queue/action/',body:{job_id:21,key:'',action:'retry'}}])
    expect(queueSnapshot().data).toEqual(after)
    expect(view(queueSnapshot())).not.toContain('aria-label="Blocked"')
  })

  it('shows a failed retry inline under Blocked',async()=>{
    reply=()=>({status:400,body:{detail:'Still no posting text.'}})
    await queueAction(blocked,'retry')
    expect(section(view({...queueSnapshot(),data:withBlocked()}),'Blocked')).toMatch(/role="alert".*Still no posting text\./)
  })

  it('does not trigger the fast poll on its own',async()=>{
    vi.useFakeTimers()
    reply=()=>({status:200,body:{concurrency:2,items:[blocked,...fixture().items.slice(3)]}})
    const stop=watchQueue(()=>{},true)
    await vi.advanceTimersByTimeAsync(0)
    await vi.advanceTimersByTimeAsync(29999);expect(calls.length).toBe(1)
    await vi.advanceTimersByTimeAsync(1);expect(calls.length).toBe(2)
    stop()
  })
})

// TASK-322: a job held because its posting lacks tasks, requirements, salary or a company description.
describe('incomplete postings (TASK-322)',()=>{
  const held=item({...blocked,job_id:22,company:'Eta',incomplete:true,error:'Posting incomplete: missing salary, company description. Paste the full posting on the job page, or Continue anyway.'})
  it('offers Continue anyway beside Retry only for an incomplete blocked item',()=>{
    const d=withBlocked();d.items.push(held)
    const listed=section(view({data:d}),'Blocked')
    expect(listed.match(/>Retry</g)?.length).toBe(2)
    expect(listed.match(/>Continue anyway</g)?.length).toBe(1)
    expect(listed).toMatch(/Eta — Ops Engineer.*>Retry<\/button><button[^>]*>Continue anyway</)
    expect(view({data:fixture()})).not.toContain('Continue anyway')
  })
  it('posts continue with an empty key and renders the returned list',async()=>{
    const after:QueueData={concurrency:2,items:[item({job_id:22,company:'Eta',status:'queued',position:1})]}
    reply=()=>({status:200,body:after})
    await queueAction({...held,key:'cv-de'},'continue')
    expect(calls).toEqual([{method:'POST',url:'/api/jobs/application-prep/queue/action/',body:{job_id:22,key:'',action:'continue'}}])
    expect(queueSnapshot().data).toEqual(after)
  })
})

describe('queue polling',()=>{
  const gets=()=>calls.filter(c=>c.method==='GET').length
  it('polls every 3 s while something is queued or running, 30 s otherwise, and stops on unmount',async()=>{
    vi.useFakeTimers()
    const stop=watchQueue(()=>{},true)
    await vi.advanceTimersByTimeAsync(0);expect(gets()).toBe(1)
    await vi.advanceTimersByTimeAsync(2999);expect(gets()).toBe(1)
    await vi.advanceTimersByTimeAsync(1);expect(gets()).toBe(2)
    reply=()=>({status:200,body:{concurrency:2,items:fixture().items.slice(3)}})   // only done/failed left
    await vi.advanceTimersByTimeAsync(3000);expect(gets()).toBe(3)
    await vi.advanceTimersByTimeAsync(29999);expect(gets()).toBe(3)
    await vi.advanceTimersByTimeAsync(1);expect(gets()).toBe(4)
    stop()
    await vi.advanceTimersByTimeAsync(120000);expect(gets()).toBe(4)
  })

  it('keeps the navbar count at the slow rate when the page is not open',async()=>{
    vi.useFakeTimers()
    const stop=watchQueue(()=>{})
    await vi.advanceTimersByTimeAsync(0);expect(gets()).toBe(1)
    await vi.advanceTimersByTimeAsync(29999);expect(gets()).toBe(1)
    await vi.advanceTimersByTimeAsync(1);expect(gets()).toBe(2)
    stop()
  })
})

describe('Queue navbar link',()=>{
  const nav=(user:any)=>{
    vi.stubGlobal('localStorage',{getItem:(k:string)=>k==='dachapply_user'?JSON.stringify(user):null,setItem:()=>{},removeItem:()=>{}})
    vi.stubGlobal('window',{matchMedia:()=>({matches:true,addEventListener:()=>{},removeEventListener:()=>{}})})
    try{return renderToStaticMarkup(<MemoryRouter><Nav/></MemoryRouter>)}finally{vi.unstubAllGlobals()}
  }
  it('is shown to the CV owner with done/total and the time left while work is pending, and to nobody else',async()=>{
    await queueAction(fixture().items[1],'first')   // the store now holds the fixture: 1 running + 2 queued
    const html=nav({username:'owner',can_generate_cv:true})
    expect(html).toMatch(/href="\/queue"[^>]*>Queue <span class="whitespace-nowrap"><span[^>]*>1\/4 · about 25 min<\/span><\/span>/)
    expect(html).toContain('aria-label="Queue: 1 of 4 done, about 25 min left"')
    expect(html).toMatch(/title="German CV · Acme GmbH: about 2 min left\s+0 analyses and 3 documents left, about 25 min in total"/)
    expect(nav({username:'friend',can_generate_cv:false})).not.toContain('/queue')
  })
  it('is plain Queue when only blocked or finished items remain',async()=>{
    reply=()=>({status:200,body:{concurrency:2,summary:{done:1,total:1,analyses_left:0,documents_left:0,seconds_left:0},items:[blocked,fixture().items[3]]}})
    await queueAction(fixture().items[1],'first')
    expect(nav({username:'owner',can_generate_cv:true})).toMatch(/href="\/queue"[^>]*>Queue<\/a>/)
  })
})

// TASK-340: the navbar's estimate, in the job page's and Queue page's wording (applicationPrep.about).
describe('queue estimate text (TASK-340)',()=>{
  it('rounds to minutes, at least one, and switches to hours',()=>{
    expect([0,59,60,89,1500,3599,3600,4800].map(about)).toEqual(['about 1 min','about 1 min','about 1 min','about 1 min','about 25 min','about 1 h','about 1 h','about 1 h 20 min'])
    expect([timeLeft(120),timeLeft(4800),timeLeft(0)]).toEqual(['about 2 min left','about 1 h 20 min left',''])
  })
  it('is null while idle and lists what runs, soonest first, then what is left',()=>{
    expect(queueProgress(null)).toBeNull()
    const data:QueueData={concurrency:1,summary:{done:3,total:12,analyses_left:2,documents_left:7,seconds_left:5000},items:[
      item({key:'',label:'Analysing fit',document:null,company:'Kappa',status:'running',position:null,eta_seconds:400}),
      item({status:'running',position:null,eta_seconds:30}),item({key:'letter-de',status:'queued',eta_seconds:900})]}
    expect(queueProgress(data)).toEqual({text:'3/12 · about 1 h 23 min',label:'Queue: 3 of 12 done, about 1 h 23 min left',
      title:'German CV · Acme GmbH: about 1 min left\nAnalysing fit · Kappa: about 7 min left\n2 analyses and 7 documents left, about 1 h 23 min in total'})
  })
  it('shows each queued and pipeline row\'s finish estimate on the Queue page',()=>{
    const data=fixture();data.items[1]={...data.items[1],eta_seconds:720}
    data.items.unshift(item({job_id:41,key:'',label:'Waiting to analyse',document:null,status:'running',position:null,eta_seconds:300}))
    const html=view({data})
    expect(section(html,'Queued')).toMatch(/#1 English letter.*Ready in about 12 min/)
    expect(section(html,'Queued').match(/Ready in/g)?.length).toBe(1)   // the message has no estimate
    expect(section(html,'Running')).toMatch(/Waiting to analyse.*about 5 min left/)
  })
})

// TASK-325: the automatic pipeline's steps (TASK-324), one row per job with key '' and no document.
describe('pipeline steps (TASK-325)',()=>{
  const step=(extra:Partial<QueueItem>)=>item({job_id:40,company:'Kappa',title:'Platform Engineer',key:'',document:null,language:null,position:null,queued_at:null,...extra})
  it('lists fetching and analysing under Running without a progress bar, and a skip under Done with its fit score',()=>{
    const data=fixture();data.items.unshift(step({label:'Fetching posting',status:'running',started_at:'2026-10-21T08:00:00Z'}),step({job_id:41,label:'Analysing fit',status:'running'}))
    data.items.push(step({job_id:42,label:'Not applying',status:'skipped',error:'Skip · fit 44',finished_at:'2026-10-21T08:05:00Z'}))
    const html=view({data})
    const running=section(html,'Running')
    expect(running).toMatch(/Fetching posting.*Kappa — Platform Engineer/)
    expect(running).toContain('Analysing fit')
    expect(running.match(/<progress/g)?.length).toBe(1)   // only the German CV's
    const done=section(html,'Done')
    expect(done).toMatch(/Not applying.*href="\/jobs\/42"[^>]*>Review<.*Skip · fit 44.*Finished /)
    for(const title of ['Queued','Blocked','Failed / cancelled'])expect(section(html,title)).not.toContain('Kappa')
  })
  it('shows a daily-limit hold as Blocked with Retry, posting an empty key',async()=>{
    const held=step({label:'Documents',status:'blocked',error:'Daily limit of 50 automatic runs reached. Press Retry to run it now, or raise the limit on the Profile page.'})
    const listed=section(view({data:{concurrency:2,items:[held]}}),'Blocked')
    expect(listed).toContain('Daily limit of 50 automatic runs reached.')
    expect(listed.match(/>Retry</g)?.length).toBe(1)
    await queueAction(held,'retry')
    expect(calls).toEqual([{method:'POST',url:'/api/jobs/application-prep/queue/action/',body:{job_id:40,key:'',action:'retry'}}])
  })
})
