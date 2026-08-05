import { useMemo, useState } from 'react'
import { CalendarDays, ChevronLeft, ChevronRight } from 'lucide-react'
import type { Booking, Channel } from './api'

type Props = { bookings: Booking[]; channels: Channel[] }

const MONTHS = ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь']
const STATUS: Record<string,string> = { requested:'Заявка', confirmed:'Подтверждено', active:'Активно', done:'Выполнено', cancelled:'Отменено', overdue:'Просрочено' }

function dayKey(date: Date){ return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}` }
function monthGrid(year:number, month:number):(Date|null)[]{const first=new Date(year,month,1);const start=(first.getDay()+6)%7;const count=new Date(year,month+1,0).getDate();const cells:(Date|null)[]=[];for(let i=0;i<start;i++)cells.push(null);for(let day=1;day<=count;day++)cells.push(new Date(year,month,day));return cells}
function atDay(booking:Booking, day:Date){if(!booking.publish_at)return false;const start=new Date(booking.publish_at);const end=booking.delete_at?new Date(booking.delete_at):new Date(start.getTime()+7*86400000);const current=new Date(day.getFullYear(),day.getMonth(),day.getDate());const from=new Date(start.getFullYear(),start.getMonth(),start.getDate());const to=new Date(end.getFullYear(),end.getMonth(),end.getDate());return current>=from&&current<=to}
function fmt(value:string|null){if(!value)return '—';try{return new Date(value).toLocaleString('ru-RU',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})}catch{return value}}

export default function AdCalendar({bookings,channels}:Props){
 const now=new Date();const [year,setYear]=useState(now.getFullYear());const [month,setMonth]=useState(now.getMonth());const [selected,setSelected]=useState<Date|null>(null);const [channelId,setChannelId]=useState<number|null>(null)
 const filtered=bookings.filter(b=>channelId==null||b.channel_id===channelId)
 const cells=monthGrid(year,month)
 const selectedBookings=selected?filtered.filter(b=>atDay(b,selected)):[]
 const today=dayKey(new Date())
 const channelName=(id:number|null)=>channels.find(c=>c.id===id)?.title||'Канал не указан'
 const occupiedCount=useMemo(()=>cells.filter((day):day is Date=>!!day&&filtered.some(b=>atDay(b,day))).length,[cells,filtered])
 function shift(delta:number){const next=new Date(year,month+delta,1);setYear(next.getFullYear());setMonth(next.getMonth())}
 return <section className="panel ad-calendar">
  <div className="panel-title"><div className="ad-calendar-title"><CalendarDays size={18}/><h2>Рекламный календарь</h2></div><span className="calendar-count">{occupiedCount}</span></div>
  <p className="ad-calendar-note">Показывает только занятые рекламные дни. Редактирование, оплата и посты находятся в дашборде и во вкладке «Посты».</p>
  <select className="field" value={channelId??''} onChange={e=>setChannelId(e.target.value?Number(e.target.value):null)}><option value="">Все каналы</option>{channels.map(c=><option key={c.id} value={c.id}>{c.title}</option>)}</select>
  <div className="cal-head" style={{marginTop:12}}><button className="icon-btn" onClick={()=>shift(-1)}><ChevronLeft size={17}/></button><strong>{MONTHS[month]} {year}</strong><button className="icon-btn" onClick={()=>shift(1)}><ChevronRight size={17}/></button></div>
  <div className="ad-calendar-grid">{['Пн','Вт','Ср','Чт','Пт','Сб','Вс'].map(day=><div className="cal-dow" key={day}>{day}</div>)}{cells.map((day,index)=>day?<button key={index} className={'ad-calendar-day'+(filtered.some(b=>atDay(b,day))?' occupied':'')+(dayKey(day)===today?' today':'')+(selected&&dayKey(day)===dayKey(selected)?' selected':'')} onClick={()=>setSelected(selected&&dayKey(selected)===dayKey(day)?null:day)}>{day.getDate()}{filtered.some(b=>atDay(b,day))&&<i/>}</button>:<div className="ad-calendar-day empty" key={index}/>)}</div>
  <div className="ad-calendar-legend"><span><i className="legend-dot occupied-dot"/> занято</span><span><i className="legend-dot today-dot"/> сегодня</span></div>
  {selected&&<div className="ad-calendar-day-list"><div className="panel-title"><strong>{selected.getDate()} {MONTHS[selected.getMonth()]}</strong><span>{selectedBookings.length} размещ.</span></div>{selectedBookings.length?selectedBookings.map(b=><article className="ad-calendar-booking" key={b.id}><div><strong>{b.advertiser_name||`Бронь #${b.id}`}</strong><span>{channelName(b.channel_id)} · {fmt(b.publish_at)} — {fmt(b.delete_at)}</span></div><span className={'status status-'+b.status}>{STATUS[b.status]||b.status}</span></article>):<p className="ad-calendar-empty">На этот день размещений нет.</p>}</div>}
 </section>
}
