import { useEffect,useState } from 'react'
import { BarChart3,CalendarDays,CirclePlus,Link2,Megaphone,MoreHorizontal,Radio,RefreshCw,Users,Clock,Wallet,LineChart,Settings,Image as ImageIcon,Send,FileText,ChevronLeft,ChevronRight,MessageSquare,History,Trash2,Plus,Paperclip,X } from 'lucide-react'
import { api,type Workspace,type Pending,type Channel,type Member,type Invite,type Post,type Comment,type Version,type Template,type Button,type Asset,type Advertiser,type Booking,type FinanceSummary } from './api'

const APP_VERSION = 'v0.11.1'
type Tab = 'overview'|'calendar'|'create'|'ads'|'more'
const ROLE_LABEL:Record<string,string>={owner:'Владелец',admin:'Администратор',editor:'Редактор',author:'Автор',designer:'Дизайнер',ad_manager:'Рекламный менеджер',analyst:'Аналитик',viewer:'Наблюдатель'}
const STATUS_LABEL:Record<string,string>={idea:'Идея',draft:'Черновик',in_progress:'В работе',review:'На согласовании',changes_requested:'Требует правок',approved:'Одобрено',scheduled:'Запланировано',publishing:'Публикуется…',published:'Опубликовано',failed:'Ошибка',cancelled:'Отменено'}
const MONTHS=['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь']
const BOOKING_STATUS_LABEL:Record<string,string>={requested:'Заявка',confirmed:'Подтверждено',in_progress:'Идёт',done:'Выполнено',cancelled:'Отменено'}
const PAYMENT_LABEL:Record<string,string>={unpaid:'Не оплачено',partially_paid:'Частично',paid:'Оплачено'}
const FORMAT_LABEL:Record<string,string>={post:'Пост',mention:'Упоминание',repost:'Репост',other:'Другое'}

