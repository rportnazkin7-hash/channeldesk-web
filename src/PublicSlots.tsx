import { useEffect, useMemo, useState } from 'react'
import { CalendarDays, CheckCircle2, Send, XCircle } from 'lucide-react'

type Busy = { publish_at: string; delete_at: string | null; status: string }
type Page = { title: string; description: string; default_cost: number; currency: string; channel_title: string; username: string | null; busy: Busy[]; formats: string[] }

const FORMAT: Record<string,string> = { post:'Пост', mention:'Упоминание', repost:'Репост' }
function dateValue(date: Date){const local=new Date(date.getTime()-date.getTimezoneOffset()*60000);return local.toISOString().slice(0,10)}
function money(value:number,currency:string){return `${Number(value||0).toLocaleString('ru-RU')} ${currency}`}
function busyOnDate(busy:Busy[], value:string){const date=new Date(`${value}T12:00:00`);return busy.some(item=>{const start=new Date(item.publish_at);const end=item.delete_at?new Date(item.delete_at):new Date(start.getTime()+7*86400000);return date>=new Date(start.getFullYear(),start.getMonth(),start.getDate())&&date<=new Date(end.getFullYear(),end.getMonth(),end.getDate())})}

export default function PublicSlots({token}:{token:string}){
 const [page,setPage]=useState<Page|null>(null),[loading,setLoading]=useState(true),[error,setError]=useState(''),[success,setSuccess]=useState('')
 const today=dateValue(new Date());const [startDate,setStartDate]=useState(today),[endDate,setEndDate]=useState(today),[format,setFormat]=useState('post'),[name,setName]=useState(''),[telegram,setTelegram]=useState(''),[email,setEmail]=useState(''),[targetUrl,setTargetUrl]=useState(''),[comment,setComment]=useState(''),[sending,setSending]=useState(false)
 useEffect(()=>{fetch(`/api/public/slots/${encodeURIComponent(token)}`).then(async r=>{const b=await r.json().catch(()=>({}));if(!r.ok)throw new Error(b.detail||`Ошибка ${r.status}`);return b as Page}).then(setPage).catch(e=>setError(e instanceof Error?e.message:'Витрина недоступна')).finally(()=>setLoading(false))},[token])
 const occupied=useMemo(()=>page?.busy.filter(item=>item.status!=='cancelled'&&item.status!=='done')||[],[page])
 const rangeBusy=page?busyOnDate(occupied,startDate)||busyOnDate(occupied,endDate):false
 async function submit(){setError('');setSuccess('');if(!name.trim()||!startDate||!endDate){setError('Заполните имя и период размещения');return}if(new Date(`${endDate}T12:00:00`)<new Date(`${startDate}T12:00:00`)){setError('Дата окончания раньше даты начала');return}if(rangeBusy){setError('Выбранный период уже занят. Выберите другие даты.');return}setSending(true);try{const r=await fetch(`/api/public/slots/${encodeURIComponent(token)}/request`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({contact_name:name,contact_telegram:telegram,contact_email:email,target_url:targetUrl,format,start_date:startDate,end_date:endDate,comment})});const b=await r.json().catch(()=>({}));if(!r.ok)throw new Error(b.detail||`Ошибка ${r.status}`);setSuccess(b.message||'Заявка отправлена');setName('');setTelegram('');setEmail('');setTargetUrl('');setComment('')}catch(e){setError(e instanceof Error?e.message:'Не удалось отправить заявку')}finally{setSending(false)}}
 if(loading)return <main className="public-report-page"><div className="public-report-state">Загружаю свободные слоты…</div></main>
 if(error&&!page)return <main className="public-report-page"><div className="public-report-state"><XCircle size={30}/><strong>Витрина недоступна</strong><span>{error}</span></div></main>
 if(!page)return null
 return <main className="public-report-page"><section className="public-report-shell slots-shell">
  <div className="public-report-brand"><span className="public-report-logo">CD</span><span>ChannelDesk</span></div>
  <div className="public-report-heading"><div><span className="public-report-eyebrow">РЕКЛАМНЫЕ РАЗМЕЩЕНИЯ</span><h1>{page.channel_title}</h1></div><CalendarDays size={24}/></div>
  <p className="public-report-muted">{page.description||'Выберите свободный период и отправьте заявку на размещение.'}</p>
  <div className="slots-price"><span>Базовая стоимость</span><strong>{money(page.default_cost,page.currency)}</strong></div>
  {success&&<div className="public-slot-success"><CheckCircle2 size={18}/><span>{success}</span></div>}
  {error&&<div className="public-slot-error"><XCircle size={16}/><span>{error}</span></div>}
  <section className="public-slot-form"><h2>Оставить заявку</h2>
   <label>Формат<select value={format} onChange={e=>setFormat(e.target.value)}>{page.formats.map(item=><option key={item} value={item}>{FORMAT[item]||item}</option>)}</select></label>
   <div className="slots-date-row"><label>Начало<input type="date" value={startDate} onChange={e=>setStartDate(e.target.value)}/></label><label>Окончание<input type="date" value={endDate} onChange={e=>setEndDate(e.target.value)}/></label></div>
   {rangeBusy&&<div className="public-slot-error"><span>Этот период пересекается с занятым размещением.</span></div>}
   <label>Имя или компания<input placeholder="ООО «Ромашка»" value={name} onChange={e=>setName(e.target.value)}/></label>
   <label>Telegram<input placeholder="@username" value={telegram} onChange={e=>setTelegram(e.target.value)}/></label>
   <label>Email<input type="email" placeholder="mail@example.com" value={email} onChange={e=>setEmail(e.target.value)}/></label>
   <label>Ссылка на продукт<input type="url" placeholder="https://example.com" value={targetUrl} onChange={e=>setTargetUrl(e.target.value)}/></label>
   <label>Комментарий<textarea placeholder="Что рекламируем и когда удобно связаться?" value={comment} onChange={e=>setComment(e.target.value)}/></label>
   <button className="public-slot-submit" onClick={()=>void submit()} disabled={sending||rangeBusy}><Send size={15}/>{sending?'Отправляю…':'Отправить заявку'}</button>
  </section>
  {occupied.length>0&&<section className="slots-busy"><h2>Уже занятые периоды</h2>{occupied.slice(0,10).map((item,index)=><div key={index}>{new Date(item.publish_at).toLocaleDateString('ru-RU')} — {item.delete_at?new Date(item.delete_at).toLocaleDateString('ru-RU'):'дата окончания не указана'}</div>)}</section>}
  <p className="public-report-footer">Заявка не подтверждает размещение автоматически. Менеджер свяжется с вами.</p>
 </section></main>
}
