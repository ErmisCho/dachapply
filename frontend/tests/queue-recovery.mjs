// TASK-366: real browser + Django recovery smoke; all output lives in the system temp directory.
import assert from 'node:assert/strict'
import {spawn,execFileSync} from 'node:child_process'
import {mkdtemp,writeFile,rm} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import path from 'node:path'
import {fileURLToPath} from 'node:url'
import {createInterface} from 'node:readline'
import {test} from 'node:test'

const frontend=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const backend=path.resolve(frontend,'../backend')
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms))
test('cloud retry and usage-limit recovery through real routes',{timeout:120000},async()=>{
  const temp=await mkdtemp(path.join(tmpdir(),'dachapply-recovery-'))
  const servers=[];let browser,page,log='',passed=false,django
  const origin='http://127.0.0.1:4396'
  function start(exe,args,cwd){
    const child=spawn(exe,args,{cwd,detached:process.platform!=='win32',stdio:['pipe','pipe','pipe'],env:{...process.env,NO_COLOR:'1',FORCE_COLOR:'0',PYTHONDONTWRITEBYTECODE:'1',DATABASE_URL:'',UV_CACHE_DIR:path.join(temp,'uv-cache')}})
    servers.push(child)
    child.stdout.on('data',data=>{log+=data});child.stderr.on('data',data=>{log+=data})
    child.on('error',error=>{log+=error.stack})
    child.stdin.on('error',error=>{log+=error.message})
    return child
  }
  async function until(fn,label='recovery state'){for(let i=0;i<200;i++){if(await fn())return;await sleep(100)}throw Error('Timed out waiting for '+label)}
  try{
    const {chromium}=await import('playwright')
    const python=execFileSync('uv',['run','--no-sync','python','-c','import sys; print(sys.executable)'],{cwd:backend,encoding:'utf8',timeout:15000,env:{...process.env,PYTHONDONTWRITEBYTECODE:'1',UV_CACHE_DIR:path.join(temp,'uv-cache')}}).trim()
    django=start(python,[path.join(frontend,'tests/queue-recovery-backend.py'),temp,'8396',origin],backend)
    const messages=[]
    createInterface({input:django.stdout}).on('line',line=>{try{messages.push(JSON.parse(line))}catch{}})
    const command=command=>django.stdin.write(JSON.stringify({command})+'\n')
    await until(()=>messages.some(m=>m.ready)||django.exitCode!==null,'backend ready')
    assert.equal(django.exitCode,null,log)
    const {jobs}=messages.find(m=>m.ready)
    const config=path.join(temp,'vite.config.mjs')
    await writeFile(config,`import react from ${JSON.stringify(import.meta.resolve('@vitejs/plugin-react'))};export default {plugins:[react()],root:${JSON.stringify(frontend)},cacheDir:${JSON.stringify(path.join(temp,'vite-cache'))},server:{host:'127.0.0.1',port:4396,strictPort:true,proxy:{'/api':'http://127.0.0.1:8396'}}}`)
    const vite=start(process.execPath,[path.join(frontend,'node_modules/vite/bin/vite.js'),'--config',config,'--configLoader','native'],frontend)
    await until(()=>log.includes(origin)||vite.exitCode!==null,'vite log')
    assert.equal(vite.exitCode,null,log)  // TASK-366: never use an unrelated frontend already occupying this port.
    await until(async()=>{try{return (await fetch(origin)).ok}catch{return false}},'vite fetch')
    browser=await chromium.launch(process.platform==='win32'?{channel:'chrome'}:{})
    const context=await browser.newContext({viewport:{width:1440,height:1000}})
    page=await context.newPage();page.setDefaultTimeout(15000)
    const errors=[];page.on('pageerror',error=>errors.push(error.message))
    await context.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort())
    const csrf=await context.request.get(origin+'/api/auth/csrf/');assert.equal(csrf.status(),200)
    const token=(await context.cookies()).find(c=>c.name==='csrftoken').value
    const login=await context.request.post(origin+'/api/auth/login/',{data:{username:'recovery-test',password:'fixture-password'},headers:{'X-CSRFToken':token,Origin:origin}})
    assert.equal(login.status(),200,await login.text())
    const user=await (await context.request.get(origin+'/api/auth/me/')).json()
    await page.addInitScript(user=>{localStorage.setItem('dachapply_user',JSON.stringify(user));localStorage.setItem('dachapply_tour_done','true')},user)
    await page.goto(origin+'/settings/profile')
    const limit=page.locator('#analysis-time-limit')
    await limit.fill('2')
    await page.getByRole('button',{name:'Save profile',exact:true}).click()
    await until(async()=> (await (await context.request.get(origin+'/api/profile/')).json()).analysis_time_limit_minutes===2,'profile saved')
    await page.reload();assert.equal(await limit.inputValue(),'2')
    assert.equal(await page.getByRole('checkbox',{name:'Use cloud models only',exact:true}).isChecked(),false)
    command('analysis')
    await page.goto(origin+'/queue')
    await page.getByText('Finding models',{exact:true}).waitFor()
    await page.getByText(/\d+:\d{2} so far/).waitFor()
    await page.getByRole('button',{name:'Use cloud models only this time',exact:true}).click()
    await page.getByRole('region',{name:'Done',exact:true}).getByText('Cloud fixture — Engineer').waitFor()
    assert.equal((await (await context.request.get(origin+'/api/profile/')).json()).use_cloud_models_only,false)
    command('release')
    await page.goto(origin)
    await page.getByRole('checkbox',{name:/^Select Limit fixture/}).check()
    await page.getByRole('button',{name:'Generate CV and Motivation Letter',exact:true}).click()
    const dialog=page.getByRole('dialog',{name:'Generate CV and Motivation Letter',exact:true})
    await dialog.getByRole('checkbox',{name:'Create letter',exact:true}).uncheck()
    const tasks=[]
    page.on('response',async response=>{if(/\/api\/cv-generation\/tasks\/[^/]+\/$/.test(new URL(response.url()).pathname)){try{tasks.push(await response.json())}catch{}}})
    await dialog.getByRole('button',{name:/^Generate/}).click()
    const line=page.getByText(/^Codex limit reached\. Continues automatically at \d{2}:\d{2}\.$/).first()
    await line.waitFor()
    const visible=await dialog.innerText()
    assert.doesNotMatch(visible,/PRIVATE PROMPT|example.invalid|provider banner/)
    await until(()=>tasks.some(task=>task.status==='running'),'running task')
    const running=tasks.find(task=>task.status==='running')
    assert.ok(tasks.filter(task=>['scheduled','running'].includes(task.status)).every(task=>task.id===running.id))
    assert.ok(tasks.some(task=>task.status==='scheduled'&&task.id===running.id))
    await dialog.getByRole('button',{name:'Cancel generation',exact:true}).click()
    await until(()=>tasks.some(task=>task.status==='cancelled'),'cancelled task')
    command('evidence');await until(()=>messages.some(m=>m.calls!==undefined),'evidence msg')
    assert.deepEqual(messages.find(m=>m.calls!==undefined),{calls:2,identical:true})
    assert.deepEqual(errors,[])
    passed=true
  }catch(error){
    if(page)await page.screenshot({path:path.join(temp,'failure.png')}).catch(()=>{})
    await writeFile(path.join(temp,'failure.txt'),`${error.stack}\n${log.slice(-16000)}`)
    console.error(`TASK-366 diagnostics: ${temp}`)
    throw error
  }finally{
    const cleanupErrors=[]
    await browser?.close().catch(()=>{})
    for(const child of servers.reverse()){
      if(child.exitCode!==null){if(child===django&&child.exitCode!==0)cleanupErrors.push(`Backend exited ${child.exitCode}`);continue}
      try{
        child.stdin.write('{"command":"stop"}\n')
        for(let i=0;i<50&&child.exitCode===null;i++)await sleep(100)
        if(child.exitCode===null){
          if(process.platform==='win32')execFileSync('taskkill',['/PID',String(child.pid),'/T','/F'],{stdio:'pipe',timeout:10000})
          else process.kill(-child.pid,'SIGKILL')
        }
        await until(()=>child.exitCode!==null||child.signalCode!==null)
        if(child===django)assert.equal(child.exitCode,0,'Backend fixture did not shut down cleanly')
      }catch(error){cleanupErrors.push(`Cleanup PID ${child.pid}: ${error.message}`);passed=false}
    }
    if(passed)await rm(temp,{recursive:true,force:true})
    if(cleanupErrors.length){
      await writeFile(path.join(temp,'failure.txt'),`${cleanupErrors.join('\n')}\n${log.slice(-16000)}`)
      console.error(`TASK-366 diagnostics: ${temp}`)
    }
    assert.deepEqual(cleanupErrors,[])  // TASK-366: cleanup failures fail the check too.
  }
})
