// TASK-307: the CV popup's only request on open is GET /jobs/<id>/cv-generation/. It is prefetched (job page
// load, hover/focus of the board button) so opening renders filled; writes drop the cache so a generation
// can never leave stale files behind. No DOM here (TASK-177), so the popup is read as emitted markup.
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {CvGenerator} from './App'
import {api,cachedCvGeneration,clearAuthCache,fetchCvGeneration,prefetchCvGeneration} from './api/client'
import appSource from './App.tsx?raw'
import type {Job} from './types'

vi.stubGlobal('localStorage',{getItem:vi.fn(()=>JSON.stringify({can_generate_cv:true})),setItem:vi.fn(),removeItem:vi.fn()})

const originalFetch=Object.getOwnPropertyDescriptor(globalThis,'fetch')
const originalDocument=Object.getOwnPropertyDescriptor(globalThis,'document')
let calls:string[]=[]
let files=['old.pdf']
const preview=()=>({cvs:[{key:'en',label:'English CV',language:'en',path:'/w/cv.tex'}],letters:[{key:'l',label:'English letter',language:'en',path:'/w/l.tex'}],selected_cv:'en',selected_letter:'l',models:[],default_pick:null,configured:true,workspace:'/w',generated_files:files.map(name=>({name})),job:{company:'Acme',source_text:'Posting text',pending_source_text:''}})

beforeEach(()=>{
  calls=[];files=['old.pdf'];clearAuthCache()
  Object.defineProperty(globalThis,'document',{value:{cookie:''},configurable:true,writable:true})
  Object.defineProperty(globalThis,'fetch',{value:async(url:string,init:any)=>{calls.push(`${init?.method||'GET'} ${url}`);return {ok:true,status:200,headers:{get:()=>'application/json'},json:async()=>preview()}},configurable:true,writable:true})
})
afterEach(()=>{
  clearAuthCache()
  originalFetch?Object.defineProperty(globalThis,'fetch',originalFetch):delete (globalThis as any).fetch
  originalDocument?Object.defineProperty(globalThis,'document',originalDocument):delete (globalThis as any).document
})

const popup=()=>renderToStaticMarkup(<CvGenerator compact job={{id:216} as Job} onClose={()=>{}}/>)
const settle=()=>new Promise(resolve=>setTimeout(resolve,0))

describe('CV popup prefetch (TASK-307)',()=>{
  it('opens filled, without the loading text, once prefetched',async()=>{
    expect(popup()).toContain('Loading generator options…')   // control: nothing cached yet
    prefetchCvGeneration(216);prefetchCvGeneration(216)        // hover then focus: one request
    await settle()
    expect(calls).toEqual(['GET /api/jobs/216/cv-generation/'])
    const html=popup()
    expect(html).not.toContain('Loading generator options…')
    expect(html).toContain('English CV')
    expect(html).toContain('Create letter')
  })

  it('drops the cache on any write, so a generation never paints stale files',async()=>{
    prefetchCvGeneration(216);await settle()
    const early=fetchCvGeneration(216)               // a refresh in flight when the generation starts...
    await api('/jobs/216/cv-generation/run/',{method:'POST',body:{}})
    await early
    expect(cachedCvGeneration(216)).toBeUndefined()  // ...is not stored over the cleared entry
    expect(popup()).toContain('Loading generator options…')
    files=['new.pdf']
    await fetchCvGeneration(216)                     // what the popup runs when the task is ready
    expect(cachedCvGeneration(216).generated_files).toEqual([{name:'new.pdf'}])
  })

  it('is wired to the job page load, the board button, and task completion',()=>{
    expect(appSource).toContain("if(storedUser()?.can_generate_cv)prefetchCvGeneration(Number(id));")
    expect(appSource).toContain('onPointerEnter={()=>prefetchCvGeneration(selected[0])} onFocus={()=>prefetchCvGeneration(selected[0])}')
    expect(appSource).toContain("if(current.status==='ready'){fetchCvGeneration(job.id)")
  })
})
