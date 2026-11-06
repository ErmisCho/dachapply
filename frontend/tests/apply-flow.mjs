import assert from 'node:assert/strict'
import {spawn} from 'node:child_process'
import {after,before,test} from 'node:test'
import {chromium} from 'playwright'

// TASK-351/352/353. The real board, job page and Stats page; only the API boundary is synthetic,
// and the fixture is sized like the measured account: 11 ready, 28 skip-recommended, 179 jobs.
// Run: npm run test:board (install Chromium with npx playwright install chromium).
const port=4388,url=`http://127.0.0.1:${port}`
const server=spawn(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',String(port),'--strictPort'],{stdio:'pipe'})
let output='',browser
server.stdout.on('data',data=>{output+=data})
server.stderr.on('data',data=>{output+=data})
const user={username:'flow-test',can_generate_cv:true,is_staff:true}
const row=(id,status,fit=80)=>({id,company:`Company ${id}`,title:`Engineer ${id}`,status,latest_fit_score:fit})
const skipRows=Array.from({length:28},(_,i)=>({id:500+i,company:`Skip ${i}`,title:`Skip role ${i}`}))
const nextUp=Array.from({length:6},(_,i)=>row(i+1,'ready_to_submit',90-i))
const bands=[['80+',6,1,2],['70-79',9,2,3],['60-69',4,1,1],['Under 60',2,0,1],['No score',3,2,0]].map(([band,applications,interviews,rejections])=>({band,applications,interviews,rejections}))
const counts={applications:24,interviews:6,offers:0,waiting:12,applied_to_interview_rate:25,interview_to_offer_rate:0}
const stats=()=>({total_jobs:179,funnel:{recent_window_days:90,recent_window_start:'2026-08-08',all_time:counts,recent:counts,interviews_without_application:5,fit_bands:bands},next_up:nextUp,next_up_total:39,skip_recommended_new:skipRows,month_week_applications:[],workday_applications:[]})
const suggestion=id=>({id,job:id,job_company:`Mail ${id}`,job_title:'Backend Engineer',suggestion_type:'status_change',payload:{status:'interview'},status:'pending',created_at:'2026-10-01T10:00:00Z',decided_at:null,postponed_until:null,message:{id,sender:'"Jane Recruiter" <jane@synthetic.test>',subject:'Invitation'}})
const boardRows=Array.from({length:30},(_,i)=>({...row(i+1,'ready_to_submit'),location:'Vienna',work_mode:'remote',url:'',skill_matches:[],missing_skills:[],created_at:'2026-10-01T10:00:00Z'}))
const detail=()=>({id:1,company:'Company 1',title:'Engineer 1',status:'ready_to_submit',url:'https://jobs.example.test/1',location:'Vienna',work_mode:'remote',salary_info:'',language_requirements:'',raw_description:'Synthetic text',original_source_text:'Synthetic text',latest_evaluation:null,application_requirements:null,created_at:'2026-10-01T10:00:00Z'})
const letter=(key,label,recommended=false)=>({key,document:'letter',language:'de',letter_label:label,recommended,status:'ready',files:{letter_tex:`C:\\ws\\${key}.tex`}})
const prep={reason:'',rule:'Rule',model:{},selection:[],variants:[{key:'cv-de',document:'cv',language:'de',status:'ready',files:{cv_pdf:'C:\\ws\\cv.pdf'}},letter('letter-a','Anschreiben'),letter('letter-b','Motivationsschreiben',true)]}

const preview=job=>({configured:true,job:{...job,source_text:'Synthetic job description',pending_source_text:''},cvs:[{key:'english',label:'English'},{key:'german',label:'German'}],letters:[],models:[{provider:'openai',key:'fixture',label:'Fixture',efforts:['low'],default_effort:'low'}],selected_cv:'english',selected_letter:'',default_pick:{provider:'openai',model:'fixture',effort:'low',speed:'normal'}})

async function open(path,{width=1366,height=768,storage={},api={}}={}){
  const context=await browser.newContext({viewport:{width,height}})
  await context.grantPermissions(['clipboard-read','clipboard-write'],{origin:url})
  await context.route('https://jobs.example.test/**',route=>route.fulfill({contentType:'text/html',body:'Synthetic posting'}))
  const page=await context.newPage()
  page.setDefaultTimeout(5000)
  const seen={errors:[],writes:[]}
  page.on('pageerror',error=>seen.errors.push(error.message))
  await page.addInitScript(({user,storage})=>{localStorage.setItem('dachapply_user',JSON.stringify(user));localStorage.setItem('dachapply_tour_done','true');localStorage.setItem('dachapply_onboarding_done','true');for(const[k,v] of Object.entries(storage))if(localStorage.getItem(k)===null)localStorage.setItem(k,v)},{user,storage})
  let job=detail()
  await page.route('**/api/**',async route=>{
    const request=route.request(),path=new URL(request.url()).pathname,method=request.method()
    if(!path.startsWith('/api/'))return route.continue()
    if(method!=='GET'&&path!=='/api/jobs/source-text/refresh-due/')seen.writes.push({method,path,search:new URL(request.url()).search,body:request.postDataJSON()})
    let data=[]
    if(api[path])data=api[path]()
    else if(path==='/api/auth/me/')data=user
    else if(path==='/api/stats/')data=stats()
    else if(path==='/api/mailbox-suggestions/')data=[suggestion(901),suggestion(902)]
    else if(path==='/api/jobs/')data=boardRows
    else if(path==='/api/jobs/application-prep/active/')data={}
    else if(path==='/api/jobs/source-text/refresh-due/')data={remaining:0,staged:0}
    else if(path==='/api/jobs/1/cv-generation/')data=preview(job)
    else if(path==='/api/jobs/1/mailbox/')data={messages:[],notes:[]}
    else if(path==='/api/jobs/1/application-prep/')data=prep
    else if(path==='/api/jobs/1/application-prep/export/')data={text:`TEX ${new URL(request.url()).searchParams.get('key')}`}
    else if(path==='/api/jobs/1/'&&method==='PATCH'){job={...job,...request.postDataJSON()};data=job}
    else if(path==='/api/jobs/1/')data=job
    else if(path==='/api/jobs/clear-skip-recommended/')data={moved:request.postDataJSON().ids}
    await route.fulfill({status:200,json:data})
  })
  await page.goto(url+path)
  return {page,seen,close:()=>context.close()}
}
const noSideScroll=page=>page.evaluate(()=>{const d=document.documentElement;return {scroll:d.scrollWidth,client:d.clientWidth}})
const box=locator=>locator.evaluate(el=>{const r=el.getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,height:r.height,width:r.width}})

