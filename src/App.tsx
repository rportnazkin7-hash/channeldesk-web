import { useCallback,useEffect,useRef,useState } from 'react'
import { Activity,BarChart3,CalendarDays,CirclePlus,Link2,Megaphone,MoreHorizontal,Radio,RefreshCw,Users,Clock,Wallet,LineChart,Settings,Image as ImageIcon,Send,FileText,ChevronLeft,ChevronRight,MessageSquare,History,Trash2,Plus,Paperclip,X,CheckCircle2,Download } from 'lucide-react'
import { api,type Workspace,type Pending,type Channel,type Member,type Invite,type Post,type Comment,type Version,type Template,type Button,type Asset,type Advertiser,type Booking,type FinanceSummary,type MediaKit,type Task } from './api'
import Statistics from './Statistics'
import Analytics from './Analytics'
import AdCampaignFlow from './AdCampaignFlow'

const APP_VERSION = 'v0.35.0'
type Tab = 'overview'|'calendar'|'ads'|'more'
type DeleteJob = Awaited<ReturnType<typeof api.deletePostFromTelegramStatus>>
const ROLE_LABEL:Record<string,string>={owner:'Владелец',admin:'Администратор',editor:'Редактор',author:'Автор',designer:'Дизайнер',ad_manager:'Рекламный менеджер',analyst:'Аналитик',viewer:'Наблюдатель'}
const STATUS_LABEL:Record<string,string>={idea:'Идея',draft:'Черновик',in_progress:'В работе',review:'На согласовании',changes_requested:'Требует правок',approved:'Одобрено',scheduled:'Запланировано',publishing:'Публикуется…',published:'Опубликовано',failed:'Ошибка',cancelled:'Отменено'}
const MONTHS=['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь']
const BOOKING_STATUS_LABEL:Record<string,string>={requested:'Заявка',confirmed:'Подтверждено',active:'Активно',done:'Выполнено',cancelled:'Отменено',overdue:'Просрочено'}
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
function validButtonUrl(url:string){return /^(https?:\/\/|tg:\/\/)/i.test(url.trim())}

function errorHint(msg:string):string{
 if(msg.includes('401')) return 'Telegram-авторизация не получена. Откройте приложение через Telegram (кнопка WebApp у @channel_desk_bot), а не через браузер.'
 if(msg.includes('503')) return 'Сервер временно не подключился к базе. Обновление повторится автоматически; если ошибка не исчезнет, проверьте Supabase и Vercel.'
 if(msg.includes('500')) return 'Внутренняя ошибка сервера. Проверьте журналы Vercel и состояние миграций БД.'
 if(msg.includes('429')) return 'Слишком много запросов. Подождите минуту и обновите экран.'
 if(msg.includes('Нет соединения')||msg.includes('не ответил')) return 'Проверьте интернет-соединение и обновите экран (кнопка со стрелками вверху).'
 return ''
}

