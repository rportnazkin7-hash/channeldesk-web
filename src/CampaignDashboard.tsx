import { useEffect, useMemo, useState } from 'react'
import { FileText, Send, Trash2 } from 'lucide-react'
import { api, type Booking, type Post, type TrackingLink } from './api'

type Props = {
  workspaceId: number
  bookings: Booking[]
  posts: Post[]
  onOpenPost: (postId: number) => void
  onCreateReport: (advertiserId: number) => void
  onDeleteTelegram: (postId: number) => void
}

const STATUS: Record<string, string> = { requested: 'Заявка', confirmed: 'Подтверждено', active: 'Активна', done: 'Выполнено', cancelled: 'Отменено', overdue: 'Просрочено' }
const PAYMENT: Record<string, string> = { unpaid: 'Не оплачено', partially_paid: 'Частично оплачено', paid: 'Оплачено' }
const FORMAT: Record<string, string> = { post: 'Пост', mention: 'Упоминание', repost: 'Репост', other: 'Размещение' }

function formatDate(value: string | null): string {
  if (!value) return '—'
  try { return new Date(value).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) } catch { return value }
}

function money(value: number, currency: string): string {
  return `${Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ${currency || 'RUB'}`
}

export default function CampaignDashboard({ workspaceId, bookings, posts, onOpenPost, onCreateReport, onDeleteTelegram }: Props) {
  const [selectedId, setSelectedId] = useState<number | null>(bookings[0]?.id || null)
  const [links, setLinks] = useState<TrackingLink[]>([])
  const [loadingLinks, setLoadingLinks] = useState(false)
  const selected = bookings.find(booking => booking.id === selectedId) || bookings[0] || null
  const post = selected?.post_id ? posts.find(item => item.id === selected.post_id) || null : null
  const campaignLinks = useMemo(() => selected ? links.filter(link => link.booking_id === selected.id) : [], [links, selected?.id])
  const clicks = campaignLinks.reduce((total, link) => total + Number(link.clicks || 0), 0)

  useEffect(() => {
    if (!selected && bookings.length) setSelectedId(bookings[0].id)
  }, [bookings, selected])

  useEffect(() => {
    let alive = true
    setLoadingLinks(true)
    api.trackingLinks(workspaceId).then(value => { if (alive) setLinks(value) }).catch(() => { if (alive) setLinks([]) }).finally(() => { if (alive) setLoadingLinks(false) })
    return () => { alive = false }
  }, [workspaceId])

  if (!selected) return <section className="panel campaign-dashboard"><div className="panel-title"><h2>Дашборд кампании</h2><FileText size={20}/></div><div className="empty"><p>Создайте рекламную бронь — и здесь появится вся кампания целиком.</p></div></section>

  const paymentDone = selected.payment_status === 'paid'
  const published = post?.status === 'published'
  const postReady = !!post?.text?.trim() && !post.text.startsWith('Рекламный пост:')
  const steps = [
    { label: 'Бронь', done: true },
    { label: 'Пост', done: postReady },
    { label: 'Оплата', done: paymentDone },
    { label: 'Публикация', done: published },
    { label: 'Отчёт', done: false },
  ]
  const currentStep = steps.findIndex(step => !step.done)

  return <section className="panel campaign-dashboard">
    <div className="campaign-dashboard-head"><div><span className="eyebrow">ЦЕНТР КАМПАНИИ</span><h2>Дашборд кампании</h2></div><FileText size={20}/></div>
    <select className="field campaign-dashboard-select" value={selected.id} onChange={event => setSelectedId(Number(event.target.value))}>{bookings.map(booking => <option key={booking.id} value={booking.id}>#{booking.id} · {booking.advertiser_name || `Рекламодатель #${booking.advertiser_id}`}</option>)}</select>
    <div className="campaign-dashboard-title"><div><strong>{selected.advertiser_name || `Рекламодатель #${selected.advertiser_id}`}</strong><span>{selected.channel_title || 'Канал не указан'} · {FORMAT[selected.format] || selected.format}</span></div><span className={`status status-${selected.status}`}>{STATUS[selected.status] || selected.status}</span></div>
    <div className="campaign-dashboard-metrics"><div><span>Стоимость</span><b>{money(selected.cost, selected.currency)}</b></div><div><span>Оплата</span><b className={paymentDone ? 'campaign-green' : 'campaign-yellow'}>{PAYMENT[selected.payment_status] || selected.payment_status}</b></div><div><span>Переходы</span><b className="campaign-blue">{clicks.toLocaleString('ru-RU')}</b></div></div>
    <div className="campaign-dashboard-steps">{steps.map((step,index) => <span className={step.done ? 'done' : index === currentStep ? 'current' : ''} key={step.label}>{step.done ? '✓ ' : ''}{step.label}</span>)}</div>
    <div className="campaign-dashboard-card"><div className="campaign-dashboard-card-head"><strong>Рекламный пост</strong><span>{post ? (post.status === 'published' ? 'Опубликован' : STATUS[post.status] || post.status) : 'Не создан'}</span></div>{post ? <><h3>{post.title || '(без заголовка)'}</h3><p>{post.text || 'Текст пока не добавлен.'}</p>{post.buttons?.length ? <div className="campaign-dashboard-chips">{post.buttons.flat().map((button,index)=><span key={index}>🔗 {button.text}</span>)}</div> : null}</> : <div className="campaign-dashboard-empty">Пост появится после создания брони.</div>}</div>
    <div className="campaign-dashboard-card"><div className="campaign-dashboard-card-head"><strong>Период размещения</strong><span>7 дней</span></div><p>{formatDate(selected.publish_at)} — {formatDate(selected.delete_at)}</p></div>
    <div className="campaign-dashboard-card"><div className="campaign-dashboard-card-head"><strong>Ссылки кампании</strong><span>{loadingLinks ? 'загрузка…' : `${campaignLinks.length} шт.`}</span></div>{campaignLinks.length ? campaignLinks.map(link => <div className="campaign-dashboard-link" key={link.id}><div><strong>{link.name}</strong><span>{link.target_url}</span></div><b>{Number(link.clicks || 0).toLocaleString('ru-RU')} переходов</b></div>) : <div className="campaign-dashboard-empty">Ссылок пока нет.</div>}</div>
    <div className="campaign-dashboard-actions">{post&&<button className="icon-btn" onClick={()=>onOpenPost(post.id)}><FileText size={14}/> Изменить пост</button>}<button className="icon-btn" onClick={()=>onCreateReport(selected.advertiser_id)}><Send size={14}/> Отправить отчёт</button>{post?.status === 'published'&&<button className="icon-btn danger" onClick={()=>onDeleteTelegram(post.id)}><Trash2 size={14}/> Удалить из Telegram</button>}</div>
  </section>
}
