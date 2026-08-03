import { useEffect,useState } from 'react'
import { BarChart3,CalendarDays,CirclePlus,Link2,Megaphone,MoreHorizontal,Radio,RefreshCw,Users,Clock,Wallet,LineChart,Settings,Image as ImageIcon,Send,FileText } from 'lucide-react'
import { api,type Workspace,type Pending,type Channel,type Member,type Invite,type Post } from './api'

const APP_VERSION = 'v0.7.1'
type Tab = 'overview'|'calendar'|'create'|'ads'|'more'
const ROLE_LABEL:Record<string,string>={owner:'Владелец',admin:'Администратор',editor:'Редактор',author:'Автор',designer:'Дизайнер',ad_manager:'Рекламный менеджер',analyst:'Аналитик',viewer:'Наблюдатель'}
const STATUS_LABEL:Record<string,string>={idea:'Идея',draft:'Черновик',in_progress:'В работе',review:'На согласовании',changes_requested:'Требует правок',approved:'Одобрено',scheduled:'Запланировано',publishing:'Публикуется…',published:'Опубликовано',failed:'Ошибка',cancelled:'Отменено'}

function buzz(){try{window.Telegram?.WebApp?.HapticFeedback?.impactOccurred?.('light')}catch{}}

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
 const hasInitData=!!(window.Telegram?.WebApp?.initData)
 async function load(){setLoading(true);setError('');try{const s=await api.workspaces();setSpaces(s);const a=active&&s.some(x=>x.id===active.id)?active:s[0]||null;setActive(a);const [p,c,m,po]=await Promise.all([api.pending(),a?api.channels(a.id):Promise.resolve([]),a?api.members(a.id):Promise.resolve([]),a?api.posts(a.id):Promise.resolve([])]);setPending(p);setChannels(c);setMembers(m);setPosts(po)}catch(e){setError(e instanceof Error?e.message:'Ошибка загрузки')}finally{setLoading(false)}}
 useEffect(()=>{const sp=window.Telegram?.WebApp?.initDataUnsafe?.start_param||'';if(sp.startsWith('invite_')){api.acceptInvite(sp.slice('invite_'.length)).then(res=>{setJoined({workspace_name:res.workspace_name,role:res.role});return load()}).catch(e=>{setError(e instanceof Error?e.message:'Ошибка принятия приглашения');return load()})}else{load()}},[])
 async function create(){buzz();try{await api.createWorkspace(name);setName('Моё агентство');await load();setTab('overview')}catch(e){setError(e instanceof Error?e.message:'Ошибка')}}
 async function connect(id:number){buzz();if(!active)return;try{await api.connect(active.id,id);await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка подключения')}}
 async function makeInvite(){buzz();if(!active)return;setError('');try{const iv=await api.createInvite(active.id,'editor');setInvite(iv);setCopied(false)}catch(e){setError(e instanceof Error?e.message:'Ошибка создания приглашения')}}
 async function copyInvite(){buzz();if(!invite)return;try{await navigator.clipboard.writeText(invite.token);setCopied(true)}catch{setCopied(false)}}
 function goSection(id:string){buzz();setTab('overview');setTimeout(()=>{document.getElementById(id)?.scrollIntoView({behavior:'smooth',block:'start'})},80)}
 async function createDraft(){buzz();if(!active)return;setBusy(true);setError('');try{await api.createPost(active.id,{title:newTitle,text:newText,channel_id:draftChannel});setNewTitle('');setNewText('');setDraftChannel(null);await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка создания черновика')}finally{setBusy(false)}}
 async function actPost(id:number,kind:'submit'|'approve'|'changes'|'schedule'|'now'|'cancel'){buzz();if(!active)return;setBusy(true);setError('');try{const w=active.id;if(kind==='submit')await api.submitPost(w,id);if(kind==='approve')await api.approvePost(w,id);if(kind==='changes')await api.requestChanges(w,id);if(kind==='schedule')await api.schedulePost(w,id,new Date(Date.now()+3600000).toISOString());if(kind==='now')await api.publishNow(w,id);if(kind==='cancel')await api.cancelPost(w,id);await load();if(kind==='now')setTimeout(()=>{load()},5000)}catch(e){setError(e instanceof Error?e.message:'Ошибка операции')}finally{setBusy(false)}}
 const canManage=active?.role==='owner'||active?.role==='admin'
 const canReview=active?.role==='owner'||active?.role==='admin'||active?.role==='editor'
 const canSchedule=canReview||active?.role==='ad_manager'
 const hint=error?errorHint(error):''
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
    <section className="panel"><div className="panel-title"><h2>Новый черновик</h2><FileText size={20}/></div>
     <input placeholder="Заголовок" value={newTitle} onChange={e=>setNewTitle(e.target.value)} style={{width:'100%',padding:12,borderRadius:12,border:'1px solid #445',background:'#111722',color:'white',margin:'12px 0 10px'}}/>
     <textarea placeholder="Текст (поддерживается Telegram HTML: <b>, <i>, <a href=...>)" value={newText} onChange={e=>setNewText(e.target.value)} rows={4} style={{width:'100%',padding:12,borderRadius:12,border:'1px solid #445',background:'#111722',color:'white',resize:'vertical'}}/>
     <div style={{display:'flex',gap:10,alignItems:'center',margin:'12px 0'}}>
      <select value={draftChannel??''} onChange={e=>setDraftChannel(e.target.value?Number(e.target.value):null)} style={{flex:1,padding:12,borderRadius:12,border:'1px solid #445',background:'#111722',color:'white'}}>
       <option value="">— без канала —</option>
       {channels.map(c=><option key={c.id} value={c.id}>{c.title}</option>)}
      </select>
      <button onClick={createDraft} disabled={busy||!newTitle.trim()}><CirclePlus size={18}/> Черновик</button>
     </div>
    </section>
    <section className="panel" style={{marginTop:14}}><div className="panel-title"><h2>Публикации</h2><Clock size={20}/></div>
     {posts.length===0?<div className="empty"><p>Пока нет публикаций. Создайте первый черновик выше.</p></div>:posts.map(p=><article key={p.id} style={{padding:'14px 0',borderBottom:'1px solid #252b36'}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:10}}>
       <strong style={{fontSize:14}}>{p.title||'(без заголовка)'}</strong>
       <span className={"status status-"+p.status}>{STATUS_LABEL[p.status]||p.status}</span>
      </div>
      <p style={{color:'#8d96a8',fontSize:12,margin:'6px 0 0'}}>
       {p.channel_title||'без канала'}
       {p.scheduled_at?` · ${new Date(p.scheduled_at).toLocaleString('ru-RU',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})}`:''}
       {p.author_username?` · @${p.author_username}`:''}
      </p>
      <div style={{display:'flex',gap:8,flexWrap:'wrap',marginTop:10}}>
       {['draft','in_progress','idea','changes_requested'].includes(p.status)&&<button onClick={()=>actPost(p.id,'submit')} disabled={busy}><Send size={14}/> На согласование</button>}
       {p.status==='review'&&canReview&&<><button onClick={()=>actPost(p.id,'approve')} disabled={busy}>✓ Одобрить</button><button onClick={()=>actPost(p.id,'changes')} disabled={busy}>Правки</button></>}
       {p.status==='approved'&&canSchedule&&<><button onClick={()=>actPost(p.id,'now')} disabled={busy}><Send size={14}/> Опубликовать сейчас</button><button onClick={()=>actPost(p.id,'schedule')} disabled={busy}>⏱ +1 час</button></>}
       {p.status==='scheduled'&&canSchedule&&<button onClick={()=>actPost(p.id,'now')} disabled={busy}><Send size={14}/> Опубликовать сейчас</button>}
       {p.status==='failed'&&canSchedule&&<button onClick={()=>actPost(p.id,'now')} disabled={busy}><Send size={14}/> Повторить публикацию</button>}
       {p.status==='cancelled'&&canSchedule&&<button onClick={()=>actPost(p.id,'now')} disabled={busy}><Send size={14}/> Возобновить</button>}
       {p.status==='failed'&&p.last_error&&<p style={{color:'#ff9b9b',fontSize:11,marginTop:8,width:'100%'}}>Причина: {p.last_error}</p>}
       {!['published','cancelled','publishing'].includes(p.status)&&<button onClick={()=>actPost(p.id,'cancel')} disabled={busy} style={{opacity:.7}}>Отменить</button>}
      </div>
     </article>)}
    </section>
   </>}
  </>}

  {tab==='create'&&<section className="panel"><div className="panel-title"><h2>Создать</h2><CirclePlus size={20}/></div>
   {active?<>
    <button className="invite-btn" onClick={()=>{buzz();setTab('calendar')}}><FileText size={15}/> Новая публикация</button>
    <button className="invite-btn" disabled style={{opacity:.5}}><Megaphone size={15}/> Рекламный слот (Этап C)</button>
    <div style={{margin:'18px 0 10px'}}><strong>Новое рабочее пространство</strong></div>
    <input value={name} onChange={e=>setName(e.target.value)} style={{width:'100%',padding:13,borderRadius:12,border:'1px solid #445',background:'#111722',color:'white',marginBottom:12}}/>
    <button onClick={create}><CirclePlus size={19}/> Создать пространство</button>
   </>:<>
    <p style={{color:'#8d96a8',fontSize:14}}>Создайте рабочее пространство, чтобы начать работу.</p>
    <input value={name} onChange={e=>setName(e.target.value)} style={{width:'100%',padding:13,borderRadius:12,border:'1px solid #445',background:'#111722',color:'white',marginBottom:12}}/>
    <button onClick={create}><CirclePlus size={19}/> Создать</button>
   </>}
  </section>}

  {tab==='ads'&&<section className="panel"><div className="panel-title"><h2>Реклама</h2><Megaphone size={20}/></div><div className="empty"><div className="empty-icon"><Wallet/></div><h3>Рекламный календарь — Этап C</h3><p>Здесь будут рекламодатели, бронирования слотов, ERID и оплаты.</p></div></section>}

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