before(async()=>{
  for(let attempt=0;;attempt++){
    if(server.exitCode!==null)throw new Error(output)
    try{if((await fetch(url)).ok)break}catch{}
    if(attempt===100)throw new Error(`Vite did not start: ${output}`)
    await new Promise(resolve=>setTimeout(resolve,100))
  }
  browser=await chromium.launch(process.platform==='win32'?{channel:'chrome'}:{})
})
after(async()=>{await browser?.close();server.kill()})

test('the first screen at 1366x768 has jobs, Ready to submit first, and the email decisions',async()=>{
  const {page,seen,close}=await open('/')
  const list=page.getByRole('region',{name:/^Next up/})
  const first=list.getByRole('link').first()
  await first.waitFor()
  assert.match(await first.innerText(),/Ready to submit/)
  const links=await list.getByRole('link').all()
  assert.equal(links.length,6)
  const bottom=await box(links[5])
  assert.ok(bottom.bottom<=768,`last Next up row ends at ${bottom.bottom}`)
  const mail=await box(page.locator('[data-panel="mailbox_review"]'))
  assert.ok(mail.top<768,`Email decisions starts at ${mail.top}`)
  console.log('board 1366x768:',{lastNextUpBottom:bottom.bottom,emailDecisionsTop:mail.top,emailDecisionsBottom:mail.bottom})
  await page.getByRole('button',{name:'Panels',exact:true}).click()
  for(const label of ['Application pace','Conversion funnel','Total'])assert.equal(await page.getByRole('button',{name:new RegExp(`^${label}`)}).count(),1)
  assert.equal(await page.locator('[data-panel="funnel"]').count(),1,'stats panels stay on the board')
  assert.deepEqual(seen.errors,[])
  await close()
})

