const API='/api';
function getCookie(name:string){return document.cookie.split('; ').find(r=>r.startsWith(name+'='))?.split('=')[1]}
export async function api(path:string, options:any={}){const headers:any={'Content-Type':'application/json',...(options.headers||{})}; const csrf=getCookie('csrftoken'); if(csrf) headers['X-CSRFToken']=csrf; const res=await fetch(API+path,{credentials:'include',...options,headers,body:options.body&&typeof options.body!=='string'?JSON.stringify(options.body):options.body}); if(!res.ok){let e; try{e=await res.json()}catch{e={detail:await res.text()}} throw e} const ct=res.headers.get('content-type')||''; return ct.includes('json')?res.json():res.text()}
export const fileUrl=(path:string)=>API+path;
