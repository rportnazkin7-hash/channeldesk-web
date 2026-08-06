const headers=()=>{const h=new Headers({'Content-Type':'application/json'});const data=window.Telegram?.WebApp?.initData;if(data)h.set('X-Telegram-Init-Data',data);return h}
async function req<T>(path:string,options:RequestInit={}):Promise<T>{
 const ctrl=new AbortController();const timer=setTimeout(()=>ctrl.abort(),12000)
 try{
  const r=await fetch(path,{...options,headers:headers(),signal:ctrl.signal})
  if(!r.ok){let m=`Ошибка ${r.status}`;try{const j=await r.json();m=j.detail||m}catch{}throw new Error(m)}
  if(r.status===204)return undefined as T
  return r.json()
 }catch(e){
  if(e instanceof DOMException&&e.name==='AbortError')throw new Error('Сервер не ответил за 12 секунд. Проверьте интернет и обновите экран.')
  if(e instanceof TypeError)throw new Error('Нет соединения с сервером. Проверьте интернет и обновите экран.')
  throw e
 }finally{clearTimeout(timer)}
}
export type Workspace={id:number;name:string;role:string;settings?:{overdue_cancel_days?:number}}
export type Pending={id:number;telegram_chat_id:number;title:string;username:string|null;bot_permissions:Record<string,boolean>}
export type Channel={id:number;title:string;username:string|null;is_connected:boolean}
export type Member={id:number;role:string;status:string;channel_scope:number[]|null;telegram_id:number;username:string|null;first_name:string|null;last_name:string|null}
export type Invite={id:number;role:string;max_uses:number|null;expires_at:string|null;token:string}
export type ApiKey={id:number;name:string;key_prefix:string;scopes:string[];expires_at:string|null;last_used_at:string|null;revoked_at:string|null;created_at:string}
export type Webhook={id:number;name:string;url:string;events:string[];is_active:boolean;last_delivered_at:string|null;last_error:string|null;created_at:string}
export type AuditEntry={id:number;action:string;entity_type:string;entity_id:number|null;created_at:string}
export type Post={id:number;title:string;text:string;status:string;scheduled_at:string|null;channel_id:number|null;channel_title:string|null;author_username:string|null;approval_required:boolean;publish_key:string|null;telegram_message_id:number|null;last_error:string|null;buttons:Button[][]|null;created_at:string}
export type Button={text:string;url:string}
export type Comment={id:number;text:string;created_at:string;username:string|null;first_name:string|null;last_name:string|null}
export type Version={id:number;title:string;text:string;created_by:number|null;created_at:string}
export type Template={id:number;name:string;title:string;text:string}
export type Asset={id:number;file_name:string;file_type:string;file_url:string;size_bytes:number|null}
export type Advertiser={id:number;name:string;contact:Record<string,string>|null;notes:string;is_active:boolean}
export type PublicFeedbackItem={id:number;booking_id:number;post_id:number|null;decision:'approved'|'changes_requested';comment:string;created_at:string;advertiser_name:string;format:string;publish_at:string|null;channel_title:string|null;post_title:string|null}
export type Booking={id:number;advertiser_id:number;channel_id:number|null;post_id:number|null;format:string;cost:number;currency:string;status:string;payment_status:string;publish_at:string|null;delete_at:string|null;erid:string|null;erid_required:boolean;materials_url:string|null;report_url:string|null;advertiser_name:string|null;channel_title:string|null}
export type FinanceTx={id:number;booking_id:number|null;type:'income'|'expense';amount:number;currency:string;category:string;description:string;occurred_at:string;advertiser_name?:string|null;channel_title?:string|null}
export type FinanceTrend={year:number;month:number;income:number;expense:number;profit:number}
export type FinanceSummary={year:number;month:number;income:number;expense:number;profit:number;count:number;trend:FinanceTrend[]}
export type ChannelMetric={id:number;workspace_id:number;channel_id:number;channel_title?:string;metric_date:string;subscribers:number;views:number;reach:number;reactions:number;forwards:number;posts_count:number;source:'bot_api';notes:string}
export type AnalyticsSeries={date:string;subscribers:number;reactions:number;posts_count:number}
export type TrackingLink={id:number;name:string;target_url:string;clicks:number;notes?:string;channel_id:number;channel_title?:string;booking_id:number|null;advertiser_name?:string|null}
export type AnalyticsSummary={subscribers:number;reactions:number;posts_count:number;channels:number;clicks:number;links:number;available:string[];unavailable:string[];series:AnalyticsSeries[]}
export type AnalyticsOverview={from_date:string;to_date:string;metrics:ChannelMetric[];links:TrackingLink[];summary:AnalyticsSummary;data_source:'telegram_bot_api'}
export type MediaKit={id:number;name:string;channel_id:number|null;channel_title:string|null;description:string;audience:Record<string,unknown>;stats:Record<string,unknown>;pricing:unknown[];contacts:Record<string,unknown>;is_active:boolean}
export type Task={id:number;title:string;description:string;status:'todo'|'in_progress'|'done'|'cancelled';priority:'low'|'normal'|'high'|'urgent';assignee_id:number|null;due_at:string|null;remind_at:string|null;assignee_username:string|null;assignee_first_name:string|null}
export type PublicNewsPage={title:string;description:string;channel_title:string|null;channel_id:number|null}
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
  deleteWorkspace:(id:number)=>req<void>(`/api/workspaces/${id}`,{method:'DELETE'}),
  workspaceSettings:(wid:number)=>req<{overdue_cancel_days:number}>(`/api/workspaces/${wid}/settings`),
  updateWorkspaceSettings:(wid:number,p:{overdue_cancel_days:number})=>req<{overdue_cancel_days:number}>(`/api/workspaces/${wid}/settings`,{method:'PATCH',body:JSON.stringify(p)}),
  apiKeys:(wid:number)=>req<ApiKey[]>(`/api/workspaces/${wid}/api-keys`),
  createApiKey:(wid:number,p:{name:string;scopes:string[]})=>req<ApiKey & {token:string}>(`/api/workspaces/${wid}/api-keys`,{method:'POST',body:JSON.stringify(p)}),
  revokeApiKey:(wid:number,id:number)=>req<void>(`/api/workspaces/${wid}/api-keys/${id}`,{method:'DELETE'}),
  webhooks:(wid:number)=>req<Webhook[]>(`/api/workspaces/${wid}/webhooks`),
  createWebhook:(wid:number,p:{name:string;url:string;events:string[]})=>req<Webhook & {secret:string}>(`/api/workspaces/${wid}/webhooks`,{method:'POST',body:JSON.stringify(p)}),
  deleteWebhook:(wid:number,id:number)=>req<void>(`/api/workspaces/${wid}/webhooks/${id}`,{method:'DELETE'}),
  createPublicNewsPage:(wid:number,p:{channel_id:number|null;title:string;description:string})=>req<{id:number;title:string;description:string;channel_id:number|null;path:string}>(`/api/workspaces/${wid}/public-news-pages`,{method:'POST',body:JSON.stringify(p)}),
  deletePublicNewsPage:(wid:number,id:number)=>req<void>(`/api/workspaces/${wid}/public-news-pages/${id}`,{method:'DELETE'}),
  publicNewsPage:(token:string)=>req<PublicNewsPage>(`/api/public-news/${encodeURIComponent(token)}`),
  publicNewsUploadUrl:(token:string,p:{file_name:string;content_type:string;size:number})=>req<UploadTicket>(`/api/public-news/${encodeURIComponent(token)}/upload-url`,{method:'POST',body:JSON.stringify(p)}),
  publicNewsSubmit:(token:string,p:{title:string;text:string;contact_name:string;contact_telegram:string;contact_email:string;source_url:string;is_anonymous:boolean;asset_ids:number[]})=>req<{request_id:number;post_id:number;message:string}>(`/api/public-news/${encodeURIComponent(token)}/submit`,{method:'POST',body:JSON.stringify(p)}),
  pending:()=>req<Pending[]>('/api/channel-connections/pending'),
 channels:(wid:number)=>req<Channel[]>(`/api/workspaces/${wid}/channels`),
 workspaceSnapshot:(wid:number)=>req<{pending:Pending[];channels:Channel[];members:Member[];posts:Post[];templates:Template[];advertisers:Advertiser[];bookings:Booking[];feedback:PublicFeedbackItem[];finance_summary:FinanceSummary|null;media_kits:MediaKit[];tasks:Task[]}>(`/api/workspaces/${wid}/snapshot`),
 connect:(wid:number,id:number)=>req<Channel>(`/api/workspaces/${wid}/channels/connect`,{method:'POST',body:JSON.stringify({connection_id:id})}),
 deleteChannel:(wid:number,id:number)=>req<void>(`/api/workspaces/${wid}/channels/${id}`,{method:'DELETE'}),
 members:(wid:number)=>req<Member[]>(`/api/workspaces/${wid}/members`),
 createInvite:(wid:number,role='viewer')=>req<Invite>(`/api/workspaces/${wid}/invites`,{method:'POST',body:JSON.stringify({role})}),
 acceptInvite:(token:string)=>req<{workspace_id:number;workspace_name:string;role:string}>(`/api/invites/accept`,{method:'POST',body:JSON.stringify({token})}),
 audit:(wid:number)=>req<AuditEntry[]>(`/api/workspaces/${wid}/audit`),
 posts:(wid:number)=>req<Post[]>(`/api/workspaces/${wid}/posts`),
 getPost:(wid:number,id:number)=>req<{post:Post;latest_version:Version|null}>(`/api/workspaces/${wid}/posts/${id}`),
 createPost:(wid:number,p:{title:string;text:string;channel_id:number|null;buttons?:Button[][]})=>req<Post>(`/api/workspaces/${wid}/posts`,{method:'POST',body:JSON.stringify(p)}),
 updatePost:(wid:number,id:number,p:{title?:string;text?:string;channel_id?:number|null;buttons?:Button[][]})=>req<Post>(`/api/workspaces/${wid}/posts/${id}`,{method:'PATCH',body:JSON.stringify(p)}),
 submitPost:(wid:number,id:number)=>req<Post>(`/api/workspaces/${wid}/posts/${id}/submit`,{method:'POST'}),
 approvePost:(wid:number,id:number)=>req<Post>(`/api/workspaces/${wid}/posts/${id}/approve`,{method:'POST'}),
 requestChanges:(wid:number,id:number)=>req<Post>(`/api/workspaces/${wid}/posts/${id}/request-changes`,{method:'POST'}),
 schedulePost:(wid:number,id:number,at:string)=>req<Post>(`/api/workspaces/${wid}/posts/${id}/schedule`,{method:'POST',body:JSON.stringify({scheduled_at:at})}),
 publishNow:(wid:number,id:number)=>req<Post>(`/api/workspaces/${wid}/posts/${id}/publish-now`,{method:'POST'}),
 deletePostFromTelegram:(wid:number,id:number)=>req<{id:number;status:string;message:string}>(`/api/workspaces/${wid}/posts/${id}/delete-from-telegram`,{method:'POST'}),
 deletePostFromTelegramStatus:(wid:number,id:number)=>req<{id:number|null;status:'none'|'pending'|'processing'|'done'|'failed';error_text:string|null;created_at:string|null;completed_at:string|null}>(`/api/workspaces/${wid}/posts/${id}/delete-from-telegram`),
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
 advertisers:(wid:number)=>req<Advertiser[]>(`/api/workspaces/${wid}/advertisers`),
 createAdvertiser:(wid:number,p:{name:string;contact?:Record<string,string>;notes?:string})=>req<Advertiser>(`/api/workspaces/${wid}/advertisers`,{method:'POST',body:JSON.stringify(p)}),
 deleteAdvertiser:(wid:number,id:number)=>req<void>(`/api/workspaces/${wid}/advertisers/${id}`,{method:'DELETE'}),
 createPublicReport:(wid:number,advertiserId:number,expiresInDays=30)=>req<{id:number;advertiser_name:string;path:string;expires_at:string}>(`/api/workspaces/${wid}/advertisers/${advertiserId}/public-report`,{method:'POST',body:JSON.stringify({expires_in_days:expiresInDays})}),
 revokePublicReport:(wid:number,advertiserId:number)=>req<void>(`/api/workspaces/${wid}/advertisers/${advertiserId}/public-report`,{method:'DELETE'}),
 bookings:(wid:number,status?:string)=>req<Booking[]>(`/api/workspaces/${wid}/bookings${status?`?status=${status}`:''}`),
 createBooking:(wid:number,p:{advertiser_id:number;channel_id?:number|null;format?:string;cost:number;currency?:string;publish_at?:string|null;delete_at?:string|null;erid?:string|null;erid_required?:boolean;materials_url?:string|null})=>req<Booking>(`/api/workspaces/${wid}/bookings`,{method:'POST',body:JSON.stringify(p)}),
 updateBooking:(wid:number,id:number,p:Record<string,unknown>)=>req<Booking>(`/api/workspaces/${wid}/bookings/${id}`,{method:'PATCH',body:JSON.stringify(p)}),
 payBooking:(wid:number,id:number,payment_status:string)=>req<Booking>(`/api/workspaces/${wid}/bookings/${id}/pay`,{method:'POST',body:JSON.stringify({payment_status})}),
 deleteBooking:(wid:number,id:number)=>req<void>(`/api/workspaces/${wid}/bookings/${id}`,{method:'DELETE'}),
  financeSummary:(wid:number,year:number,month:number)=>req<FinanceSummary>(`/api/workspaces/${wid}/finance/summary?year=${year}&month=${month}`),
  financeTransactions:(wid:number,year:number,month:number,limit=100)=>req<FinanceTx[]>(`/api/workspaces/${wid}/finance/transactions?year=${year}&month=${month}&limit=${limit}`),
  createTransaction:(wid:number,p:{type:'income'|'expense';amount:number;category?:string;description?:string;occurred_at?:string})=>req<FinanceTx>(`/api/workspaces/${wid}/finance/transactions`,{method:'POST',body:JSON.stringify(p)}),
  analytics:(wid:number,p:{channel_id?:number;from_date?:string;to_date?:string}={})=>{const q=new URLSearchParams();if(p.channel_id!=null)q.set('channel_id',String(p.channel_id));if(p.from_date)q.set('from_date',p.from_date);if(p.to_date)q.set('to_date',p.to_date);return req<AnalyticsOverview>(`/api/workspaces/${wid}/analytics${q.toString()?`?${q}`:''}`)},
  trackingLinks:(wid:number)=>req<TrackingLink[]>(`/api/workspaces/${wid}/tracking-links`),
  createTrackingLink:(wid:number,p:{channel_id:number;booking_id?:number|null;name:string;target_url:string;notes?:string})=>req<TrackingLink & {path:string;source:string}>(`/api/workspaces/${wid}/tracking-links`,{method:'POST',body:JSON.stringify(p)}),
  createSlotPage:(wid:number,channelId:number,p:{title?:string;description?:string;default_cost?:number;currency?:string})=>req<{id:number;channel_title:string;path:string}>(`/api/workspaces/${wid}/channels/${channelId}/public-slots`,{method:'POST',body:JSON.stringify(p)}),
  deleteTrackingLink:(wid:number,id:number)=>req<void>(`/api/workspaces/${wid}/tracking-links/${id}`,{method:'DELETE'}),
  mediaKits:(wid:number)=>req<MediaKit[]>(`/api/workspaces/${wid}/media-kits`),
 createMediaKit:(wid:number,p:{name:string;channel_id?:number|null;description?:string;stats?:Record<string,unknown>;pricing?:unknown[];contacts?:Record<string,unknown>})=>req<MediaKit>(`/api/workspaces/${wid}/media-kits`,{method:'POST',body:JSON.stringify(p)}),
 updateMediaKit:(wid:number,id:number,p:Record<string,unknown>)=>req<MediaKit>(`/api/workspaces/${wid}/media-kits/${id}`,{method:'PATCH',body:JSON.stringify(p)}),
 deleteMediaKit:(wid:number,id:number)=>req<void>(`/api/workspaces/${wid}/media-kits/${id}`,{method:'DELETE'}),
 tasks:(wid:number,status?:string)=>req<Task[]>(`/api/workspaces/${wid}/tasks${status?`?status=${status}`:''}`),
 createTask:(wid:number,p:{title:string;description?:string;priority?:string;assignee_id?:number|null;due_at?:string|null;remind_at?:string|null})=>req<Task>(`/api/workspaces/${wid}/tasks`,{method:'POST',body:JSON.stringify(p)}),
 completeTask:(wid:number,id:number)=>req<Task>(`/api/workspaces/${wid}/tasks/${id}/done`,{method:'POST'}),
 deleteTask:(wid:number,id:number)=>req<void>(`/api/workspaces/${wid}/tasks/${id}`,{method:'DELETE'}),
  requestExport:(wid:number,kind:'posts'|'bookings'|'finance'|'media_kits',format:'csv'|'xlsx'|'pdf',period?:{year:number;month:number})=>req<{id:number;kind:string;format:string;status:string;message:string}>(`/api/workspaces/${wid}/exports`,{method:'POST',body:JSON.stringify({kind,format,...(period?{period_year:period.year,period_month:period.month}:{})})}),
  exportsStatus:(wid:number)=>req<{id:number;kind:string;format:string;status:string;error_text:string|null;created_at:string;completed_at:string|null}[]>(`/api/workspaces/${wid}/exports`),
  publicReportFeedback:(wid:number)=>req<PublicFeedbackItem[]>(`/api/workspaces/${wid}/public-report-feedback`),
}