test('a saved panel choice is kept',async()=>{
  const {page,close}=await open('/',{storage:{dachapply_dashboard_panel_order:JSON.stringify(['funnel','total','mailbox_review']),dachapply_dashboard_panel_hidden:JSON.stringify(['next_up','total','mailbox_unmatched']),dachapply_dashboard_panel_defaults_seeded:JSON.stringify(['mailbox_unmatched'])}})
  await page.locator('[data-panel="funnel"]').waitFor()
  assert.equal(await page.locator('[data-panel="next_up"]').count(),0)
  assert.equal(await page.locator('[data-panel="total"]').count(),0)
  await page.getByRole('button',{name:'Panels',exact:true}).click()
  await page.getByRole('button',{name:/^Next up/}).click()
  await page.locator('[data-panel="next_up"]').waitFor()
  assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('dachapply_dashboard_panel_hidden')).includes('next_up')),false)
  await close()
})

test('clearing lists the jobs and changes nothing until confirmed',async()=>{
  let cleared=false
  const {page,seen,close}=await open('/',{api:{'/api/stats/':()=>({...stats(),skip_recommended_new:cleared?[]:skipRows})}})
  const action=page.getByRole('button',{name:'Clear 28 recommended skip',exact:true})
  await action.click()
  const dialog=page.getByRole('dialog',{name:'Move 28 jobs to Skipped?',exact:true})
  await dialog.waitFor()
  assert.equal(await dialog.getByRole('listitem').count(),28)
  assert.equal((await dialog.getByRole('listitem').first().innerText()),'Skip 0 · Skip role 0')
  assert.deepEqual(seen.writes,[])
  await dialog.getByRole('button',{name:'Cancel',exact:true}).click()
  assert.equal(await dialog.count(),0)
  await action.click();await dialog.waitFor();await page.keyboard.press('Escape')
  assert.equal(await dialog.count(),0)
  assert.deepEqual(seen.writes,[])
  await action.click()
  cleared=true
  await dialog.getByRole('button',{name:'Move 28 to Skipped',exact:true}).click()
  await page.getByText('Moved 28 to Skipped.',{exact:true}).waitFor()
  assert.deepEqual(seen.writes.map(w=>[w.method,w.path]),[['POST','/api/jobs/clear-skip-recommended/']])
  assert.deepEqual(seen.writes[0].body.ids,skipRows.map(r=>r.id))
  await action.waitFor({state:'detached'})
  await close()
})

test('nothing to clear means no action',async()=>{
  const {page,close}=await open('/',{api:{'/api/stats/':()=>({...stats(),skip_recommended_new:[]})}})
  await page.getByRole('region',{name:/^Next up/}).waitFor()
  assert.equal(await page.getByRole('button',{name:/recommended skip/}).count(),0)
  await close()
})

for(const[width,height] of [[1366,768],[360,740]])test(`the job bar stays visible at ${width}px`,async()=>{
  const {page,close}=await open('/jobs/1',{width,height})
  const bar=page.getByRole('region',{name:'Apply actions',exact:true})
  await bar.waitFor()
  await bar.getByRole('button',{name:'Mark applied',exact:true}).waitFor()
  const total=await page.evaluate(()=>document.documentElement.scrollHeight)
  assert.ok(total>2*height,`page is only ${total}px`)
  for(const y of [800,total]){
    await page.evaluate(top=>window.scrollTo({top,behavior:'instant'}),y)
    await page.waitForFunction(()=>true)
    const rect=await box(bar),nav=await box(page.locator('div.app-nav'))
    console.log(`job bar ${width}px scrollY=${y}:`,{navBottom:nav.bottom,barTop:rect.top,barBottom:rect.bottom})
    assert.ok(rect.top>=nav.bottom-1,`bar top ${rect.top} is under the nav bottom ${nav.bottom}`)
    assert.ok(rect.bottom<=height,`bar bottom ${rect.bottom}`)
  }
  const size=await noSideScroll(page)
  assert.ok(size.scroll<=size.client,JSON.stringify(size))
  assert.ok((await box(bar)).height<=(width===360?66:60),'one row')
  if(width===360)for(const name of ['Open posting','Copy TeX','Mark applied']){
    const target=await box(bar.getByText(name,{exact:true}).locator('xpath=ancestor-or-self::*[self::a or self::button]'))
    assert.ok(target.height>=44,`${name} is ${target.height}px tall`)
  }
  await close()
})

