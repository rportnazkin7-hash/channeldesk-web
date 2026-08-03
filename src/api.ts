const headers=()=>{const h=new Headers({'Content-Type':'application/json'});const data=window.Telegram?.WebApp?.initData;if(data)h.set('X-Telegram-Init-Data',data);return h}
async function req<T>(path:string,options:RequestInit={}):Promise<T>{
 const ctrl=new AbortController();const timer=setTimeout(()=>ctrl.abort(),12000)
 try{
  const r=await fetch(path,{...options,headers:headers(),signal:ctrl.signal})
  if(!r.ok){let m=`Ошибка ${r.status}`;try{const j=await r.json();m=j.detail||m}catch{}throw new Error(m)}
  return r.json()
 }catch(e){
  if(e instanceof DOMException&&e.name==='AbortError')throw new Error('Сервер не ответил за 12 секунд. Проверьте интернет и обновите экран.')
  if(e instanceof TypeError)throw new Error('Нет соединения с сервером. Проверьте интернет и обновите экран.')
  throw e
 }finally{clearTimeout(timer)}
}
export type Workspace={id:number;name:string;role:string}
export type Pending={id:number;telegram_chat_id:number;title:string;username:string|null;bot_permissions:Record<string,boolean>}
export type Channel={id:number;title:string;username:string|null;is_connected:boolean}
export type Member={id:number;role:string;status:string;channel_scope:number[]|null;telegram_id:number;username:string|null;first_name:string|null;last_name:string|null}
export type Invite={id:number;role:string;max_uses:number|null;expires_at:string|null;token:string}
export type AuditEntry={id:number;action:string;entity_type:string;entity_id:number|null;created_at:string}
export type Post={id:number;title:string;text:string;status:string;scheduled_at:string|null;channel_id:number|null;channel_title:string|null;author_username:string|null;approval_required:boolean;publish_key:string|null;telegram_message_id:number|null;last_error:string|null;buttons:Button[][]|null;created_at:string}
export type Button={text:string;url:string}
export type Comment={id:number;text:string;created_at:string;username:string|null;first_name:string|null;last_name:string|null}
export type Version={id:number;title:string;text:string;created_by:number|null;created_at:string}
export type Template={id:number;name:string;title:string;text:string}
export type Asset={id:number;file_name:string;file_type:string;file_url:string;size_bytes:number|null}
export type UploadTicket={asset_id:number;file_url:string;upload_url:string;anon_key:string;bucket:string}
async function uploadDirect(ticket:UploadTicket,file:File):Promise<void>{
 const ctrl=new AbortController();const timer=setTimeout(()=>ctrl.abort(),90000)
 try{
  const r=await fetch(ticket.upload_url,{method:'POST',body:file,headers:{'Content-Type':file.type||'application/octet-stream','Authorization':`Bearer ${ticket.anon_key}`,'apikey':ticket.anon_key},signal:ctrl.signal})
  if(!r.ok){let m=`Ошибка ${r.status}`;try{const j=await r.json();m=j.message||j.error||m}catch{}throw new Error(`Загрузка файла в хранилище: ${m}`)}
 }catch(e){
  if(e instanceof DOMException&&e.name==='AbortError')throw new Error('Загрузка файла не завершилась за 90 секунд')
  if(e instanceof TypeError)throw new Error('Хранилище не отвечает. Проверьте CORS в Supabase: Project Settings → API → Allowed Origins → добавьте https://channeldesk.vercel.app (или *)')
  throw e
 }finally{clearTimeout(timer)}
}
export const api={
 workspaces:()=>req<Workspace[]>('/api/workspaces'),
 createWorkspace:(name:string)=>req<Workspace>('/api/workspaces',{method:'POST',body:JSON.stringify({name})}),
 pending:()=>req<Pending[]>('/api/channel-connections/pending'),
 channels:(wid:number)=>req<Channel[]>(`/api/workspaces/${wid}/channels`),
 connect:(wid:number,id:number)=>req<Channel>(`/api/workspaces/${wid}/channels/connect`,{method:'POST',body:JSON.stringify({connection_id:id})}),
 members:(wid:number)=>req<Member[]>(`/api/workspaces/${wid}/members`),
 createInvite:(wid:number,role='viewer')=>req<Invite>(`/api/workspaces/${wid}/invites`,{method:'POST',body:JSON.stringify({role})}),
 acceptInvite:(token:string)=>req<{workspace_id:number;workspace_name:string;role:string}>(`/api/invites/accept`,{method:'POST',body:JSON.stringify({token})}),
 audit:(wid:number)=>req<AuditEntry[]>(`/api/workspaces/${wid}/audit`),
 posts:(wid:number)=>req<Post[]>(`/api/workspaces/${wid}/posts`),
 createPost:(wid:number,p:{title:string;text:string;channel_id:number|null;buttons?:Button[][]})=>req<Post>(`/api/workspaces/${wid}/posts`,{method:'POST',body:JSON.stringify(p)}),
 updatePost:(wid:number,id:number,p:{title?:string;text?:string;channel_id?:number|null;buttons?:Button[][]})=>req<Post>(`/api/workspaces/${wid}/posts/${id}`,{method:'PATCH',body:JSON.stringify(p)}),
 submitPost:(wid:number,id:number)=>req<Post>(`/api/workspaces/${wid}/posts/${id}/submit`,{method:'POST'}),
 approvePost:(wid:number,id:number)=>req<Post>(`/api/workspaces/${wid}/posts/${id}/approve`,{method:'POST'}),
 requestChanges:(wid:number,id:number)=>req<Post>(`/api/workspaces/${wid}/posts/${id}/request-changes`,{method:'POST'}),
 schedulePost:(wid:number,id:number,at:string)=>req<Post>(`/api/workspaces/${wid}/posts/${id}/schedule`,{method:'POST',body:JSON.stringify({scheduled_at:at})}),
 publishNow:(wid:number,id:number)=>req<Post>(`/api/workspaces/${wid}/posts/${id}/publish-now`,{method:'POST'}),
 cancelPost:(wid:number,id:number)=>req<Post>(`/api/workspaces/${wid}/posts/${id}/cancel`,{method:'POST'}),
 comments:(wid:number,id:number)=>req<Comment[]>(`/api/workspaces/${wid}/posts/${id}/comments`),
 addComment:(wid:number,id:number,text:string)=>req<Comment>(`/api/workspaces/${wid}/posts/${id}/comments`,{method:'POST',body:JSON.stringify({text})}),
 versions:(wid:number,id:number)=>req<Version[]>(`/api/workspaces/${wid}/posts/${id}/versions`),
 templates:(wid:number)=>req<Template[]>(`/api/workspaces/${wid}/templates`),
 createTemplate:(wid:number,p:{name:string;title:string;text:string})=>req<Template>(`/api/workspaces/${wid}/templates`,{method:'POST',body:JSON.stringify(p)}),
 deleteTemplate:(wid:number,id:number)=>req<void>(`/api/workspaces/${wid}/templates/${id}`,{method:'DELETE'}),
 assets:(wid:number,postId?:number)=>req<Asset[]>(`/api/workspaces/${wid}/assets${postId!=null?`?post_id=${postId}`:''}`),
 uploadTicket:(wid:number,p:{post_id:number;file_name:string;content_type:string;size:number})=>req<UploadTicket>(`/api/workspaces/${wid}/assets/upload-url`,{method:'POST',body:JSON.stringify(p)}),
 uploadDirect,
 deleteAsset:(id:number)=>req<void>(`/api/assets/${id}`,{method:'DELETE'}),
}
