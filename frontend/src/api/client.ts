const API='/api';
function getCookie(name:string){return document.cookie.split('; ').find(r=>r.startsWith(name+'='))?.split('=')[1]}
export async function api(path:string, options:any={}){if(options.method&&options.method!=='GET'){cvPreviews.clear();cvFetches.clear()} const headers:any={'Content-Type':'application/json',...(options.headers||{})}; const csrf=getCookie('csrftoken'); if(csrf) headers['X-CSRFToken']=csrf; const res=await fetch(API+path,{credentials:'include',...options,headers,body:options.body&&typeof options.body!=='string'?JSON.stringify(options.body):options.body}); const ct=res.headers.get('content-type')||''; if(!res.ok){if(res.status===401)clearAuthCache();const text=await res.text();let e:any;try{e=text?JSON.parse(text):{detail:res.statusText}}catch{e={detail:ct.includes('html')?'The server encountered an error. Please try again.':text||res.statusText}}throw e} return ct.includes('json')?res.json():res.text()}
export async function downloadApi(path:string,body:any){const headers:any={'Content-Type':'application/json'};const csrf=getCookie('csrftoken');if(csrf)headers['X-CSRFToken']=csrf;const res=await fetch(API+path,{method:'POST',credentials:'include',headers,body:JSON.stringify(body)});if(!res.ok){if(res.status===401)clearAuthCache();const text=await res.text();try{throw JSON.parse(text)}catch(e:any){if(e?.detail)throw e;throw {detail:text||res.statusText}}}const blob=await res.blob();const disposition=res.headers.get('content-disposition')||'';const filename=disposition.match(/filename="?([^";]+)"?/i)?.[1]||'application.zip';const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=filename;a.click();URL.revokeObjectURL(url)}
export const fileUrl=(path:string)=>API+path;
// RequireAuth wraps every protected route, so /auth/me/ used to re-run on every internal
// navigation and blank the page until it resolved. Fetch it once per page load instead.
// The cache MUST NOT outlive the session: it is cleared on logout, account deletion, login,
// and on any 401 from any endpoint (above), so a dead session cannot keep rendering routes.
let authUser:any=null,authCheck:Promise<any>|null=null;
export const cachedAuthUser=()=>authUser;
export function clearAuthCache(){authUser=null;authCheck=null;boardRows=null;cvPreviews.clear();cvFetches.clear()}
// TASK-307: GET /jobs/<id>/cv-generation/ per job (templates, model options, latest files), prefetched on the job
// page and on hover/focus of the board's Generate button so the CV popup opens filled. The popup still refetches on
// open and replaces the data. Any write (generation, revise, recompile, rename, job edits) drops every entry, and a
// fetch started before that write is not stored. ponytail: coarse clear-all, per-job keys if writes get frequent.
const cvPreviews=new Map<number,any>(),cvFetches=new Map<number,Promise<any>>();
export const cachedCvGeneration=(jobId:number)=>cvPreviews.get(jobId);
export function fetchCvGeneration(jobId:number):Promise<any>{const inflight=cvFetches.get(jobId);if(inflight)return inflight;const p:Promise<any>=api(`/jobs/${jobId}/cv-generation/`).then(r=>{if(cvFetches.get(jobId)===p)cvPreviews.set(jobId,r);return r}).finally(()=>{if(cvFetches.get(jobId)===p)cvFetches.delete(jobId)});cvFetches.set(jobId,p);return p}
export function prefetchCvGeneration(jobId:number){if(!cvPreviews.has(jobId))fetchCvGeneration(jobId).catch(()=>{})}
// TASK-283: last board rows, so returning to the board paints instantly while /jobs/?board=1 revalidates.
// Keyed by username + query and dropped by clearAuthCache (logout, login, account deletion, any 401),
// so one account's rows can never be painted for another. In-memory only; one entry.
let boardRows:{key:string;rows:any[]}|null=null;
export const boardCacheKey=(username:any,query:string)=>JSON.stringify([String(username||''),query]);
export const cachedBoardRows=(key:string)=>boardRows?.key===key?boardRows.rows:undefined;
export function cacheBoardRows(key:string,rows:any[]){boardRows={key,rows}}
export function authMe(){return authCheck||(authCheck=api('/auth/me/').then(u=>{authUser=u;return u},e=>{clearAuthCache();throw e}))}