test('each bar action works from far down the page',async()=>{
  const {page,seen,close}=await open('/jobs/1')
  const bar=page.getByRole('region',{name:'Apply actions',exact:true})
  await bar.getByRole('button',{name:'Copy TeX',exact:true}).waitFor()
  await page.waitForFunction(()=>!document.querySelector('[aria-label="Apply actions"] button[title="No letter prepared yet"]'))
  await page.evaluate(()=>window.scrollTo({top:900,behavior:'instant'}))
  const [popup]=await Promise.all([page.context().waitForEvent('page'),bar.getByRole('link',{name:/Open the original posting/}).click()])
  await popup.waitForLoadState()
  assert.equal(popup.url(),'https://jobs.example.test/1')
  await popup.close()

  await bar.getByRole('button',{name:'Copy TeX',exact:true}).click()
  await bar.getByRole('button',{name:'Copied',exact:true}).waitFor()
  assert.equal(await page.evaluate(()=>navigator.clipboard.readText()),'TEX letter-b','recommended by default')
  await page.getByRole('combobox',{name:'TeX file to copy'}).selectOption('letter-a')
  await bar.getByText(/^Anschreiben/).waitFor()
  await bar.getByRole('button',{name:'Copy TeX',exact:true}).click({timeout:8000})
  await page.waitForFunction(()=>navigator.clipboard.readText().then(t=>t==='TEX letter-a'))

  await bar.getByRole('button',{name:'Mark applied',exact:true}).click()
  await bar.getByText('Applied',{exact:true}).waitFor()
  const today=new Date().toISOString().slice(0,10)
  const patch=seen.writes.filter(w=>w.path==='/api/jobs/1/')
  assert.equal(patch.length,1)
  assert.deepEqual({status:patch[0].body.status,status_date:patch[0].body.status_date},{status:'applied',status_date:today})
  const status=page.getByRole('combobox',{name:'Status',exact:true})
  assert.equal(await status.inputValue(),'applied','the details form follows, so saving cannot write the old status back')
  assert.equal(await page.getByRole('button',{name:'Discard changes',exact:true}).first().isDisabled(),true,'not flagged as unsaved')
  await page.getByRole('textbox',{name:'Job title',exact:true}).fill('Edited title')
  await Promise.all([page.waitForResponse(r=>new URL(r.url()).pathname==='/api/jobs/1/'&&r.request().method()==='PATCH'),page.getByRole('button',{name:'Save all details',exact:true}).first().click()])
  assert.equal(seen.writes.filter(w=>w.path==='/api/jobs/1/').at(-1).body.status,'applied','saving the form keeps Applied')
  assert.deepEqual(seen.errors,[])
  await close()
})

test('a page at 360px has no sideways scroll, and the dialog fits',async()=>{
  const {page,close}=await open('/',{width:360,height:740})
  const action=page.getByRole('button',{name:'Clear 28 recommended skip',exact:true})
  await action.waitFor()
  await page.getByRole('region',{name:/^Next up/}).waitFor()
  assert.ok((await box(action)).height>=44)
  const link=await box(page.getByRole('region',{name:/^Next up/}).getByRole('link').first())
  assert.ok(link.height>=44,`Next up row is ${link.height}px`)
  const boardSize=await noSideScroll(page)
  await action.click()
  const dialog=await box(page.getByRole('dialog'))
  console.log('360px:',{board:boardSize,dialog})
  assert.ok(dialog.left>=0&&dialog.right<=360&&dialog.bottom<=740)
  assert.ok(boardSize.scroll<=boardSize.client,JSON.stringify(boardSize))
  await close()
  const stats=await open('/stats',{width:360,height:740})
  await stats.page.getByRole('table').waitFor()
  assert.equal(await stats.page.getByRole('rowheader').count(),5)
  const statsSize=await noSideScroll(stats.page)
  console.log('360px stats:',statsSize)
  assert.ok(statsSize.scroll<=statsSize.client,JSON.stringify(statsSize))
  await stats.close()
})

for(const[name,fields,shown,absent] of [
  ['salary only',{posting_missing:['salary'],status:'to_apply'},'Salary not stated in the posting.','Paste the full posting here.'],
  ['ready to submit',{posting_missing:['tasks','salary'],status:'ready_to_submit'},'Salary not stated in the posting.','Paste the full posting here.'],
  ['another part missing',{posting_missing:['tasks','salary'],status:'to_apply'},'Posting incomplete: missing tasks, salary. Paste the full posting here.','Salary not stated in the posting.'],
])test(`job page posting note: ${name}`,async()=>{
  const {page,close}=await open('/jobs/1',{api:{'/api/jobs/1/':()=>({...detail(),...fields})}})
  await page.getByText(shown,{exact:true}).waitFor()
  assert.equal(await page.getByText(absent,{exact:false}).count(),0)
  await close()
})
