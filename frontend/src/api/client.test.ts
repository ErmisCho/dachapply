import {afterEach,beforeEach,describe,expect,it} from 'vitest'
import {api,authMe,cachedAuthUser,clearAuthCache} from './client'

// RequireAuth wraps every protected route, so /auth/me/ is cached for the session. The cache
// surviving a logout or a dead session would be a security bug, not a performance win.
const originalFetch=Object.getOwnPropertyDescriptor(globalThis,'fetch')
const originalDocument=Object.getOwnPropertyDescriptor(globalThis,'document')
let calls:string[]=[]
let status=200
function res(){return {ok:status<400,status,headers:{get:()=>'application/json'},json:async()=>({username:'me'}),text:async()=>JSON.stringify({detail:'nope'})}}

beforeEach(()=>{
  calls=[];status=200;clearAuthCache()
  Object.defineProperty(globalThis,'document',{value:{cookie:''},configurable:true,writable:true})
  Object.defineProperty(globalThis,'fetch',{value:async(url:string)=>{calls.push(String(url));return res()},configurable:true,writable:true})
})
afterEach(()=>{
  clearAuthCache()
  originalFetch?Object.defineProperty(globalThis,'fetch',originalFetch):delete (globalThis as any).fetch
  originalDocument?Object.defineProperty(globalThis,'document',originalDocument):delete (globalThis as any).document
})

describe('session auth check cache',()=>{
  it('hits /auth/me/ once no matter how many routes ask',async()=>{
    expect(await authMe()).toEqual({username:'me'})
    await authMe();await authMe()
    expect(calls).toEqual(['/api/auth/me/'])
    expect(cachedAuthUser()).toEqual({username:'me'})
  })

  it('drops the cache on logout so the next route re-checks',async()=>{
    await authMe()
    clearAuthCache()
    expect(cachedAuthUser()).toBe(null)
    await authMe()
    expect(calls).toEqual(['/api/auth/me/','/api/auth/me/'])
  })

  it('drops the cache when any other endpoint answers 401',async()=>{
    await authMe()
    status=401
    await expect(api('/jobs/')).rejects.toBeTruthy()
    expect(cachedAuthUser()).toBe(null)
    status=200
    await authMe()
    expect(calls.filter(u=>u.endsWith('/auth/me/'))).toHaveLength(2)
  })

  it('does not cache a failed check',async()=>{
    status=401
    await expect(authMe()).rejects.toBeTruthy()
    expect(cachedAuthUser()).toBe(null)
    status=200
    expect(await authMe()).toEqual({username:'me'})
  })
})