function buzz(){try{window.Telegram?.WebApp?.HapticFeedback?.impactOccurred?.('light')}catch{}}
function dayKey(d:Date){return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`}
function postDayKey(p:Post){const d=p.scheduled_at?new Date(p.scheduled_at):new Date(p.created_at);return dayKey(d)}
function monthGrid(year:number,month:number):(Date|null)[]{
 const first=new Date(year,month,1);const start=(first.getDay()+6)%7
 const days=new Date(year,month+1,0).getDate();const cells:(Date|null)[]=[]
 for(let i=0;i<start;i++)cells.push(null)
 for(let d=1;d<=days;d++)cells.push(new Date(year,month,d))
 return cells
}
function fmtDate(s:string){try{return new Date(s).toLocaleString('ru-RU',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})}catch{return s}}

function errorHint(msg:string):string{
 if(msg.includes('401')) return 'Telegram-авторизация не получена. Откройте приложение через Telegram (кнопка WebApp у @channel_desk_bot), а не через браузер.'
 if(msg.includes('503')) return 'Серверная служба недоступна: проверьте DATABASE_URL на Vercel и состояние БД Supabase.'
 if(msg.includes('500')) return 'Внутренняя ошибка сервера. Проверьте журналы Vercel и состояние миграций БД.'
 if(msg.includes('429')) return 'Слишком много запросов. Подождите минуту и обновите экран.'
 if(msg.includes('Нет соединения')||msg.includes('не ответил')) return 'Проверьте интернет-соединение и обновите экран (кнопка со стрелками вверху).'
 return ''
}

export default function App(){
 const [tab,setTab]=useState<Tab>('overview')
 const [spaces,setSpaces]=useState<Workspace[]>([]),[active,setActive]=useState<Workspace|null>(null),[pending,setPending]=useState<Pending[]>([]),[channels,setChannels]=useState<Channel[]>([]),[members,setMembers]=useState<Member[]>([]),[invite,setInvite]=useState<Invite|null>(null),[copied,setCopied]=useState(false),[joined,setJoined]=useState<{workspace_name:string;role:string}|null>(null),[name,setName]=useState('Моё агентство'),[error,setError]=useState(''),[loading,setLoading]=useState(true)
 const [posts,setPosts]=useState<Post[]>([]),[newTitle,setNewTitle]=useState(''),[newText,setNewText]=useState(''),[draftChannel,setDraftChannel]=useState<number|null>(null),[busy,setBusy]=useState(false)
 const [draftBtns,setDraftBtns]=useState<Button[]>([]),[draftBtnText,setDraftBtnText]=useState(''),[draftBtnUrl,setDraftBtnUrl]=useState(''),[draftFiles,setDraftFiles]=useState<File[]>([])
 const [calYear,setCalYear]=useState(new Date().getFullYear()),[calMonth,setCalMonth]=useState(new Date().getMonth()),[selectedDay,setSelectedDay]=useState<Date|null>(null)
 const [openPost,setOpenPost]=useState<number|null>(null),[comments,setComments]=useState<Record<number,Comment[]>>({}),[versions,setVersions]=useState<Record<number,Version[]>>({}),[commentText,setCommentText]=useState('')
 const [assetsByPost,setAssetsByPost]=useState<Record<number,Asset[]>>({})
 const [templates,setTemplates]=useState<Template[]>([]),[newTplName,setNewTplName]=useState(''),[btnText,setBtnText]=useState(''),[btnUrl,setBtnUrl]=useState('')
 const [advertisers,setAdvertisers]=useState<Advertiser[]>([]),[bookings,setBookings]=useState<Booking[]>([]),[finSummary,setFinSummary]=useState<FinanceSummary|null>(null)
 const [advName,setAdvName]=useState(''),[advContact,setAdvContact]=useState('')
 const [bkAdv,setBkAdv]=useState<number|null>(null),[bkChannel,setBkChannel]=useState<number|null>(null),[bkCost,setBkCost]=useState(''),[bkDate,setBkDate]=useState(''),[bkErid,setBkErid]=useState(''),[bkNoErid,setBkNoErid]=useState(false)
 const [finType,setFinType]=useState<'income'|'expense'>('income'),[finAmount,setFinAmount]=useState(''),[finDesc,setFinDesc]=useState('')
 const [adsTab,setAdsTab]=useState<'bookings'|'advertisers'|'finance'>('bookings')
 const hasInitData=!!(window.Telegram?.WebApp?.initData)

 async function load(){setLoading(true);setError('');try{const s=await api.workspaces();setSpaces(s);const a=active&&s.some(x=>x.id===active.id)?active:s[0]||null;setActive(a);const [p,c,m,po,t,ad,bk,fs]=await Promise.all([api.pending(),a?api.channels(a.id):Promise.resolve([]),a?api.members(a.id):Promise.resolve([]),a?api.posts(a.id):Promise.resolve([]),a?api.templates(a.id):Promise.resolve([]),a?api.advertisers(a.id):Promise.resolve([]),a?api.bookings(a.id):Promise.resolve([]),a?api.financeSummary(a.id,new Date().getFullYear(),new Date().getMonth()+1):Promise.resolve(null)]);setPending(p);setChannels(c);setMembers(m);setPosts(po);setTemplates(t);setAdvertisers(ad);setBookings(bk);setFinSummary(fs);setOpenPost(null)}catch(e){setError(e instanceof Error?e.message:'Ошибка загрузки')}finally{setLoading(false)}}
 async function addAdvertiser(){buzz();if(!active)return;setError('');try{await api.createAdvertiser(active.id,{name:advName,notes:advContact});setAdvName('');setAdvContact('');await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка добавления рекламодателя')}}
 async function delAdvertiser(id:number){buzz();if(!active)return;try{await api.deleteAdvertiser(active.id,id);await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка удаления рекламодателя')}}
 async function addBooking(){buzz();if(!active)return;setError('');try{await api.createBooking(active.id,{advertiser_id:bkAdv??0,cost:Number(bkCost)||0,channel_id:bkChannel,publish_at:bkDate?new Date(bkDate).toISOString():null,erid:bkNoErid?null:(bkErid||null),erid_required:!bkNoErid});setBkAdv(null);setBkCost('');setBkDate('');setBkErid('');setBkNoErid(false);await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка создания брони')}}
 async function payBooking(id:number){buzz();if(!active)return;try{await api.payBooking(active.id,id,'paid');await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка отметки оплаты')}}
 async function delBooking(id:number){buzz();if(!active)return;try{await api.deleteBooking(active.id,id);await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка удаления брони')}}
 async function addFinance(){buzz();if(!active)return;setError('');try{await api.createTransaction(active.id,{type:finType,amount:Number(finAmount)||0,category:finType==='income'?'advertising':'other',description:finDesc});setFinAmount('');setFinDesc('');await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка добавления транзакции')}}
 useEffect(()=>{const sp=window.Telegram?.WebApp?.initDataUnsafe?.start_param||'';if(sp.startsWith('invite_')){api.acceptInvite(sp.slice('invite_'.length)).then(res=>{setJoined({workspace_name:res.workspace_name,role:res.role});return load()}).catch(e=>{setError(e instanceof Error?e.message:'Ошибка принятия приглашения');return load()})}else{load()}},[])
 async function create(){buzz();try{await api.createWorkspace(name);setName('Моё агентство');await load();setTab('overview')}catch(e){setError(e instanceof Error?e.message:'Ошибка')}}
 async function connect(id:number){buzz();if(!active)return;try{await api.connect(active.id,id);await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка подключения')}}
 async function makeInvite(){buzz();if(!active)return;setError('');try{const iv=await api.createInvite(active.id,'editor');setInvite(iv);setCopied(false)}catch(e){setError(e instanceof Error?e.message:'Ошибка создания приглашения')}}
 async function copyInvite(){buzz();if(!invite)return;try{await navigator.clipboard.writeText(invite.token);setCopied(true)}catch{setCopied(false)}}
 function goSection(id:string){buzz();setTab('overview');setTimeout(()=>{document.getElementById(id)?.scrollIntoView({behavior:'smooth',block:'start'})},80)}
 async function createDraft(){buzz();if(!active)return;setBusy(true);setError('');try{const post=await api.createPost(active.id,{title:newTitle,text:newText,channel_id:draftChannel,buttons:draftBtns.length?[draftBtns]:[]});for(const f of draftFiles){const ticket=await api.uploadTicket(active.id,{post_id:post.id,file_name:f.name,content_type:f.type||'application/octet-stream',size:f.size});await api.uploadDirect(ticket,f)}setNewTitle('');setNewText('');setDraftChannel(null);setDraftBtns([]);setDraftFiles([]);await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка создания черновика')}finally{setBusy(false)}}
 function addDraftBtn(){buzz();const t=draftBtnText.trim(),u=draftBtnUrl.trim();if(!t||!u)return;setDraftBtns([...draftBtns,{text:t,url:u}]);setDraftBtnText('');setDraftBtnUrl('')}
 function pickFiles(list:FileList|null){if(!list)return;setDraftFiles([...draftFiles,...Array.from(list)].slice(0,10))}
 async function actPost(id:number,kind:'submit'|'approve'|'changes'|'schedule'|'now'|'cancel'){buzz();if(!active)return;setBusy(true);setError('');try{const w=active.id;if(kind==='submit')await api.submitPost(w,id);if(kind==='approve')await api.approvePost(w,id);if(kind==='changes')await api.requestChanges(w,id);if(kind==='schedule')await api.schedulePost(w,id,new Date(Date.now()+3600000).toISOString());if(kind==='now')await api.publishNow(w,id);if(kind==='cancel')await api.cancelPost(w,id);await load();if(kind==='now')setTimeout(()=>{load()},5000)}catch(e){setError(e instanceof Error?e.message:'Ошибка операции')}finally{setBusy(false)}}
 async function openDetails(id:number){buzz();if(!active)return;const w=active.id;setOpenPost(openPost===id?null:id);if(openPost!==id){try{const [cm,vs,as]=await Promise.all([api.comments(w,id),api.versions(w,id),api.assets(w,id)]);setComments(prev=>({...prev,[id]:cm}));setVersions(prev=>({...prev,[id]:vs}));setAssetsByPost(prev=>({...prev,[id]:as}))}catch(e){setError(e instanceof Error?e.message:'Ошибка загрузки деталей')}}}
 async function uploadToPost(id:number,files:FileList|null){buzz();if(!active||!files||!files.length)return;const w=active.id;setBusy(true);setError('');try{for(const f of Array.from(files).slice(0,10)){const ticket=await api.uploadTicket(w,{post_id:id,file_name:f.name,content_type:f.type||'application/octet-stream',size:f.size});await api.uploadDirect(ticket,f)}const as=await api.assets(w,id);setAssetsByPost(prev=>({...prev,[id]:as}))}catch(e){setError(e instanceof Error?e.message:'Ошибка загрузки вложения')}finally{setBusy(false)}}
 async function delAsset(postId:number,assetId:number){buzz();if(!active)return;try{await api.deleteAsset(assetId);const as=await api.assets(active.id,postId);setAssetsByPost(prev=>({...prev,[postId]:as}))}catch(e){setError(e instanceof Error?e.message:'Ошибка удаления вложения')}}
 async function addCommentTo(id:number){buzz();if(!active||!commentText.trim())return;const w=active.id;try{await api.addComment(w,id,commentText.trim());setCommentText('');const cm=await api.comments(w,id);setComments(prev=>({...prev,[id]:cm}))}catch(e){setError(e instanceof Error?e.message:'Ошибка добавления комментария')}}
 async function addButtonTo(id:number){buzz();if(!active||!btnText.trim()||!btnUrl.trim())return;const w=active.id;try{const post=posts.find(p=>p.id===id);const cur=post?.buttons||[];const next=[...cur,[{text:btnText.trim(),url:btnUrl.trim()}]];await api.updatePost(w,id,{buttons:next});setBtnText('');setBtnUrl('');await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка добавления кнопки')}}
 async function useTemplate(t:Template){buzz();setNewTitle(t.title);setNewText(t.text);setTab('calendar');setTimeout(()=>{document.getElementById('draft-form')?.scrollIntoView({behavior:'smooth'})},80)}
 async function saveTemplate(){buzz();if(!active||!newTplName.trim())return;try{await api.createTemplate(active.id,{name:newTplName.trim(),title:newTitle,text:newText});setNewTplName('');await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка сохранения шаблона')}}
 async function delTemplate(id:number){buzz();if(!active)return;try{await api.deleteTemplate(active.id,id);await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка удаления шаблона')}}
 const canManage=active?.role==='owner'||active?.role==='admin'
 const canReview=active?.role==='owner'||active?.role==='admin'||active?.role==='editor'
 const canSchedule=canReview||active?.role==='ad_manager'
 const hint=error?errorHint(error):''
 const todayKey=dayKey(new Date())
 const calCells=monthGrid(calYear,calMonth)
 const dayPosts=selectedDay?posts.filter(p=>postDayKey(p)===dayKey(selectedDay)):posts

 function renderPostCard(p:Post){
  const open=openPost===p.id
  return <article key={p.id} style={{padding:'14px 0',borderBottom:'1px solid #252b36'}}>
   <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:10}}>
    <strong style={{fontSize:14}}>{p.title||'(без заголовка)'}</strong>
    <span className={"status status-"+p.status}>{STATUS_LABEL[p.status]||p.status}</span>
   </div>
   <p style={{color:'#8d96a8',fontSize:12,margin:'6px 0 0'}}>
    {p.channel_title||'без канала'}
    {p.scheduled_at?` · ${fmtDate(p.scheduled_at)}`:''}
    {p.author_username?` · @${p.author_username}`:''}
   </p>
   {p.text&&<p style={{fontSize:13,margin:'8px 0 0',lineHeight:1.5}}>{p.text.length>160?p.text.slice(0,160)+'…':p.text}</p>}
   {p.buttons&&p.buttons.length>0&&<div style={{display:'flex',gap:6,flexWrap:'wrap',marginTop:8}}>{p.buttons.flat().map((b,i)=><span key={i} className="btn-chip">🔗 {b.text}</span>)}</div>}
   <div style={{display:'flex',gap:8,flexWrap:'wrap',marginTop:10}}>
    {['draft','in_progress','idea','changes_requested'].includes(p.status)&&<button onClick={()=>actPost(p.id,'submit')} disabled={busy}><Send size={14}/> На согласование</button>}
    {p.status==='review'&&canReview&&<><button onClick={()=>actPost(p.id,'approve')} disabled={busy}>✓ Одобрить</button><button onClick={()=>actPost(p.id,'changes')} disabled={busy}>Правки</button></>}
    {p.status==='approved'&&canSchedule&&<><button onClick={()=>actPost(p.id,'now')} disabled={busy}><Send size={14}/> Опубликовать сейчас</button><button onClick={()=>actPost(p.id,'schedule')} disabled={busy}>⏱ +1 час</button></>}
    {p.status==='scheduled'&&canSchedule&&<button onClick={()=>actPost(p.id,'now')} disabled={busy}><Send size={14}/> Опубликовать сейчас</button>}
    {p.status==='failed'&&canSchedule&&<button onClick={()=>actPost(p.id,'now')} disabled={busy}><Send size={14}/> Повторить</button>}
    {p.status==='cancelled'&&canSchedule&&<button onClick={()=>actPost(p.id,'now')} disabled={busy}><Send size={14}/> Возобновить</button>}
    {p.status==='failed'&&p.last_error&&<p style={{color:'#ff9b9b',fontSize:11,marginTop:8,width:'100%'}}>Причина: {p.last_error}</p>}
    {!['published','cancelled','publishing'].includes(p.status)&&<button onClick={()=>actPost(p.id,'cancel')} disabled={busy} style={{opacity:.7}}>Отменить</button>}
    <button onClick={()=>openDetails(p.id)} disabled={busy} style={{opacity:.8}}>{open?'Свернуть':'Подробнее'}</button>
   </div>
   {open&&<div style={{marginTop:12,padding:12,borderRadius:14,background:'#0d1119',border:'1px solid #222936'}}>
    {(p.status==='draft'||p.status==='in_progress'||p.status==='idea')&&<div style={{marginBottom:12}}>
     <strong style={{fontSize:13}}>Кнопка (URL)</strong>
     <div style={{display:'flex',gap:8,marginTop:8}}>
      <input placeholder="Текст кнопки" value={btnText} onChange={e=>setBtnText(e.target.value)} style={{flex:1,padding:10,borderRadius:10,border:'1px solid #445',background:'#111722',color:'white',fontSize:13}}/>
      <input placeholder="https://" value={btnUrl} onChange={e=>setBtnUrl(e.target.value)} style={{flex:1.5,padding:10,borderRadius:10,border:'1px solid #445',background:'#111722',color:'white',fontSize:13}}/>
      <button onClick={()=>addButtonTo(p.id)} disabled={busy||!btnText.trim()||!btnUrl.trim()}><Plus size={15}/></button>
     </div>
    </div>}
    <div style={{marginBottom:12}}>
     <strong style={{fontSize:13,display:'flex',alignItems:'center',gap:6}}><Paperclip size={14}/> Вложения ({(assetsByPost[p.id]||[]).length})</strong>
     {(assetsByPost[p.id]||[]).length>0&&<div style={{display:'flex',flexWrap:'wrap',gap:8,marginTop:8}}>
      {(assetsByPost[p.id]||[]).map(a=>a.file_type.startsWith('image/')?<div key={a.id} style={{position:'relative'}}><img src={a.file_url} alt={a.file_name} style={{width:64,height:64,borderRadius:10,objectFit:'cover',border:'1px solid #2c3455'}}/>{(p.status==='draft'||p.status==='in_progress'||p.status==='idea')&&<button onClick={()=>delAsset(p.id,a.id)} style={{position:'absolute',top:-6,right:-6,background:'#2a1414',border:'1px solid #4a2c2c',color:'#ff9b9b',borderRadius:'50%',width:20,height:20,display:'grid',placeItems:'center',padding:0}}><X size={11}/></button>}</div>:<div key={a.id} style={{display:'flex',alignItems:'center',gap:6,border:'1px solid #2c3455',borderRadius:10,padding:'6px 10px',background:'#1a2130',fontSize:12}}>📎 <a href={a.file_url} target="_blank" rel="noreferrer" style={{color:'#8cb3ff',textDecoration:'none'}}>{a.file_name.length>20?a.file_name.slice(0,20)+'…':a.file_name}</a>{(p.status==='draft'||p.status==='in_progress'||p.status==='idea')&&<button onClick={()=>delAsset(p.id,a.id)} style={{background:'none',border:0,color:'#ff9b9b',padding:0,marginLeft:4}}><X size={12}/></button>}</div>)}
     </div>}
     {(p.status==='draft'||p.status==='in_progress'||p.status==='idea')&&<label className="file-btn" style={{marginTop:8}}><Paperclip size={14}/> Добавить файл<input type="file" multiple accept="image/*,video/*,.pdf,.doc,.docx,.xls,.xlsx,.txt" style={{display:'none'}} onChange={e=>{uploadToPost(p.id,e.target.files);e.target.value=''}}/></label>}
    </div>
    <div style={{marginBottom:12}}>
     <strong style={{fontSize:13,display:'flex',alignItems:'center',gap:6}}><MessageSquare size={14}/> Комментарии</strong>
     <div style={{display:'flex',gap:8,marginTop:8}}>
      <input placeholder="Комментарий…" value={commentText} onChange={e=>setCommentText(e.target.value)} style={{flex:1,padding:10,borderRadius:10,border:'1px solid #445',background:'#111722',color:'white',fontSize:13}}/>
      <button onClick={()=>addCommentTo(p.id)} disabled={busy||!commentText.trim()}>Отправить</button>
     </div>
     {(comments[p.id]||[]).length?comments[p.id].map(cm=><div key={cm.id} style={{marginTop:8,fontSize:12}}><span style={{color:'#8cb3ff'}}>{cm.first_name||cm.username||'?'}:</span> {cm.text}<div style={{color:'#5b6475',fontSize:10}}>{fmtDate(cm.created_at)}</div></div>):<p style={{color:'#5b6475',fontSize:12,marginTop:8}}>Комментариев пока нет.</p>}
    </div>
    <div>
     <strong style={{fontSize:13,display:'flex',alignItems:'center',gap:6}}><History size={14}/> Версии</strong>
     {(versions[p.id]||[]).length?versions[p.id].slice(0,5).map(v=><div key={v.id} style={{marginTop:8,fontSize:12,color:'#aeb6c8'}}><span style={{color:'#5b6475'}}>{fmtDate(v.created_at)}</span> · {v.title||'(без заголовка)'} · {(v.text||'').slice(0,60)}{v.text&&v.text.length>60?'…':''}</div>):<p style={{color:'#5b6475',fontSize:12,marginTop:8}}>Версий пока нет.</p>}
    </div>
   </div>}
  </article>
 }

 return <div className="app"><header><div><span className="eyebrow">РАБОЧЕЕ ПРОСТРАНСТВО</span><h1>ChannelDesk</h1></div><button className="workspace" onClick={()=>{buzz();load()}} title="Обновить"><RefreshCw size={15}/></button></header><main>
  {!hasInitData&&<section className="panel warn"><strong>⚠ Приложение работает только внутри Telegram</strong><p>Откройте его через бота <code>@channel_desk_bot</code> (кнопка «Открыть ChannelDesk») — так Telegram передаст авторизацию.</p></section>}
  {error&&<section className="panel err"><strong>{error}</strong>{hint&&<p className="hint">{hint}</p>}</section>}
  {joined&&<section className="panel ok">✓ Вы присоединились к «{joined.workspace_name}» (роль: {ROLE_LABEL[joined.role]||joined.role})</section>}

  {tab==='overview'&&<>
   {!active&&!loading?<section className="hero"><p>Создайте рабочее пространство агентства.</p><input value={name} onChange={e=>setName(e.target.value)} style={{width:'100%',padding:13,borderRadius:12,border:'1px solid #445',background:'#111722',color:'white',marginBottom:12}}/><button onClick={create}><CirclePlus size={19}/> Создать</button></section>:<>
    <section className="hero"><span className="eyebrow">{active?.role}</span><p style={{marginTop:8}}>{active?.name}</p><div>{spaces.length>1&&<select value={active?.id} onChange={e=>{buzz();setActive(spaces.find(x=>x.id===Number(e.target.value))||null)}}>{spaces.map(w=><option key={w.id} value={w.id}>{w.name}</option>)}</select>}</div></section>
    {pending.length>0&&<section className="panel" style={{marginTop:16}}><div className="panel-title"><h2>Обнаруженные каналы</h2><Radio size={20}/></div>{pending.map(p=><article key={p.id} style={{padding:'14px 0',borderBottom:'1px solid #252b36'}}><strong>{p.title}</strong><p style={{color:'#8d96a8',fontSize:12}}>{p.bot_permissions.can_post_messages?'Публикация разрешена':'Нет права публикации'}</p><button onClick={()=>connect(p.id)} disabled={!p.bot_permissions.can_post_messages}>Подключить</button></article>)}</section>}
    <section className="stats"><article><span>Каналы</span><strong>{channels.length}</strong></article><article><span>Запланировано</span><strong>{posts.filter(p=>p.status==='scheduled').length}</strong></article><article><span>На согласовании</span><strong>{posts.filter(p=>p.status==='review').length}</strong></article><article><span>Доход</span><strong>0 ₽</strong></article></section>
    <section id="channels-section" className="panel"><div className="panel-title"><h2>Каналы</h2><CalendarDays size={20}/></div>{channels.length?channels.map(c=><div key={c.id} style={{padding:'15px 0',borderBottom:'1px solid #252b36'}}><strong>{c.title}</strong><div style={{color:'#72d99f',fontSize:12}}>● подключён</div></div>):<div className="empty"><div className="empty-icon"><Megaphone/></div><h3>Каналов пока нет</h3><p>Добавьте бота администратором канала и обновите экран.</p></div>}</section>
    <section id="team-section" className="panel" style={{marginTop:16}}><div className="panel-title"><h2>Команда</h2><Users size={20}/></div>
     {canManage&&<button className="invite-btn" onClick={makeInvite}><Link2 size={15}/> Создать приглашение (редактор)</button>}
     {invite&&<div className="invite-box"><p>Токен приглашения: <code>{invite.token}</code></p><p className="hint">Ссылка для сотрудника: <code>https://t.me/channel_desk_bot?start=invite_{invite.token}</code></p><button onClick={copyInvite}>{copied?'Скопировано':'Скопировать токен'}</button></div>}
     {members.length?members.map(m=><div key={m.id} style={{padding:'13px 0',borderBottom:'1px solid #252b36',display:'flex',justifyContent:'space-between',alignItems:'center'}}><strong>{m.first_name||m.username||`ID ${m.telegram_id}`}</strong><span style={{color:'#8d96a8',fontSize:12}}>{ROLE_LABEL[m.role]||m.role}</span></div>):<div className="empty"><p>Участников пока нет.</p></div>}
    </section>
   </>}
  </>}

  {tab==='calendar'&&<>
   {!active?<section className="panel"><div className="empty"><div className="empty-icon"><CalendarDays/></div><h3>Создайте рабочее пространство</h3><p>Календарь публикаций появится после создания пространства и подключения канала.</p></div></section>:<>
    <section id="draft-form" className="panel">
     <div className="panel-title"><h2>Новый черновик</h2><FileText size={20}/></div>
     <label className="form-label">Заголовок</label>
     <input className="field" placeholder="О чём пост?" value={newTitle} onChange={e=>setNewTitle(e.target.value)}/>
     <label className="form-label">Текст (Telegram HTML: &lt;b&gt;, &lt;i&gt;, &lt;a href=…&gt;)</label>
     <textarea className="field" rows={4} placeholder="Текст публикации…" value={newText} onChange={e=>setNewText(e.target.value)}/>
     <label className="form-label">Канал</label>
     <select className="field" value={draftChannel??''} onChange={e=>setDraftChannel(e.target.value?Number(e.target.value):null)}>
      <option value="">— без канала —</option>
      {channels.map(c=><option key={c.id} value={c.id}>{c.title}</option>)}
     </select>
     <label className="form-label">Кнопки (до 8)</label>
     <div className="btn-row">
      <input className="field" placeholder="Текст кнопки" value={draftBtnText} onChange={e=>setDraftBtnText(e.target.value)}/>
      <input className="field" placeholder="https://…" value={draftBtnUrl} onChange={e=>setDraftBtnUrl(e.target.value)}/>
      <button className="icon-btn" onClick={addDraftBtn} disabled={!draftBtnText.trim()||!draftBtnUrl.trim()} title="Добавить кнопку"><Plus size={16}/></button>
     </div>
     {draftBtns.length>0&&<div className="chip-wrap">{draftBtns.map((b,i)=><span key={i} className="btn-chip">🔗 {b.text} <button onClick={()=>{buzz();setDraftBtns(draftBtns.filter((_,j)=>j!==i))}} style={{background:'none',border:0,color:'#ff9b9b',padding:'0 2px',marginLeft:4}}><X size={11}/></button></span>)}</div>}
     <label className="form-label">Вложения (фото, видео, документы)</label>
     <label className="file-btn"><Paperclip size={15}/> Выбрать файлы<input type="file" multiple accept="image/*,video/*,.pdf,.doc,.docx,.xls,.xlsx,.txt" style={{display:'none'}} onChange={e=>pickFiles(e.target.files)}/></label>
     {draftFiles.length>0&&<div className="chip-wrap">{draftFiles.map((f,i)=><span key={i} className="btn-chip">📎 {f.name.length>22?f.name.slice(0,22)+'…':f.name} <button onClick={()=>{buzz();setDraftFiles(draftFiles.filter((_,j)=>j!==i))}} style={{background:'none',border:0,color:'#ff9b9b',padding:'0 2px',marginLeft:4}}><X size={11}/></button></span>)}</div>}
     <button className="primary-btn" onClick={createDraft} disabled={busy||!newTitle.trim()}><CirclePlus size={18}/> Создать черновик {draftFiles.length?`(${draftFiles.length} вл.)`:''}</button>
     {templates.length>0&&<div style={{marginTop:14}}><span style={{color:'#8d96a8',fontSize:12}}>Шаблоны: </span>{templates.map(t=><button key={t.id} onClick={()=>useTemplate(t)} disabled={busy} className="chip-btn">{t.name}</button>)}</div>}
    </section>

    <section className="panel" style={{marginTop:14}}>
     <div className="cal-head">
      <button className="icon-btn" onClick={()=>{buzz();setCalMonth(m=>m===0?(setCalYear(y=>y-1),11):m-1)}}><ChevronLeft size={17}/></button>
      <strong>{MONTHS[calMonth]} {calYear}</strong>
      <button className="icon-btn" onClick={()=>{buzz();setCalMonth(m=>m===11?(setCalYear(y=>y+1),0):m+1)}}><ChevronRight size={17}/></button>
     </div>
     <div className="cal-grid">{['Пн','Вт','Ср','Чт','Пт','Сб','Вс'].map(d=><div key={d} className="cal-dow">{d}</div>)}
      {calCells.map((d,i)=>d?(()=>{const k=dayKey(d);const has=posts.some(p=>postDayKey(p)===k);const sel=selectedDay&&dayKey(selectedDay)===k;return <button key={i} className={"cal-day"+(has?' has':'')+(sel?' sel':'')+(k===todayKey?' today':'')} onClick={()=>{buzz();setSelectedDay(sel?null:d)}}><span>{d.getDate()}</span>{has&&<i/>}</button>})():<div key={i} className="cal-day empty"/>)}
     </div>
     <div className="cal-hint">{selectedDay?`Посты за ${selectedDay.getDate()} ${MONTHS[selectedDay.getMonth()]}`:'Выберите день, чтобы фильтровать посты'}</div>
    </section>

    <section className="panel" style={{marginTop:14}}><div className="panel-title"><h2>Публикации</h2><Clock size={20}/></div>
     {dayPosts.length===0?<div className="empty"><p>Нет публикаций.</p></div>:dayPosts.map(renderPostCard)}
    </section>
   </>}
  </>}

  {tab==='create'&&<section className="panel"><div className="panel-title"><h2>Создать</h2><CirclePlus size={20}/></div>
   {active?<>
    <button className="invite-btn" onClick={()=>{buzz();setTab('calendar')}}><FileText size={15}/> Новая публикация</button>
    <button className="invite-btn" disabled style={{opacity:.5}}><Megaphone size={15}/> Рекламный слот (Этап C)</button>
    <div style={{margin:'18px 0 10px'}}><strong>Сохранить текущий черновик как шаблон</strong></div>
    <div style={{display:'flex',gap:8}}>
     <input placeholder="Название шаблона" value={newTplName} onChange={e=>setNewTplName(e.target.value)} style={{flex:1,padding:12,borderRadius:12,border:'1px solid #445',background:'#111722',color:'white'}}/>
     <button onClick={saveTemplate} disabled={busy||!newTplName.trim()||!newText.trim()}>Сохранить</button>
    </div>
    {templates.length>0&&<div style={{marginTop:14}}>{templates.map(t=><div key={t.id} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'10px 0',borderBottom:'1px solid #222936'}}><div><strong style={{fontSize:14}}>{t.name}</strong><div style={{color:'#8d96a8',fontSize:12}}>{t.title||'(без заголовка)'}</div></div><div style={{display:'flex',gap:6}}><button onClick={()=>useTemplate(t)} disabled={busy} className="icon-btn"><FileText size={15}/></button><button onClick={()=>delTemplate(t.id)} disabled={busy} className="icon-btn danger"><Trash2 size={15}/></button></div></div>)}</div>}
    <div style={{margin:'18px 0 10px'}}><strong>Новое рабочее пространство</strong></div>
    <input value={name} onChange={e=>setName(e.target.value)} style={{width:'100%',padding:13,borderRadius:12,border:'1px solid #445',background:'#111722',color:'white',marginBottom:12}}/>
    <button onClick={create}><CirclePlus size={19}/> Создать пространство</button>
   </>:<>
    <p style={{color:'#8d96a8',fontSize:14}}>Создайте рабочее пространство, чтобы начать работу.</p>
    <input value={name} onChange={e=>setName(e.target.value)} style={{width:'100%',padding:13,borderRadius:12,border:'1px solid #445',background:'#111722',color:'white',marginBottom:12}}/>
    <button onClick={create}><CirclePlus size={19}/> Создать</button>
   </>}
  </section>}

  {tab==='ads'&&<>
   {!active?<section className="panel"><div className="empty"><div className="empty-icon"><Megaphone/></div><h3>Создайте рабочее пространство</h3><p>Рекламный раздел появится после создания пространства.</p></div></section>:<>
    <section className="panel"><div className="panel-title"><h2>Реклама</h2><Megaphone size={20}/></div>
     <div className="seg">
      {(['bookings','advertisers','finance'] as const).map(t=><button key={t} className={adsTab===t?'seg-on':''} onClick={()=>{buzz();setAdsTab(t)}}>{t==='bookings'?'Брони':t==='advertisers'?'Рекламодатели':'Финансы'}</button>)}
     </div>
     {finSummary&&<div className="fin-cards">
      <div><span>Доход</span><strong>{finSummary.income.toLocaleString('ru-RU')} ₽</strong></div>
      <div><span>Расход</span><strong style={{color:'#ff9b9b'}}>{finSummary.expense.toLocaleString('ru-RU')} ₽</strong></div>
      <div><span>Прибыль</span><strong style={{color:'#72d99f'}}>{finSummary.profit.toLocaleString('ru-RU')} ₽</strong></div>
     </div>}
    </section>

    {adsTab==='bookings'&&<section className="panel" style={{marginTop:14}}>
     <div className="panel-title"><h2>Новая бронь</h2><Wallet size={20}/></div>
     <label className="form-label">Рекламодатель</label>
     <select className="field" value={bkAdv??''} onChange={e=>setBkAdv(e.target.value?Number(e.target.value):null)}>
      <option value="">— выберите —</option>
      {advertisers.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}
     </select>
     <label className="form-label">Канал</label>
     <select className="field" value={bkChannel??''} onChange={e=>setBkChannel(e.target.value?Number(e.target.value):null)}>
      <option value="">— без канала —</option>
      {channels.map(c=><option key={c.id} value={c.id}>{c.title}</option>)}
     </select>
     <div className="btn-row" style={{marginTop:14}}>
      <input className="field" placeholder="Стоимость, ₽" type="number" value={bkCost} onChange={e=>setBkCost(e.target.value)}/>
      <input className="field" placeholder="Дата (ГГГГ-ММ-ДД)" type="date" value={bkDate} onChange={e=>setBkDate(e.target.value)}/>
     </div>
     <label className="form-label" style={{display:'flex',alignItems:'center',gap:10,cursor:'pointer'}}>
      <input type="checkbox" checked={bkNoErid} onChange={e=>setBkNoErid(e.target.checked)} style={{width:18,height:18,accentColor:'#8cb3ff'}}/>
      <span>ERID не требуется (обычный Telegram-канал)</span>
     </label>
     {!bkNoErid&&<>
      <label className="form-label">ERID</label>
      <input className="field" placeholder="erid: …" value={bkErid} onChange={e=>setBkErid(e.target.value)}/>
     </>}
     <button className="primary-btn" onClick={addBooking} disabled={!bkAdv}><Megaphone size={17}/> Создать бронь</button>
     <div className="panel-title" style={{marginTop:20}}><h3 className="list-h">Бронирования</h3></div>
     {bookings.length===0?<div className="empty"><p>Броней пока нет.</p></div>:bookings.map(b=><article key={b.id} style={{padding:'13px 0',borderBottom:'1px solid #222936'}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:10}}>
       <strong style={{fontSize:14}}>{b.advertiser_name||`#${b.advertiser_id}`}</strong>
       <span className={"status status-"+b.status}>{BOOKING_STATUS_LABEL[b.status]||b.status}</span>
      </div>
      <p style={{color:'#8d96a8',fontSize:12,margin:'6px 0 0'}}>
       {FORMAT_LABEL[b.format]||b.format} · {b.cost.toLocaleString('ru-RU')} {b.currency}
       {b.channel_title?` · ${b.channel_title}`:''}
       {b.publish_at?` · ${fmtDate(b.publish_at)}`:''}
      </p>
      {!b.erid_required?<span className="no-erid-badge">без ERID</span>:b.erid?<p style={{color:'#5b6475',fontSize:11,margin:'4px 0 0'}}>{b.erid}</p>:<span className="no-erid-badge warn">ERID не указан</span>}
      <div style={{display:'flex',gap:8,flexWrap:'wrap',marginTop:10,alignItems:'center'}}>
       <span className={"status "+(b.payment_status==='paid'?'status-published':b.payment_status==='partially_paid'?'status-review':'status-cancelled')}>{PAYMENT_LABEL[b.payment_status]||b.payment_status}</span>
       {b.payment_status!=='paid'&&<button onClick={()=>payBooking(b.id)} disabled={busy}>✓ Оплачено</button>}
       <button onClick={()=>delBooking(b.id)} disabled={busy} style={{opacity:.7}}>Удалить</button>
      </div>
     </article>)}
    </section>}

    {adsTab==='advertisers'&&<section className="panel" style={{marginTop:14}}>
     <div className="panel-title"><h2>Новый рекламодатель</h2><Users size={20}/></div>
     <input className="field" placeholder="Название / компания" value={advName} onChange={e=>setAdvName(e.target.value)} style={{marginTop:12}}/>
     <input className="field" placeholder="Контакты (телефон, @telegram, email…)" value={advContact} onChange={e=>setAdvContact(e.target.value)} style={{marginTop:10}}/>
     <button className="primary-btn" onClick={addAdvertiser} disabled={!advName.trim()}><Plus size={17}/> Добавить рекламодателя</button>
     <div className="panel-title" style={{marginTop:20}}><h3 className="list-h">Рекламодатели</h3></div>
     {advertisers.length===0?<div className="empty"><p>Рекламодателей пока нет.</p></div>:advertisers.map(a=><div key={a.id} style={{padding:'13px 0',borderBottom:'1px solid #222936',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
      <div><strong style={{fontSize:14}}>{a.name}</strong>{a.notes&&<div style={{color:'#8d96a8',fontSize:12}}>{a.notes}</div>}</div>
      <button onClick={()=>delAdvertiser(a.id)} disabled={busy} className="icon-btn danger" title="Удалить"><Trash2 size={14}/></button>
     </div>)}
    </section>}

    {adsTab==='finance'&&<section className="panel" style={{marginTop:14}}>
     <div className="panel-title"><h2>Транзакция</h2><Wallet size={20}/></div>
     <div className="seg" style={{marginTop:12}}>
      {(['income','expense'] as const).map(t=><button key={t} className={finType===t?'seg-on':''} onClick={()=>{buzz();setFinType(t)}}>{t==='income'?'Доход':'Расход'}</button>)}
     </div>
     <div className="btn-row" style={{marginTop:12}}>
      <input className="field" placeholder="Сумма" type="number" value={finAmount} onChange={e=>setFinAmount(e.target.value)}/>
     </div>
     <input className="field" placeholder="Описание" value={finDesc} onChange={e=>setFinDesc(e.target.value)} style={{marginTop:10}}/>
     <button className="primary-btn" onClick={addFinance} disabled={!Number(finAmount)}><Plus size={17}/> Добавить</button>
     {finSummary&&<p style={{color:'#8d96a8',fontSize:13,marginTop:16,textAlign:'center'}}>Итог за {MONTHS[finSummary.month-1]}: доход {finSummary.income.toLocaleString('ru-RU')} ₽ · расход {finSummary.expense.toLocaleString('ru-RU')} ₽ · прибыль {finSummary.profit.toLocaleString('ru-RU')} ₽</p>}
    </section>}
   </>}
  </>}

  {tab==='more'&&<section className="panel"><div className="panel-title"><h2>Ещё</h2><MoreHorizontal size={20}/></div>
   {[
    {icon:Megaphone,label:'Каналы',desc:'Управление подключёнными каналами',action:()=>goSection('channels-section')},
    {icon:Users,label:'Команда',desc:'Участники и приглашения',action:()=>goSection('team-section')},
    {icon:Wallet,label:'Финансы',desc:'Доходы и расходы'},
    {icon:LineChart,label:'Аналитика',desc:'Отчёты по каналам'},
    {icon:ImageIcon,label:'Медиакиты',desc:'Презентация для рекламодателей'},
    {icon:Settings,label:'Настройки',desc:'Пространство и уведомления'},
   ].map(item=>{
    const I=item.icon
    const go=()=>{if(item.action){item.action()}else{buzz()}}
    return <button key={item.label} className="menu-item" onClick={go}>
     <span className="menu-icon"><I size={19}/></span>
     <span className="menu-body"><strong>{item.label}</strong><span>{item.desc}</span></span>
     {!item.action&&<span className="menu-soon">скоро</span>}
    </button>
   })}
  </section>}

  <div className="ver">ChannelDesk {APP_VERSION}</div>
 </main><nav>{([[BarChart3,'Обзор','overview'],[CalendarDays,'Календарь','calendar'],[CirclePlus,'Создать','create'],[Megaphone,'Реклама','ads'],[MoreHorizontal,'Ещё','more']] as [typeof BarChart3,string,Tab][]).map(([Icon,label,t])=>{const C=Icon as typeof BarChart3;return <button key={label} className={tab===t?'active':''} onClick={()=>{buzz();setTab(t)}}><C size={21}/><span>{label}</span></button>})}</nav></div>
}
