import assert from 'node:assert/strict'
import {spawn} from 'node:child_process'
import {once} from 'node:events'
import {test} from 'node:test'
import {chromium} from 'playwright'

// Real board and generator components; only the API boundary uses synthetic data.
// Run: npm run test:board (install Chromium with npx playwright install chromium).
const server=spawn(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','4387','--strictPort'],{stdio:'pipe'})
let output=''
server.stdout.on('data',data=>{output+=data})
server.stderr.on('data',data=>{output+=data})
const url='http://127.0.0.1:4387'
const jobs=[1,2].map(id=>({id,company:`Fixture ${id}`,title:`Engineer ${id}`,status:'reviewed',location:'Vienna',work_mode:'remote',url:'',fit_score:80,skill_matches:[],missing_skills:[],created_at:'2026-11-01T12:00:00Z'}))
const user={username:'board-test',can_generate_cv:true,is_staff:true}
const preview=job=>({configured:true,job:{...job,source_text:'Synthetic job description',pending_source_text:''},cvs:[{key:'english',label:'English'},{key:'german',label:'German'}],letters:[],models:[{provider:'openai',key:'fixture',label:'Fixture',efforts:['low'],default_effort:'low'}],selected_cv:'english',selected_letter:'',default_pick:{provider:'openai',model:'fixture',effort:'low',speed:'normal'}})

test('applied jobs leave the real board selection and generators',{timeout:60000},async t=>{
  let browser
  try{
    for(let attempt=0;;attempt++){
      if(server.exitCode!==null)throw new Error(output)
      try{if((await fetch(url)).ok)break}catch{}
      if(attempt===100)throw new Error(`Vite did not start: ${output}`)
      await new Promise(resolve=>setTimeout(resolve,100))
    }
    browser=await chromium.launch(process.platform==='win32'?{channel:'chrome'}:{})
    for(const count of [1,2])await t.test(`${count} selected job(s)`,async()=>{
      const context=await browser.newContext({viewport:{width:1440,height:1000}})
      const page=await context.newPage()
      page.setDefaultTimeout(5000)
      const errors=[]
      page.on('pageerror',error=>errors.push(error.message))
      const patches=[]
      const previews=[]
      let rejectPatch=true
      await page.addInitScript(user=>{localStorage.setItem('dachapply_user',JSON.stringify(user));localStorage.setItem('dachapply_tour_done','true')},user)
      await page.route('**/api/**',async route=>{
        const path=new URL(route.request().url()).pathname
        if(!path.startsWith('/api/'))return route.continue()
        let data=[]
        let status=200
        if(path==='/api/auth/me/')data=user
        else if(path==='/api/jobs/')data=jobs
        else if(path==='/api/stats/')data={}
        else if(path==='/api/jobs/application-prep/active/')data={}
        else if(path==='/api/jobs/source-text/refresh-due/')data={remaining:0,staged:0}
        else if(/^\/api\/jobs\/\d+\/cv-generation\/$/.test(path)){
          const id=Number(path.split('/')[3]);previews.push(id);data=preview(jobs.find(job=>job.id===id))
        }else if(/^\/api\/jobs\/\d+\/$/.test(path)&&route.request().method()==='PATCH'){
          const id=Number(path.split('/')[3]);const body=route.request().postDataJSON()
          if(rejectPatch){status=500;data={detail:'Synthetic save failure'}}
          else{patches.push(id);data={...jobs.find(job=>job.id===id),...body}}
        }
        await route.fulfill({status,json:data})
      })
      try{
        await page.goto(url)
        const checkbox=id=>page.getByRole('checkbox',{name:new RegExp(`^Select Fixture ${id}`)})
        await checkbox(1).check()
        if(count===2)await checkbox(2).check()
        await page.getByRole('button',{name:count===1?'Generate CV and Motivation Letter':'Generate CV and Letters',exact:true}).click()
        const apply=page.getByRole('button',{name:count===1?'Mark applied':'Mark as applied',exact:true})
        await apply.first().waitFor()
        // Failed saves must leave both the popup and selection intact.
        await apply.first().click()
        await page.getByText('Synthetic save failure',{exact:false}).waitFor()
        assert.equal(await checkbox(1).isChecked(),true)
        assert.equal(await apply.count(),count)
        rejectPatch=false
        if(count===2)await page.getByRole('combobox',{name:/^Language/}).nth(1).selectOption('german')
        const previewCount=previews.length
        await apply.first().click()
        await page.waitForFunction(()=>!document.querySelector('input[aria-label^="Select Fixture 1"]').checked)
        assert.equal(await checkbox(1).isChecked(),false)
        assert.deepEqual(patches,[1])
        if(count===2){
          assert.equal(await checkbox(2).isChecked(),true)
          assert.equal(await apply.count(),1)
          assert.equal(await page.getByRole('link',{name:'Engineer 1',exact:true}).count(),0,'applied row leaves the popup')
          assert.equal(await page.getByRole('combobox',{name:/^Language/}).inputValue(),'german','remaining row keeps its choices')
          assert.equal(previews.length,previewCount,'removing a row must not reload remaining previews')
          await apply.click()
          await page.waitForFunction(()=>!document.querySelector('input[aria-label^="Select Fixture 2"]').checked)
          assert.deepEqual(patches,[1,2])
        }
        await apply.waitFor({state:'hidden'})
        assert.equal(await page.getByRole('button',{name:'Close',exact:true}).count(),0)
        // Opening a fresh batch after the final removal must require a new click.
        await checkbox(1).check()
        assert.equal(await apply.count(),0)
        assert.deepEqual(errors,[])
      }catch(error){console.error({errors,body:(await page.locator('body').innerText()).slice(0,5000)});throw error}finally{await context.close()}
    })
  }finally{
    await browser?.close()
    server.kill()
    if(server.exitCode===null)await once(server,'exit')
  }
})