export default function App(){
 const [tab,setTab]=useState<Tab>('overview')
 const [spaces,setSpaces]=useState<Workspace[]>([]),[activeId,setActiveId]=useState<number|null>(null),[pending,setPending]=useState<Pending[]>([]),[channels,setChannels]=useState<Channel[]>([]),[members,setMembers]=useState<Member[]>([]),[invite,setInvite]=useState<Invite|null>(null),[copied,setCopied]=useState(false),[joined,setJoined]=useState<{workspace_name:string;role:string}|null>(null),[exportMsg,setExportMsg]=useState(''),[exportJobs,setExportJobs]=useState<Awaited<ReturnType<typeof api.exportsStatus>>>([]),[deleteNotice,setDeleteNotice]=useState(''),[deletePostId,setDeletePostId]=useState<number|null>(null),[deleteJob,setDeleteJob]=useState<DeleteJob|null>(null),[name,setName]=useState('Моё агентство'),[error,setError]=useState(''),[loading,setLoading]=useState(true)
 const [posts,setPosts]=useState<Post[]>([]),[newTitle,setNewTitle]=useState(''),[newText,setNewText]=useState(''),[draftChannel,setDraftChannel]=useState<number|null>(null),[busy,setBusy]=useState(false)
 const [draftBtns,setDraftBtns]=useState<Button[]>([]),[draftBtnText,setDraftBtnText]=useState(''),[draftBtnUrl,setDraftBtnUrl]=useState(''),[draftFiles,setDraftFiles]=useState<File[]>([])
 const [calYear,setCalYear]=useState(new Date().getFullYear()),[calMonth,setCalMonth]=useState(new Date().getMonth()),[selectedDay,setSelectedDay]=useState<Date|null>(null)
 const [openPost,setOpenPost]=useState<number|null>(null),[comments,setComments]=useState<Record<number,Comment[]>>({}),[versions,setVersions]=useState<Record<number,Version[]>>({}),[commentText,setCommentText]=useState('')
 const [editTitle,setEditTitle]=useState(''),[editText,setEditText]=useState('')
 const [assetsByPost,setAssetsByPost]=useState<Record<number,Asset[]>>({})
 const [templates,setTemplates]=useState<Template[]>([]),[newTplName,setNewTplName]=useState(''),[btnText,setBtnText]=useState(''),[btnUrl,setBtnUrl]=useState('')
 const [advertisers,setAdvertisers]=useState<Advertiser[]>([]),[bookings,setBookings]=useState<Booking[]>([]),[finSummary,setFinSummary]=useState<FinanceSummary|null>(null)
 const [advName,setAdvName]=useState(''),[advContact,setAdvContact]=useState('')
 const [reportUrl,setReportUrl]=useState(''),[reportExpires,setReportExpires]=useState(''),[reportBusy,setReportBusy]=useState(false)
 const [trackingAdvertiserId,setTrackingAdvertiserId]=useState<number|null>(null),[trackingBookingId,setTrackingBookingId]=useState<number|null>(null),[trackingChannelId,setTrackingChannelId]=useState<number|null>(null),[trackingName,setTrackingName]=useState(''),[trackingTarget,setTrackingTarget]=useState(''),[trackingUrl,setTrackingUrl]=useState(''),[trackingBusy,setTrackingBusy]=useState(false)
 const [bkAdv,setBkAdv]=useState<number|null>(null),[bkChannel,setBkChannel]=useState<number|null>(null),[bkCost,setBkCost]=useState(''),[bkDate,setBkDate]=useState(''),[bkTime,setBkTime]=useState('12:00'),[bkErid,setBkErid]=useState(''),[bkNoErid,setBkNoErid]=useState(false)
 const [mediaKits,setMediaKits]=useState<MediaKit[]>([])
 const [showMediaKits,setShowMediaKits]=useState(false)
 const [showStatistics,setShowStatistics]=useState(false)
 const [showAnalytics,setShowAnalytics]=useState(false)
 const [fabOpen,setFabOpen]=useState(false)
 const [showCompose,setShowCompose]=useState(false)
 const [showBookingForm,setShowBookingForm]=useState(false)
 const [showCampaignFlow,setShowCampaignFlow]=useState(false)
 const active=spaces.find(x=>x.id===activeId)||spaces[0]||null
 const [showSettings,setShowSettings]=useState(false)
 const [confirmDelete,setConfirmDelete]=useState(false)
 const [overdueCancelDays,setOverdueCancelDays]=useState(3),[savingSettings,setSavingSettings]=useState(false)
 const [bookingTab,setBookingTab]=useState<'future'|'active'|'history'>('future')
 const [showAdvForm,setShowAdvForm]=useState(false)
 const [tasks,setTasks]=useState<Task[]>([])
 const [showTasks,setShowTasks]=useState(false)
 const [taskTitle,setTaskTitle]=useState(''),[taskDesc,setTaskDesc]=useState(''),[taskPriority,setTaskPriority]=useState('normal'),[taskDue,setTaskDue]=useState('')
 const [mkName,setMkName]=useState(''),[mkChannel,setMkChannel]=useState<number|null>(null),[mkDesc,setMkDesc]=useState(''),[mkSubs,setMkSubs]=useState(''),[mkPrice,setMkPrice]=useState('')
 const hasInitData=!!(window.Telegram?.WebApp?.initData)
 const refreshInFlight=useRef(false)

 async function load(){setLoading(true);setError('');try{const s=await api.workspaces();setSpaces(s);const a=s.find(x=>x.id===activeId)||s[0]||null;setActiveId(a?a.id:null);const [p,c,m,po,t,ad,bk,fs,mk,ts]=await Promise.all([api.pending(),a?api.channels(a.id):Promise.resolve([]),a?api.members(a.id):Promise.resolve([]),a?api.posts(a.id):Promise.resolve([]),a?api.templates(a.id):Promise.resolve([]),a?api.advertisers(a.id):Promise.resolve([]),a?api.bookings(a.id):Promise.resolve([]),a?api.financeSummary(a.id,new Date().getFullYear(),new Date().getMonth()+1):Promise.resolve(null),a?api.mediaKits(a.id):Promise.resolve([]),a?api.tasks(a.id):Promise.resolve([])]);setPending(p);setChannels(c);setMembers(m);setPosts(po);setTemplates(t);setAdvertisers(ad);setBookings(bk);setFinSummary(fs);setMediaKits(mk);setTasks(ts);setOpenPost(null)}catch(e){setError(e instanceof Error?e.message:'Ошибка загрузки')}finally{setLoading(false)}}
 // Тихий фоновый poll: обновляет данные без индикатора загрузки и без сброса открытых карточек.
 const refresh=useCallback(async ()=>{if(refreshInFlight.current)return;refreshInFlight.current=true;try{const s=await api.workspaces();const a=s.find(x=>x.id===activeId)||s[0]||null;if(!a)return;const [p,c,m,po,t,ad,bk,fs,mk,ts]=await Promise.all([api.pending(),api.channels(a.id),api.members(a.id),api.posts(a.id),api.templates(a.id),api.advertisers(a.id),api.bookings(a.id),api.financeSummary(a.id,new Date().getFullYear(),new Date().getMonth()+1),api.mediaKits(a.id),api.tasks(a.id)]);setPending(p);setChannels(c);setMembers(m);setPosts(po);setTemplates(t);setAdvertisers(ad);setBookings(bk);setFinSummary(fs);setMediaKits(mk);setTasks(ts);setSpaces(s)}catch{/* фоновая ошибка не должна тревожить пользователя */}finally{refreshInFlight.current=false}},[activeId])
 useEffect(()=>{const timer=setInterval(()=>{refresh()},15000);return ()=>clearInterval(timer)},[refresh])
 useEffect(()=>{if(!showSettings||!active)return;api.workspaceSettings(active.id).then(settings=>setOverdueCancelDays(settings.overdue_cancel_days)).catch(e=>setError(e instanceof Error?e.message:'Ошибка загрузки настроек'))},[showSettings,active?.id])
 useEffect(()=>{if(!deletePostId||!deleteJob||deleteJob.status==='done'||deleteJob.status==='failed')return;const timer=setInterval(()=>{void checkDeleteStatus(deletePostId)},5000);return ()=>clearInterval(timer)},[deletePostId,deleteJob?.status,active?.id])
 async function saveWorkspaceSettings(){if(!active)return;setSavingSettings(true);setError('');try{const result=await api.updateWorkspaceSettings(active.id,{overdue_cancel_days:Math.max(1,Math.min(30,Number(overdueCancelDays)||3))});setOverdueCancelDays(result.overdue_cancel_days)}catch(e){setError(e instanceof Error?e.message:'Ошибка сохранения настроек')}finally{setSavingSettings(false)}}
 async function addAdvertiser(){buzz();if(!active)return;setError('');try{await api.createAdvertiser(active.id,{name:advName,notes:advContact});setAdvName('');setAdvContact('');await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка добавления рекламодателя')}}
 async function delAdvertiser(id:number){buzz();if(!active)return;try{await api.deleteAdvertiser(active.id,id);await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка удаления рекламодателя')}}
 async function createAdvertiserReport(id:number){buzz();if(!active)return;setReportBusy(true);setError('');try{const r=await api.createPublicReport(active.id,id,30);const full=`${window.location.origin}${r.path}`;setReportUrl(full);setReportExpires(r.expires_at);try{await navigator.clipboard.writeText(full)}catch{void 0}}catch(e){setError(e instanceof Error?e.message:'Ошибка создания публичного отчёта')}finally{setReportBusy(false)}}
 async function revokeAdvertiserReport(id:number){buzz();if(!active)return;setReportBusy(true);setError('');try{await api.revokePublicReport(active.id,id);setReportUrl('');setReportExpires('')}catch(e){setError(e instanceof Error?e.message:'Ошибка отзыва публичного отчёта')}finally{setReportBusy(false)}}
 async function createTrackingLink(){buzz();if(!active)return;if(!trackingChannelId||!trackingName.trim()||!trackingTarget.trim()){setError('Заполните канал, название и целевую ссылку');return}setTrackingBusy(true);setError('');try{const r=await api.createTrackingLink(active.id,{channel_id:trackingChannelId,booking_id:trackingBookingId,name:trackingName.trim(),target_url:trackingTarget.trim()});const full=`${window.location.origin}${r.path}`;setTrackingUrl(full);setTrackingName('');setTrackingTarget('');try{await navigator.clipboard.writeText(full)}catch{void 0}}catch(e){setError(e instanceof Error?e.message:'Ошибка создания ссылки кампании')}finally{setTrackingBusy(false)}}
 async function addBooking(){buzz();if(!active)return;setError('');try{await api.createBooking(active.id,{advertiser_id:bkAdv??0,cost:Number(bkCost)||0,channel_id:bkChannel,publish_at:bkDate?new Date(`${bkDate}T${bkTime||'12:00'}`).toISOString():null,delete_at:bkDate&&bkTime?new Date(new Date(`${bkDate}T${bkTime||'12:00'}`).getTime()+7*86400000).toISOString():null,erid:bkNoErid?null:(bkErid||null),erid_required:!bkNoErid});setBkAdv(null);setBkCost('');setBkDate('');setBkTime('12:00');setBkErid('');setBkNoErid(false);await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка создания брони')}}
 async function payBooking(id:number){buzz();if(!active)return;try{await api.payBooking(active.id,id,'paid');await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка отметки оплаты')}}
 async function delBooking(id:number){buzz();if(!active)return;try{await api.deleteBooking(active.id,id);await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка удаления брони')}}
 async function addMediaKit(){buzz();if(!active)return;setError('');try{const stats={subscribers:mkSubs?Number(mkSubs):0};const pricing=mkPrice?[{format:'post',price:Number(mkPrice)||0}]:[];await api.createMediaKit(active.id,{name:mkName,channel_id:mkChannel,description:mkDesc,stats,pricing});setMkName('');setMkChannel(null);setMkDesc('');setMkSubs('');setMkPrice('');await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка создания медиакита')}}
 async function delMediaKit(id:number){buzz();if(!active)return;try{await api.deleteMediaKit(active.id,id);await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка удаления медиакита')}}
 async function addTask(){buzz();if(!active)return;setError('');try{await api.createTask(active.id,{title:taskTitle,description:taskDesc,priority:taskPriority,due_at:taskDue?new Date(taskDue).toISOString():null});setTaskTitle('');setTaskDesc('');setTaskPriority('normal');setTaskDue('');await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка создания задачи')}}
 async function completeTask(id:number){buzz();if(!active)return;try{await api.completeTask(active.id,id);await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка отметки задачи')}}
 async function delTask(id:number){buzz();if(!active)return;try{await api.deleteTask(active.id,id);await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка удаления задачи')}}
 async function doDeleteWorkspace(){if(!active)return;setBusy(true);setError('');try{await api.deleteWorkspace(active.id);setConfirmDelete(false);setShowSettings(false);const s=await api.workspaces();setSpaces(s);setActiveId(s.length?s[0].id:null);await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка удаления агентства');setConfirmDelete(false)}finally{setBusy(false)}}
 async function sendExport(kind:'posts'|'bookings'|'finance'|'media_kits',format:'csv'|'xlsx'|'pdf',period?:{year:number;month:number}){buzz();if(!active)return;setExportMsg('');try{await api.requestExport(active.id,kind,format,period);const periodText=period?` за ${period.month}.${period.year}`:'';setExportMsg(`Файл ${kind}.${format}${periodText} будет отправлен ботом в Telegram в течение ~30 секунд`);setTimeout(()=>setExportMsg(''),8000);checkExports()}catch(e){setError(e instanceof Error?e.message:'Ошибка экспорта')}}
 async function checkExports(){if(!active)return;try{const j=await api.exportsStatus(active.id);setExportJobs(j)}catch{}}
 useEffect(()=>{const sp=window.Telegram?.WebApp?.initDataUnsafe?.start_param||'';if(sp.startsWith('invite_')){api.acceptInvite(sp.slice('invite_'.length)).then(res=>{setJoined({workspace_name:res.workspace_name,role:res.role});return load()}).catch(e=>{setError(e instanceof Error?e.message:'Ошибка принятия приглашения');return load()})}else{load()}},[])
 async function create(){buzz();try{await api.createWorkspace(name);setName('Моё агентство');await load();setTab('overview')}catch(e){setError(e instanceof Error?e.message:'Ошибка')}}
 async function connect(id:number){buzz();if(!active)return;try{await api.connect(active.id,id);await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка подключения')}}
 async function makeInvite(){buzz();if(!active)return;setError('');try{const iv=await api.createInvite(active.id,'editor');setInvite(iv);setCopied(false)}catch(e){setError(e instanceof Error?e.message:'Ошибка создания приглашения')}}
 async function copyInvite(){buzz();if(!invite)return;try{await navigator.clipboard.writeText(invite.token);setCopied(true)}catch{setCopied(false)}}
 function goSection(id:string){buzz();setTab('overview');setTimeout(()=>{document.getElementById(id)?.scrollIntoView({behavior:'smooth',block:'start'})},80)}
 async function createDraft(){buzz();if(!active)return;setBusy(true);setError('');try{const post=await api.createPost(active.id,{title:newTitle,text:newText,channel_id:draftChannel,buttons:draftBtns.length?[draftBtns]:[]});for(const f of draftFiles){const ticket=await api.uploadTicket(active.id,{post_id:post.id,file_name:f.name,content_type:f.type||'application/octet-stream',size:f.size});await api.uploadDirect(ticket,f)}setNewTitle('');setNewText('');setDraftChannel(null);setDraftBtns([]);setDraftFiles([]);await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка создания черновика')}finally{setBusy(false)}}
 function addDraftBtn(){buzz();const t=draftBtnText.trim(),u=draftBtnUrl.trim();if(!t||!u)return;if(!validButtonUrl(u)){setError('URL кнопки должен начинаться с https://, http:// или tg://');return}setDraftBtns([...draftBtns,{text:t,url:u}]);setDraftBtnText('');setDraftBtnUrl('')}
 function pickFiles(list:FileList|null){if(!list)return;setDraftFiles([...draftFiles,...Array.from(list)].slice(0,10))}
 async function actPost(id:number,kind:'submit'|'approve'|'changes'|'schedule'|'now'|'cancel'){buzz();if(!active)return;setBusy(true);setError('');try{const w=active.id;if(kind==='submit')await api.submitPost(w,id);if(kind==='approve')await api.approvePost(w,id);if(kind==='changes')await api.requestChanges(w,id);if(kind==='schedule')await api.schedulePost(w,id,new Date(Date.now()+3600000).toISOString());if(kind==='now')await api.publishNow(w,id);if(kind==='cancel')await api.cancelPost(w,id);await load();if(kind==='now')setTimeout(()=>{load()},5000)}catch(e){setError(e instanceof Error?e.message:'Ошибка операции')}finally{setBusy(false)}}
 async function savePostContent(id:number){buzz();if(!active)return;setBusy(true);setError('');try{await api.updatePost(active.id,id,{title:editTitle,text:editText});await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка сохранения поста')}finally{setBusy(false)}}
 async function checkDeleteStatus(id:number){if(!active)return;try{const job=await api.deletePostFromTelegramStatus(active.id,id);setDeletePostId(id);setDeleteJob(job);if(job.status==='done'){setDeleteNotice('Пост удалён из Telegram');await load()}else if(job.status==='failed'){setDeleteNotice(`Удаление не выполнено: ${job.error_text||'неизвестная ошибка'}`)}else if(job.status==='pending'||job.status==='processing'){setDeleteNotice(job.status==='processing'?'Бот удаляет пост из Telegram…':'Удаление стоит в очереди…')}}catch(e){setError(e instanceof Error?e.message:'Ошибка проверки удаления поста')}}
 async function requestDeleteFromTelegram(id:number){buzz();if(!active)return;if(!window.confirm('Удалить опубликованный пост из Telegram? Это действие нельзя отменить.'))return;setBusy(true);setError('');setDeleteNotice('Ставлю удаление в очередь…');setDeletePostId(id);try{await api.deletePostFromTelegram(active.id,id);await checkDeleteStatus(id)}catch(e){setError(e instanceof Error?e.message:'Ошибка постановки удаления в очередь')}finally{setBusy(false)}}
 async function openDetails(id:number){buzz();if(!active)return;const w=active.id;const post=posts.find(item=>item.id===id);setOpenPost(openPost===id?null:id);if(openPost!==id){setEditTitle(post?.title||'');setEditText(post?.text||'');try{const [cm,vs,as]=await Promise.all([api.comments(w,id),api.versions(w,id),api.assets(w,id)]);setComments(prev=>({...prev,[id]:cm}));setVersions(prev=>({...prev,[id]:vs}));setAssetsByPost(prev=>({...prev,[id]:as}))}catch(e){setError(e instanceof Error?e.message:'Ошибка загрузки деталей')}}}
 async function uploadToPost(id:number,files:FileList|null){buzz();if(!active||!files||!files.length)return;const w=active.id;setBusy(true);setError('');try{for(const f of Array.from(files).slice(0,10)){const ticket=await api.uploadTicket(w,{post_id:id,file_name:f.name,content_type:f.type||'application/octet-stream',size:f.size});await api.uploadDirect(ticket,f)}const as=await api.assets(w,id);setAssetsByPost(prev=>({...prev,[id]:as}))}catch(e){setError(e instanceof Error?e.message:'Ошибка загрузки вложения')}finally{setBusy(false)}}
 async function delAsset(postId:number,assetId:number){buzz();if(!active)return;try{await api.deleteAsset(assetId);const as=await api.assets(active.id,postId);setAssetsByPost(prev=>({...prev,[postId]:as}))}catch(e){setError(e instanceof Error?e.message:'Ошибка удаления вложения')}}
 async function addCommentTo(id:number){buzz();if(!active||!commentText.trim())return;const w=active.id;try{await api.addComment(w,id,commentText.trim());setCommentText('');const cm=await api.comments(w,id);setComments(prev=>({...prev,[id]:cm}))}catch(e){setError(e instanceof Error?e.message:'Ошибка добавления комментария')}}
 async function addButtonTo(id:number){buzz();if(!active||!btnText.trim()||!btnUrl.trim())return;if(!validButtonUrl(btnUrl)){setError('URL кнопки должен начинаться с https://, http:// или tg://');return}const w=active.id;try{const post=posts.find(p=>p.id===id);const cur=post?.buttons||[];const next=[...cur,[{text:btnText.trim(),url:btnUrl.trim()}]];await api.updatePost(w,id,{buttons:next});setBtnText('');setBtnUrl('');await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка добавления кнопки')}}
 async function removeButtonFrom(postId:number,rowIndex:number,buttonIndex:number){buzz();if(!active)return;const post=posts.find(item=>item.id===postId);if(!post)return;const next=(post.buttons||[]).map((row,rowNo)=>row.filter((_,itemNo)=>rowNo!==rowIndex||itemNo!==buttonIndex)).filter(row=>row.length);try{await api.updatePost(active.id,postId,{buttons:next});await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка удаления кнопки')}}
 async function useTemplate(t:Template){buzz();setNewTitle(t.title);setNewText(t.text);setFabOpen(false);setShowCompose(true);setTimeout(()=>{document.getElementById('draft-form')?.scrollIntoView({behavior:'smooth'})},80)}
 function openCreate(kind:'post'|'booking'|'task'|'advertiser'){buzz();setFabOpen(false);if(kind==='post'){setShowCompose(true);return}if(kind==='task'){setShowTasks(true);return}if(kind==='booking'){if(active)setShowCampaignFlow(true);else setError('Сначала создайте рабочее пространство');return}setShowAdvForm(true)}
 async function saveTemplate(){buzz();if(!active||!newTplName.trim())return;try{await api.createTemplate(active.id,{name:newTplName.trim(),title:newTitle,text:newText});setNewTplName('');await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка сохранения шаблона')}}
 async function delTemplate(id:number){buzz();if(!active)return;try{await api.deleteTemplate(active.id,id);await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка удаления шаблона')}}
 const canManage=active?.role==='owner'||active?.role==='admin'
 const canAdvertiserManage=canManage||active?.role==='ad_manager'
 const canReview=active?.role==='owner'||active?.role==='admin'||active?.role==='editor'
 const canSchedule=canReview||active?.role==='ad_manager'
 const hint=error?errorHint(error):''
 const todayKey=dayKey(new Date())
 const calCells=monthGrid(calYear,calMonth)
 const dayPosts=selectedDay?posts.filter(p=>postDayKey(p)===dayKey(selectedDay)):posts

 const futureBookings=bookings.filter(b=>['requested','confirmed'].includes(b.status))
 const activeBookings=bookings.filter(b=>b.status==='active')
 const historyBookings=bookings.filter(b=>['done','cancelled','overdue'].includes(b.status))
 function renderBookingCard(b:Booking){
  return <article key={b.id} style={{padding:'12px 0',borderBottom:'1px solid var(--border)'}}>
   <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:10}}>
    <strong style={{fontSize:14}}>{b.advertiser_name||`#${b.advertiser_id}`}</strong>
    <span className={"status status-"+b.status}>{BOOKING_STATUS_LABEL[b.status]||b.status}</span>
   </div>
   <p style={{color:'var(--muted)',fontSize:12,margin:'6px 0 0'}}>
    {FORMAT_LABEL[b.format]||b.format} · {b.cost.toLocaleString('ru-RU')} {b.currency}
    {b.channel_title?` · ${b.channel_title}`:''}
   </p>
   {(b.publish_at||b.delete_at)&&<p style={{color:'var(--text-2)',fontSize:12,margin:'5px 0 0'}}>
    {b.publish_at?`📅 с ${fmtDate(b.publish_at)}`:''}{b.delete_at?` по ${fmtDate(b.delete_at)}`:''}
   </p>}
   {!b.erid_required?<span className="no-erid-badge">без ERID</span>:b.erid?<p style={{color:'var(--muted-2)',fontSize:11,margin:'4px 0 0'}}>{b.erid}</p>:<span className="no-erid-badge warn">ERID не указан</span>}
   <div style={{display:'flex',gap:8,flexWrap:'wrap',marginTop:10,alignItems:'center'}}>
    <span className={"status "+(b.payment_status==='paid'?'status-published':b.payment_status==='partially_paid'?'status-review':'status-cancelled')}>{PAYMENT_LABEL[b.payment_status]||b.payment_status}</span>
    {b.payment_status!=='paid'&&!['done','cancelled'].includes(b.status)&&<button onClick={()=>payBooking(b.id)} disabled={busy}>✓ Оплачено</button>}
    {b.status==='active'&&canAdvertiserManage&&<button className="icon-btn danger" onClick={()=>{if(window.confirm('Убрать активное размещение и перенести его в историю?'))void delBooking(b.id)}} disabled={busy}>Убрать из активных</button>}
   </div>
  </article>
 }
 function renderPostCard(p:Post){
  const open=openPost===p.id
  const editable=['idea','draft','in_progress','approved','scheduled'].includes(p.status)
  return <article key={p.id} style={{padding:'14px 0',borderBottom:'1px solid var(--border)'}}>
   <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:10}}>
    <strong style={{fontSize:14}}>{p.title||'(без заголовка)'}</strong>
    <span className={"status status-"+p.status}>{STATUS_LABEL[p.status]||p.status}</span>
   </div>
   <p style={{color:'var(--muted)',fontSize:12,margin:'6px 0 0'}}>
    {p.channel_title||'без канала'}
    {p.scheduled_at?` · ${fmtDate(p.scheduled_at)}`:''}
    {p.author_username?` · @${p.author_username}`:''}
   </p>
   {p.text&&<p style={{fontSize:13,margin:'8px 0 0',lineHeight:1.5}}>{p.text.length>160?p.text.slice(0,160)+'…':p.text}</p>}
   {p.buttons&&p.buttons.length>0&&<div style={{display:'flex',gap:6,flexWrap:'wrap',marginTop:8}}>{p.buttons.map((row,rowIndex)=>row.map((b,buttonIndex)=><span key={`${rowIndex}-${buttonIndex}`} className="btn-chip">🔗 {b.text}{editable&&<button onClick={()=>void removeButtonFrom(p.id,rowIndex,buttonIndex)} style={{background:'none',border:0,color:'var(--danger)',padding:'0 2px',marginLeft:3}}><X size={11}/></button>}</span>))}</div>}
   <div style={{display:'flex',gap:8,flexWrap:'wrap',marginTop:10}}>
    {['draft','in_progress','idea','changes_requested'].includes(p.status)&&<button onClick={()=>actPost(p.id,'submit')} disabled={busy}><Send size={14}/> На согласование</button>}
    {p.status==='review'&&canReview&&<><button onClick={()=>actPost(p.id,'approve')} disabled={busy}>✓ Одобрить</button><button onClick={()=>actPost(p.id,'changes')} disabled={busy}>Правки</button></>}
    {p.status==='approved'&&canSchedule&&<><button onClick={()=>actPost(p.id,'now')} disabled={busy}><Send size={14}/> Опубликовать сейчас</button><button onClick={()=>actPost(p.id,'schedule')} disabled={busy}>⏱ +1 час</button></>}
    {p.status==='scheduled'&&canSchedule&&<button onClick={()=>actPost(p.id,'now')} disabled={busy}><Send size={14}/> Опубликовать сейчас</button>}
    {p.status==='published'&&(canSchedule||canAdvertiserManage)&&<button className="icon-btn danger" onClick={()=>void requestDeleteFromTelegram(p.id)} disabled={busy}>Удалить из Telegram</button>}
    {p.status==='failed'&&canSchedule&&<button onClick={()=>actPost(p.id,'now')} disabled={busy}><Send size={14}/> Повторить</button>}
    {p.status==='cancelled'&&canSchedule&&<button onClick={()=>actPost(p.id,'now')} disabled={busy}><Send size={14}/> Возобновить</button>}
    {p.status==='failed'&&p.last_error&&<p style={{color:'var(--danger)',fontSize:11,marginTop:8,width:'100%'}}>Причина: {p.last_error}</p>}
    {!['published','cancelled','publishing'].includes(p.status)&&<button onClick={()=>actPost(p.id,'cancel')} disabled={busy} style={{opacity:.7}}>Отменить</button>}
    <button onClick={()=>openDetails(p.id)} disabled={busy} style={{opacity:.8}}>{open?'Свернуть':'Подробнее'}</button>
   </div>
   {open&&<div style={{marginTop:12,padding:12,borderRadius:14,background:'var(--panel-2)',border:'1px solid var(--border)'}}>
    {editable&&<div className="post-editor">
     <label className="form-label">Заголовок рекламного поста</label>
     <input className="field" value={editTitle} onChange={e=>setEditTitle(e.target.value)} placeholder="Заголовок" />
     <label className="form-label">Текст публикации</label>
     <textarea className="field" rows={7} value={editText} onChange={e=>setEditText(e.target.value)} placeholder="Текст рекламного поста…" />
     <button className="primary-btn" onClick={()=>void savePostContent(p.id)} disabled={busy}>Сохранить текст поста</button>
    </div>}
    {editable&&<div style={{marginBottom:12}}>
     <strong style={{fontSize:13}}>Кнопка (URL)</strong>
     <div style={{display:'flex',gap:8,marginTop:8}}>
      <input placeholder="Текст кнопки" value={btnText} onChange={e=>setBtnText(e.target.value)} style={{flex:1,padding:10,borderRadius:10,border:'1px solid var(--border-2)',background:'var(--field-bg)',color:'white',fontSize:13}}/>
      <input placeholder="https://" value={btnUrl} onChange={e=>setBtnUrl(e.target.value)} style={{flex:1.5,padding:10,borderRadius:10,border:'1px solid var(--border-2)',background:'var(--field-bg)',color:'white',fontSize:13}}/>
      <button onClick={()=>addButtonTo(p.id)} disabled={busy||!btnText.trim()||!btnUrl.trim()}><Plus size={15}/></button>
     </div>
    </div>}
    <div style={{marginBottom:12}}>
     <strong style={{fontSize:13,display:'flex',alignItems:'center',gap:6}}><Paperclip size={14}/> Вложения ({(assetsByPost[p.id]||[]).length})</strong>
     {(assetsByPost[p.id]||[]).length>0&&<div style={{display:'flex',flexWrap:'wrap',gap:8,marginTop:8}}>
      {(assetsByPost[p.id]||[]).map(a=>a.file_type.startsWith('image/')?<div key={a.id} style={{position:'relative'}}><img src={a.file_url} alt={a.file_name} style={{width:64,height:64,borderRadius:10,objectFit:'cover',border:'1px solid var(--border-2)'}}/>{editable&&<button onClick={()=>delAsset(p.id,a.id)} style={{position:'absolute',top:-6,right:-6,background:'var(--danger-bg)',border:'1px solid var(--danger-border)',color:'var(--danger)',borderRadius:'50%',width:20,height:20,display:'grid',placeItems:'center',padding:0}}><X size={11}/></button>}</div>:<div key={a.id} style={{display:'flex',alignItems:'center',gap:6,border:'1px solid var(--border-2)',borderRadius:10,padding:'6px 10px',background:'var(--chip-bg)',fontSize:12}}>📎 <a href={a.file_url} target="_blank" rel="noreferrer" style={{color:'var(--accent-2)',textDecoration:'none'}}>{a.file_name.length>20?a.file_name.slice(0,20)+'…':a.file_name}</a>{editable&&<button onClick={()=>delAsset(p.id,a.id)} style={{background:'none',border:0,color:'var(--danger)',padding:0,marginLeft:4}}><X size={12}/></button>}</div>)}
     </div>}
     {editable&&<label className="file-btn" style={{marginTop:8}}><Paperclip size={14}/> Добавить файл<input type="file" multiple accept="image/*,video/*,.pdf,.doc,.docx,.xls,.xlsx,.txt" style={{display:'none'}} onChange={e=>{uploadToPost(p.id,e.target.files);e.target.value=''}}/></label>}
    </div>
    <div style={{marginBottom:12}}>
     <strong style={{fontSize:13,display:'flex',alignItems:'center',gap:6}}><MessageSquare size={14}/> Комментарии</strong>
     <div style={{display:'flex',gap:8,marginTop:8}}>
      <input placeholder="Комментарий…" value={commentText} onChange={e=>setCommentText(e.target.value)} style={{flex:1,padding:10,borderRadius:10,border:'1px solid var(--border-2)',background:'var(--field-bg)',color:'white',fontSize:13}}/>
      <button onClick={()=>addCommentTo(p.id)} disabled={busy||!commentText.trim()}>Отправить</button>
     </div>
     {(comments[p.id]||[]).length?comments[p.id].map(cm=><div key={cm.id} style={{marginTop:8,fontSize:12}}><span style={{color:'var(--accent-2)'}}>{cm.first_name||cm.username||'?'}:</span> {cm.text}<div style={{color:'var(--muted-2)',fontSize:10}}>{fmtDate(cm.created_at)}</div></div>):<p style={{color:'var(--muted-2)',fontSize:12,marginTop:8}}>Комментариев пока нет.</p>}
    </div>
    <div>
     <strong style={{fontSize:13,display:'flex',alignItems:'center',gap:6}}><History size={14}/> Версии</strong>
     {(versions[p.id]||[]).length?versions[p.id].slice(0,5).map(v=><div key={v.id} style={{marginTop:8,fontSize:12,color:'var(--text-2)'}}><span style={{color:'var(--muted-2)'}}>{fmtDate(v.created_at)}</span> · {v.title||'(без заголовка)'} · {(v.text||'').slice(0,60)}{v.text&&v.text.length>60?'…':''}</div>):<p style={{color:'var(--muted-2)',fontSize:12,marginTop:8}}>Версий пока нет.</p>}
    </div>
   </div>}
  </article>
 }

 return <div className="app"><header><div><span className="eyebrow">РАБОЧЕЕ ПРОСТРАНСТВО</span><h1>ChannelDesk</h1></div><button className="workspace" onClick={()=>{buzz();load()}} title="Обновить"><RefreshCw size={15}/></button></header><main>
  {!hasInitData&&<section className="panel warn"><strong>⚠ Приложение работает только внутри Telegram</strong><p>Откройте его через бота <code>@channel_desk_bot</code> (кнопка «Открыть ChannelDesk») — так Telegram передаст авторизацию.</p></section>}
  {error&&<section className="panel err"><strong>{error}</strong>{hint&&<p className="hint">{hint}</p>}</section>}
  {joined&&<section className="panel ok">✓ Вы присоединились к «{joined.workspace_name}» (роль: {ROLE_LABEL[joined.role]||joined.role})</section>}
  {exportMsg&&<section className="panel ok">{exportMsg} <button className="icon-btn" style={{marginLeft:8}} onClick={()=>{buzz();checkExports()}}>Статус</button></section>}
  {deleteNotice&&<section className={`panel ${deleteJob?.status==='failed'?'err':'ok'}`}>{deleteNotice}{deletePostId&&deleteJob?.status!=='done'&&<button className="icon-btn" style={{marginLeft:8}} onClick={()=>{buzz();void checkDeleteStatus(deletePostId)}}>Проверить удаление</button>}</section>}
  {exportJobs.length>0&&<section className="panel" style={{marginTop:8}}><div className="panel-title"><h2>Экспорты</h2><Download size={16}/></div>
   {exportJobs.map(j=><div key={j.id} style={{padding:'8px 0',borderBottom:'1px solid var(--border)',fontSize:12,display:'flex',justifyContent:'space-between',alignItems:'center'}}>
    <span>{j.kind}.{j.format} — <b>{j.status==='done'?'отправлен':j.status==='processing'?'готовится…':j.status==='failed'?'ошибка':j.status}</b></span>
    {j.status==='failed'&&j.error_text&&<span style={{color:'var(--danger)'}}>{j.error_text.slice(0,80)}</span>}
   </div>)}
  </section>}

  {!showCompose&&!showTasks&&!showMediaKits&&!showStatistics&&!showAnalytics&&!showCampaignFlow&&!showBookingForm&&!showAdvForm&&!showSettings&&tab==='overview'&&<>
   {!active&&!loading?<section className="hero"><p>Создайте рабочее пространство агентства.</p><input value={name} onChange={e=>setName(e.target.value)} style={{width:'100%',padding:13,borderRadius:12,border:'1px solid var(--border-2)',background:'var(--field-bg)',color:'white',marginBottom:12}}/><button onClick={create}><CirclePlus size={19}/> Создать</button></section>:<>
    <section className="hero"><span className="eyebrow">{active?.role}</span><p style={{marginTop:8}}>{active?.name}</p><div>{spaces.length>1&&<select value={active?.id} onChange={e=>{buzz();setActiveId(Number(e.target.value))}}>{spaces.map(w=><option key={w.id} value={w.id}>{w.name}</option>)}</select>}</div></section>
    {pending.length>0&&<section className="panel" style={{marginTop:16}}><div className="panel-title"><h2>Обнаруженные каналы</h2><Radio size={20}/></div>{pending.map(p=><article key={p.id} style={{padding:'14px 0',borderBottom:'1px solid var(--border)'}}><strong>{p.title}</strong><p style={{color:'var(--muted)',fontSize:12}}>{p.bot_permissions.can_post_messages?'Публикация разрешена':'Нет права публикации'}</p><button onClick={()=>connect(p.id)} disabled={!p.bot_permissions.can_post_messages}>Подключить</button></article>)}</section>}
    <section className="stats"><article><span>Каналы</span><strong>{channels.length}</strong></article><article><span>Запланировано</span><strong>{posts.filter(p=>p.status==='scheduled').length}</strong></article><article><span>На согласовании</span><strong>{posts.filter(p=>p.status==='review').length}</strong></article><article><span>Доход за месяц</span><strong>{finSummary?finSummary.income.toLocaleString('ru-RU'):'0'} ₽</strong></article></section>
    <section id="channels-section" className="panel"><div className="panel-title"><h2>Каналы</h2><CalendarDays size={20}/></div>{channels.length?channels.map(c=><div key={c.id} style={{padding:'15px 0',borderBottom:'1px solid var(--border)'}}><strong>{c.title}</strong><div style={{color:'var(--accent-2)',fontSize:12}}>● подключён</div></div>):<div className="empty"><div className="empty-icon"><Megaphone/></div><h3>Каналов пока нет</h3><p>Добавьте бота администратором канала и обновите экран.</p></div>}</section>
    <section id="team-section" className="panel" style={{marginTop:16}}><div className="panel-title"><h2>Команда</h2><Users size={20}/></div>
     {canManage&&<button className="invite-btn" onClick={makeInvite}><Link2 size={15}/> Создать приглашение (редактор)</button>}
     {invite&&<div className="invite-box"><p>Токен приглашения: <code>{invite.token}</code></p><p className="hint">Ссылка для сотрудника: <code>https://t.me/channel_desk_bot?start=invite_{invite.token}</code></p><button onClick={copyInvite}>{copied?'Скопировано':'Скопировать токен'}</button></div>}
     {members.length?members.map(m=><div key={m.id} style={{padding:'13px 0',borderBottom:'1px solid var(--border)',display:'flex',justifyContent:'space-between',alignItems:'center'}}><strong>{m.first_name||m.username||`ID ${m.telegram_id}`}</strong><span style={{color:'var(--muted)',fontSize:12}}>{ROLE_LABEL[m.role]||m.role}</span></div>):<div className="empty"><p>Участников пока нет.</p></div>}
    </section>
    <section className="panel" style={{marginTop:16}}><div className="panel-title"><h2>Ближайшие задачи</h2><CheckCircle2 size={20}/></div>
     {tasks.filter(t=>t.status!=='done').length===0?<div className="empty"><p>Нет активных задач.</p></div>:tasks.filter(t=>t.status!=='done').slice(0,3).map(tk=><div key={tk.id} style={{padding:'10px 0',borderBottom:'1px solid var(--border)',display:'flex',justifyContent:'space-between',alignItems:'center',gap:10}}>
      <strong style={{fontSize:13}}>{tk.title}</strong>
      <span className={"status "+(tk.priority==='urgent'||tk.priority==='high'?'status-changes_requested':'status-in_progress')}>{tk.priority==='urgent'?'Срочно':tk.priority==='high'?'Высокий':'Обычный'}</span>
     </div>)}
     {tasks.filter(t=>t.status!=='done').length>3&&<button className="icon-btn" style={{marginTop:10}} onClick={()=>{buzz();setShowTasks(true)}}>Все задачи →</button>}
    </section>
   </>}
  </>}

  {!showCompose&&!showTasks&&!showMediaKits&&!showStatistics&&!showAnalytics&&!showCampaignFlow&&!showBookingForm&&!showAdvForm&&!showSettings&&tab==='calendar'&&<>
   {!active?<section className="panel"><div className="empty"><div className="empty-icon"><CalendarDays/></div><h3>Создайте рабочее пространство</h3><p>Календарь публикаций появится после создания пространства и подключения канала.</p></div></section>:<>
    <section className="panel">
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
     <div className="btn-row" style={{marginBottom:12}}>
      <button className="icon-btn" onClick={()=>sendExport('posts','csv')}><Download size={14}/> CSV</button>
      <button className="icon-btn" onClick={()=>sendExport('posts','xlsx')}><Download size={14}/> XLSX</button>
      <button className="icon-btn" onClick={()=>sendExport('posts','pdf')}><Download size={14}/> PDF</button>
     </div>
     {dayPosts.length===0?<div className="empty"><p>Нет публикаций.</p></div>:dayPosts.map(renderPostCard)}
    </section>
   </>}
  </>}

  {!showCompose&&!showTasks&&!showMediaKits&&!showStatistics&&!showAnalytics&&!showCampaignFlow&&!showBookingForm&&!showAdvForm&&!showSettings&&tab==='ads'&&<>
   {!active?<section className="panel"><div className="empty"><div className="empty-icon"><Megaphone/></div><h3>Создайте рабочее пространство</h3><p>Раздел клиентов появится после создания пространства.</p></div></section>:<>
    <section className="panel"><div className="panel-title"><h2>Клиенты</h2><Users size={20}/></div>
     <p style={{color:'var(--muted)',fontSize:12,margin:'4px 0 0'}}>Рекламодатели и размещения. Создание — через «+» внизу.</p>
    </section>

    <section className="panel" style={{marginTop:14}}>
     <div className="panel-title"><h2>Рекламодатели</h2><Users size={20}/></div>
     {reportUrl&&<div className="invite-box" style={{marginTop:10}}><p>Ссылка публичного отчёта скопирована.</p><p className="hint">Действует до {fmtDate(reportExpires)}</p><code>{reportUrl}</code></div>}
     {advertisers.length===0?<div className="empty"><p>Рекламодателей пока нет. Добавьте через кнопку «+» внизу.</p></div>:advertisers.map(a=><div key={a.id} style={{padding:'12px 0',borderBottom:'1px solid var(--border)'}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:8}}><div><strong style={{fontSize:14}}>{a.name}</strong>{a.notes&&<div style={{color:'var(--muted)',fontSize:12}}>{a.notes}</div>}</div><span className="no-erid-badge" style={{marginTop:0}}>{bookings.filter(b=>b.advertiser_id===a.id).length} броней</span></div>
      {canAdvertiserManage&&<><button className="icon-btn" style={{marginTop:9,width:'100%'}} onClick={()=>void createAdvertiserReport(a.id)} disabled={reportBusy}><Link2 size={14}/> {reportBusy?'Создаю ссылку…':'Создать публичный отчёт'}</button><button className="icon-btn danger" style={{marginTop:6,width:'100%'}} onClick={()=>void revokeAdvertiserReport(a.id)} disabled={reportBusy}>Отозвать все публичные ссылки</button></>}
     </div>)}
    </section>

    <section className="panel" style={{marginTop:14}}>
     <div className="panel-title"><h2>Ссылка кампании</h2><Link2 size={20}/></div>
     <p style={{color:'var(--muted)',fontSize:12,margin:'5px 0 0'}}>Переходы считаются автоматически. Ссылка ведёт на целевой URL.</p>
     {canAdvertiserManage&&<>
      <div className="btn-row" style={{marginTop:12}}>
       <select className="field" value={trackingAdvertiserId??''} onChange={e=>{setTrackingAdvertiserId(e.target.value?Number(e.target.value):null);setTrackingBookingId(null)}}><option value="">Рекламодатель (необязательно)</option>{advertisers.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select>
       <select className="field" value={trackingBookingId??''} onChange={e=>{const id=e.target.value?Number(e.target.value):null;const booking=bookings.find(b=>b.id===id);setTrackingBookingId(id);if(booking?.channel_id)setTrackingChannelId(booking.channel_id)}}><option value="">Бронь (необязательно)</option>{bookings.filter(b=>trackingAdvertiserId?b.advertiser_id===trackingAdvertiserId:true).map(b=><option key={b.id} value={b.id}>#{b.id} · {b.advertiser_name||'Реклама'}</option>)}</select>
      </div>
      <select className="field" style={{marginTop:8}} value={trackingChannelId??''} onChange={e=>setTrackingChannelId(e.target.value?Number(e.target.value):null)}><option value="">Канал</option>{channels.map(c=><option key={c.id} value={c.id}>{c.title}</option>)}</select>
      <div className="btn-row" style={{marginTop:8}}><input className="field" placeholder="Название ссылки" value={trackingName} onChange={e=>setTrackingName(e.target.value)}/><input className="field" type="url" placeholder="https://целевой-сайт.ru" value={trackingTarget} onChange={e=>setTrackingTarget(e.target.value)}/></div>
      <button className="primary-btn" onClick={()=>void createTrackingLink()} disabled={trackingBusy}>{trackingBusy?'Создаю…':'Создать ссылку и скопировать'}</button>
      {trackingUrl&&<div className="invite-box"><p>Ссылка скопирована:</p><code>{trackingUrl}</code></div>}
     </>}
    </section>

    <section className="panel" style={{marginTop:14}}>
     <div className="panel-title"><h2>Размещения</h2><Wallet size={20}/></div>
     <div className="seg" style={{marginTop:10}}>
      {(['future','active','history'] as const).map(t=><button key={t} className={bookingTab===t?'seg-on':''} onClick={()=>{buzz();setBookingTab(t)}}>{t==='future'?'Будущие':t==='active'?'Активные':'Архив'}</button>)}
     </div>
     {bookingTab==='future'&&<>
      <div style={{fontSize:11,color:'var(--muted-2)',margin:'10px 2px 2px'}}>Заявки и подтверждённые брони, которые ещё не начались</div>
      {futureBookings.length===0?<div className="empty"><p>Будущих броней нет. Создайте через «+».</p></div>:futureBookings.map(renderBookingCard)}
     </>}
     {bookingTab==='active'&&<>
      <div style={{fontSize:11,color:'var(--muted-2)',margin:'10px 2px 2px'}}>Идут сейчас: с даты начала до даты окончания</div>
      {activeBookings.length===0?<div className="empty"><p>Активных размещений нет.</p></div>:activeBookings.map(renderBookingCard)}
     </>}
     {bookingTab==='history'&&<>
      <div style={{fontSize:11,color:'var(--muted-2)',margin:'10px 2px 2px'}}>Завершённые, отменённые и просроченные</div>
      {historyBookings.length===0?<div className="empty"><p>Архив пуст.</p></div>:historyBookings.map(renderBookingCard)}
     </>}
    </section>
   </>}
  </>}

  {showCampaignFlow&&active&&<AdCampaignFlow workspaceId={active.id} channels={channels} advertisers={advertisers} onBack={()=>{buzz();setShowCampaignFlow(false)}} onDone={()=>{setShowCampaignFlow(false);setTab('calendar');void load()}} onError={setError}/>}

  {showCompose&&<section id="draft-form" className="panel">
   <div className="panel-title"><h2>Новый пост</h2><FileText size={20}/></div>
   <button className="icon-btn" onClick={()=>{buzz();setShowCompose(false)}} style={{marginBottom:10}}>← Назад</button>
   {!active?<>
    <p style={{color:'var(--muted)',fontSize:13}}>Создайте рабочее пространство, чтобы публиковать посты.</p>
    <input className="field" placeholder="Название пространства" value={name} onChange={e=>setName(e.target.value)}/>
    <button className="primary-btn" onClick={create}><CirclePlus size={18}/> Создать пространство</button>
   </>:<>
    <label className="form-label">Заголовок</label>
    <input className="field" placeholder="О чём пост?" value={newTitle} onChange={e=>setNewTitle(e.target.value)}/>
    <label className="form-label">Текст (Telegram HTML: &lt;b&gt;, &lt;i&gt;, &lt;a href=…&gt;)</label>
    <textarea className="field" rows={5} placeholder="Текст публикации…" value={newText} onChange={e=>setNewText(e.target.value)}/>
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
    {draftBtns.length>0&&<div className="chip-wrap">{draftBtns.map((b,i)=><span key={i} className="btn-chip">🔗 {b.text} <button onClick={()=>{buzz();setDraftBtns(draftBtns.filter((_,j)=>j!==i))}} style={{background:'none',border:0,color:'var(--danger)',padding:'0 2px',marginLeft:4}}><X size={11}/></button></span>)}</div>}
    <label className="form-label">Вложения (фото, видео, документы)</label>
    <label className="file-btn"><Paperclip size={15}/> Выбрать файлы<input type="file" multiple accept="image/*,video/*,.pdf,.doc,.docx,.xls,.xlsx,.txt" style={{display:'none'}} onChange={e=>pickFiles(e.target.files)}/></label>
    {draftFiles.length>0&&<div className="chip-wrap">{draftFiles.map((f,i)=><span key={i} className="btn-chip">📎 {f.name.length>22?f.name.slice(0,22)+'…':f.name} <button onClick={()=>{buzz();setDraftFiles(draftFiles.filter((_,j)=>j!==i))}} style={{background:'none',border:0,color:'var(--danger)',padding:'0 2px',marginLeft:4}}><X size={11}/></button></span>)}</div>}
    <div style={{marginTop:14}}><span style={{color:'var(--muted)',fontSize:12}}>Шаблоны: </span>{templates.length?templates.map(t=><button key={t.id} onClick={()=>useTemplate(t)} disabled={busy} className="chip-btn">{t.name}</button>):<span style={{color:'var(--muted-2)',fontSize:12}}>нет</span>}</div>
    <button className="primary-btn" onClick={createDraft} disabled={busy||!newTitle.trim()}><CirclePlus size={18}/> Создать черновик {draftFiles.length?`(${draftFiles.length} вл.)`:''}</button>
   </>}
  </section>}

      {showSettings&&<section className="panel">
   <div className="panel-title"><h2>Настройки</h2><Settings size={20}/></div>
   <button className="icon-btn" onClick={()=>{buzz();setShowSettings(false)}} style={{marginBottom:10}}>← Назад</button>
   {active?<>
    <div style={{fontSize:13,color:'var(--muted)'}}>Рабочее пространство</div>
    <p style={{margin:'8px 0 0',fontSize:16,fontWeight:700}}>{active.name}</p>
    <div style={{fontSize:12,color:'var(--muted-2)',marginTop:4}}>Ваша роль: {ROLE_LABEL[active.role]||active.role}</div>
    <div style={{marginTop:22,paddingTop:14,borderTop:'1px solid var(--border)'}}>
     <label className="form-label" style={{marginTop:0}}>Дней до автоотмены просроченной брони</label>
     <p style={{fontSize:11,color:'var(--muted-2)',margin:'5px 0 8px'}}>Неоплаченная бронь после даты публикации станет просроченной, а затем будет отменена автоматически.</p>
     <div className="btn-row">
      <input className="field" type="number" min="1" max="30" value={overdueCancelDays} onChange={e=>setOverdueCancelDays(Number(e.target.value)||1)} disabled={!canManage}/>
      {canManage&&<button className="icon-btn" onClick={()=>void saveWorkspaceSettings()} disabled={savingSettings}>{savingSettings?'Сохраняю…':'Сохранить'}</button>}
     </div>
    </div>
    {active.role==='owner'&&<div style={{marginTop:24}}>
     <div style={{fontSize:13,color:'var(--danger)',fontWeight:600}}>Опасная зона</div>
     <p style={{fontSize:12,color:'var(--muted-2)',margin:'6px 0 10px'}}>Удаление скроет агентство и все его данные (каналы, посты, рекламу, финансы). Действие нельзя отменить в интерфейсе.</p>
     {!confirmDelete?<button className="icon-btn danger" onClick={()=>{buzz();setConfirmDelete(true)}}>Удалить агентство</button>
      :<div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
        <button style={{border:'1px solid var(--danger-border)',background:'var(--danger-bg)',color:'var(--danger)',borderRadius:10,padding:'10px 14px',fontWeight:700}} onClick={()=>doDeleteWorkspace()}>Точно удалить</button>
        <button className="icon-btn" onClick={()=>{buzz();setConfirmDelete(false)}}>Отмена</button>
       </div>}
    </div>}
   </>:<p style={{color:'var(--muted)'}}>Создайте агентство, чтобы настроить пространство.</p>}
  </section>}

{showBookingForm&&<section className="panel">
   <div className="panel-title"><h2>Новая бронь</h2><Megaphone size={20}/></div>
   <button className="icon-btn" onClick={()=>{buzz();setShowBookingForm(false)}} style={{marginBottom:10}}>← Назад</button>
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
   </div>
   <label className="form-label">Начало публикации (дата и время)</label>
   <div className="btn-row">
    <input className="field" type="date" value={bkDate} onChange={e=>setBkDate(e.target.value)}/>
    <input className="field" type="time" value={bkTime} onChange={e=>setBkTime(e.target.value)}/>
   </div>
   <div style={{fontSize:11,color:'var(--muted-2)',marginTop:6}}>Окончание — через 7 дней после начала.</div>
   <label className="form-label" style={{display:'flex',alignItems:'center',gap:10,cursor:'pointer'}}>
    <input type="checkbox" checked={bkNoErid} onChange={e=>setBkNoErid(e.target.checked)} style={{width:18,height:18,accentColor:'var(--accent-2)'}}/>
    <span>ERID не требуется (обычный Telegram-канал)</span>
   </label>
   {!bkNoErid&&<>
    <label className="form-label">ERID</label>
    <input className="field" placeholder="erid: …" value={bkErid} onChange={e=>setBkErid(e.target.value)}/>
   </>}
   <button className="primary-btn" onClick={async()=>{await addBooking();setShowBookingForm(false)}} disabled={!bkAdv}><Megaphone size={17}/> Создать бронь</button>
  </section>}

  {showAdvForm&&<section className="panel">
   <div className="panel-title"><h2>Новый рекламодатель</h2><Users size={20}/></div>
   <button className="icon-btn" onClick={()=>{buzz();setShowAdvForm(false)}} style={{marginBottom:10}}>← Назад</button>
   <label className="form-label">Название / компания</label>
   <input className="field" placeholder="ООО Реклама" value={advName} onChange={e=>setAdvName(e.target.value)}/>
   <label className="form-label">Контакты</label>
   <input className="field" placeholder="@telegram, телефон, email…" value={advContact} onChange={e=>setAdvContact(e.target.value)} style={{marginTop:10}}/>
   <button className="primary-btn" onClick={async()=>{await addAdvertiser();setShowAdvForm(false)}} disabled={!advName.trim()}><Plus size={17}/> Добавить рекламодателя</button>
  </section>}

{showTasks&&<section className="panel">
   <div className="panel-title"><h2>Задачи</h2><CheckCircle2 size={20}/></div>
   <button className="icon-btn" onClick={()=>{buzz();setShowTasks(false)}} style={{marginBottom:12}}>← Назад</button>
   <label className="form-label">Новая задача</label>
   <input className="field" placeholder="Что нужно сделать?" value={taskTitle} onChange={e=>setTaskTitle(e.target.value)}/>
   <textarea className="field" rows={2} placeholder="Описание…" value={taskDesc} onChange={e=>setTaskDesc(e.target.value)} style={{marginTop:10}}/>
   <div className="btn-row" style={{marginTop:10}}>
    <select className="field" value={taskPriority} onChange={e=>setTaskPriority(e.target.value)}>
     <option value="low">Низкий</option><option value="normal">Обычный</option><option value="high">Высокий</option><option value="urgent">Срочный</option>
    </select>
    <input className="field" placeholder="Срок (дата)" type="date" value={taskDue} onChange={e=>setTaskDue(e.target.value)}/>
   </div>
   <button className="primary-btn" onClick={addTask} disabled={!taskTitle.trim()}><Plus size={17}/> Создать задачу</button>
   <div style={{marginTop:18}}>
    {tasks.length===0?<div className="empty"><p>Задач пока нет.</p></div>:tasks.map(tk=><article key={tk.id} style={{padding:'13px 0',borderBottom:'1px solid var(--border)'}}>
     <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:10}}>
      <strong style={{fontSize:14,textDecoration:tk.status==='done'?'line-through':'none',opacity:tk.status==='done'?.6:1}}>{tk.title}</strong>
      <span className={"status "+(tk.status==='done'?'status-published':tk.priority==='urgent'||tk.priority==='high'?'status-changes_requested':'status-scheduled')}>{tk.status==='done'?'Готово':tk.priority==='urgent'?'Срочно':tk.priority==='high'?'Высокий':'Обычный'}</span>
     </div>
     {tk.description&&<p style={{color:'var(--muted)',fontSize:12,margin:'6px 0 0'}}>{tk.description}</p>}
     <p style={{color:'var(--muted-2)',fontSize:11,margin:'4px 0 0'}}>
      {tk.due_at?`Срок: ${fmtDate(tk.due_at)}`:''}
      {tk.assignee_first_name?` · Исполнитель: ${tk.assignee_first_name}`:''}
     </p>
     <div style={{display:'flex',gap:8,marginTop:10}}>
      {tk.status!=='done'&&<button onClick={()=>completeTask(tk.id)} disabled={busy}>✓ Выполнено</button>}
      <button onClick={()=>delTask(tk.id)} disabled={busy} style={{opacity:.7}}>Удалить</button>
     </div>
    </article>)}
   </div>
  </section>}

  {showMediaKits&&<section className="panel">
   <div className="panel-title"><h2>Медиакиты</h2><ImageIcon size={20}/></div>
   <button className="icon-btn" onClick={()=>{buzz();setShowMediaKits(false)}} style={{marginBottom:12}}>← Назад</button>
   <label className="form-label">Название</label>
   <input className="field" placeholder="Медиакит канала «Новости»" value={mkName} onChange={e=>setMkName(e.target.value)}/>
   <label className="form-label">Канал</label>
   <select className="field" value={mkChannel??''} onChange={e=>setMkChannel(e.target.value?Number(e.target.value):null)}>
    <option value="">— без канала —</option>
    {channels.map(c=><option key={c.id} value={c.id}>{c.title}</option>)}
   </select>
   <label className="form-label">Описание</label>
   <textarea className="field" rows={2} placeholder="О канале, аудитории…" value={mkDesc} onChange={e=>setMkDesc(e.target.value)}/>
   <div className="btn-row" style={{marginTop:14}}>
    <input className="field" placeholder="Подписчики" type="number" value={mkSubs} onChange={e=>setMkSubs(e.target.value)}/>
    <input className="field" placeholder="Цена поста, ₽" type="number" value={mkPrice} onChange={e=>setMkPrice(e.target.value)}/>
   </div>
   <button className="primary-btn" onClick={addMediaKit} disabled={!mkName.trim()}><Plus size={17}/> Создать медиакит</button>
   <button className="icon-btn" onClick={()=>sendExport('media_kits','pdf')} disabled={!mediaKits.length} style={{marginTop:10,width:'100%'}}><Download size={14}/> Отправить медиакиты PDF в Telegram</button>
   <div style={{marginTop:18}}>
    {mediaKits.length===0?<div className="empty"><p>Медиакитов пока нет.</p></div>:mediaKits.map(k=><article key={k.id} style={{padding:'13px 0',borderBottom:'1px solid var(--border)'}}>
     <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:10}}>
      <strong style={{fontSize:14}}>{k.name}</strong>
      <button onClick={()=>delMediaKit(k.id)} disabled={busy} className="icon-btn danger" title="Удалить"><Trash2 size={14}/></button>
     </div>
     <p style={{color:'var(--muted)',fontSize:12,margin:'6px 0 0'}}>
      {k.channel_title||'без канала'}
      {k.stats&&typeof k.stats==='object'&&'subscribers' in k.stats&&(k.stats as Record<string,number>).subscribers?` · ${Number((k.stats as Record<string,number>).subscribers).toLocaleString('ru-RU')} подписчиков`:''}
     </p>
     {k.description&&<p style={{fontSize:13,margin:'6px 0 0',color:'var(--text-2)'}}>{k.description}</p>}
     {Array.isArray(k.pricing)&&k.pricing.length>0&&<p style={{color:'var(--accent-2)',fontSize:12,margin:'6px 0 0'}}>{(k.pricing[0] as {format?:string;price?:number}).format||'пост'}: {(k.pricing[0] as {price?:number}).price?.toLocaleString('ru-RU')} ₽</p>}
    </article>)}
   </div>
  </section>}

  {showAnalytics&&active&&<Analytics workspaceId={active.id} channels={channels} onBack={()=>{buzz();setShowAnalytics(false)}} onError={setError}/>}
  {showStatistics&&active&&<Statistics workspaceId={active.id} onBack={()=>{buzz();setShowStatistics(false)}} onExport={(format,year,month)=>sendExport('finance',format,{year,month})} onError={setError}/>}

  {!showStatistics&&!showAnalytics&&!showCampaignFlow&&!showMediaKits&&!showTasks&&!showCompose&&!showBookingForm&&!showAdvForm&&!showSettings&&tab==='more'&&<section className="panel"><div className="panel-title"><h2>Ещё</h2><MoreHorizontal size={20}/></div>
   {[
    {icon:Megaphone,label:'Каналы',desc:'Управление подключёнными каналами',action:()=>goSection('channels-section')},
    {icon:Users,label:'Команда',desc:'Участники и приглашения',action:()=>goSection('team-section')},
    {icon:CheckCircle2,label:'Задачи',desc:'Задачи и напоминания',action:()=>{buzz();setShowTasks(true)}},
    {icon:LineChart,label:'Статистика',desc:'Доходы, расходы, прибыль и отчёты',action:()=>{buzz();if(active)setShowStatistics(true);else setError('Сначала создайте рабочее пространство')}},
    {icon:Activity,label:'Аналитика каналов',desc:'Охват, просмотры, ссылки и метрики',action:()=>{buzz();if(active)setShowAnalytics(true);else setError('Сначала создайте рабочее пространство')}},
    {icon:ImageIcon,label:'Медиакиты',desc:'Презентация для рекламодателей',action:()=>{buzz();setShowMediaKits(true)}},
    {icon:Settings,label:'Настройки',desc:'Пространство и уведомления',action:()=>{buzz();setShowSettings(true)}},
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
 </main><nav>
  <button className={tab==='overview'?'active':''} onClick={()=>{buzz();setTab('overview')}}><BarChart3 size={21}/><span>Обзор</span></button>
  <button className={tab==='calendar'?'active':''} onClick={()=>{buzz();setTab('calendar')}}><CalendarDays size={21}/><span>Календарь</span></button>
  <button className="fab" onClick={()=>{buzz();setFabOpen(!fabOpen)}} title="Создать"><CirclePlus size={26}/><span>Создать</span></button>
  <button className={tab==='ads'?'active':''} onClick={()=>{buzz();setTab('ads')}}><Megaphone size={21}/><span>Клиенты</span></button>
  <button className={tab==='more'?'active':''} onClick={()=>{buzz();setTab('more')}}><MoreHorizontal size={21}/><span>Ещё</span></button>
 </nav>
 {fabOpen&&<div className="fab-overlay" onClick={()=>setFabOpen(false)}>
  <div className="fab-sheet" onClick={e=>e.stopPropagation()}>
   <div className="panel-title"><h2>Что создаём?</h2><button className="icon-btn" onClick={()=>setFabOpen(false)}><X size={15}/></button></div>
   <button className="fab-item" onClick={()=>openCreate('post')}><span className="menu-icon"><FileText size={19}/></span><span className="menu-body"><strong>Новый пост</strong><span>Текст, кнопки, вложения</span></span></button>
   <button className="fab-item" onClick={()=>openCreate('booking')}><span className="menu-icon"><Megaphone size={19}/></span><span className="menu-body"><strong>Рекламная бронь</strong><span>Рекламодатель, канал, цена</span></span></button>
   <button className="fab-item" onClick={()=>openCreate('task')}><span className="menu-icon"><CheckCircle2 size={19}/></span><span className="menu-body"><strong>Задача</strong><span>Для команды, со сроком</span></span></button>
   <button className="fab-item" onClick={()=>openCreate('advertiser')}><span className="menu-icon"><Users size={19}/></span><span className="menu-body"><strong>Рекламодатель</strong><span>Новый клиент</span></span></button>
  </div>
 </div>}
 </div>
}
