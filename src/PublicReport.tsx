import { useEffect, useState } from 'react'
import { CheckCircle2, Clock3, FileText, XCircle } from 'lucide-react'

type Booking = {
  id: number
  format: string
  cost: number
  currency: string
  status: string
  payment_status: string
  publish_at: string | null
  delete_at: string | null
  channel_title: string | null
  post_id: number | null
  post_title: string | null
  post_text: string | null
  post_status: string | null
}

type Feedback = { booking_id: number; decision: 'approved' | 'changes_requested'; comment: string; created_at: string }

type ReportLink = {
  id: number
  name: string
  target_url: string
  clicks: number
  booking_id: number
  channel_title: string | null
}

type Report = {
  advertiser_name: string
  expires_at: string
  generated_at: string
  bookings: Booking[]
  links: ReportLink[]
  feedback: Feedback[]
}

const STATUS: Record<string, string> = { requested: 'Заявка', confirmed: 'Подтверждено', active: 'Активно', done: 'Выполнено', cancelled: 'Отменено', overdue: 'Просрочено' }
const PAYMENT: Record<string, string> = { unpaid: 'Не оплачено', partially_paid: 'Частично оплачено', paid: 'Оплачено' }
const FORMAT: Record<string, string> = { post: 'Пост', mention: 'Упоминание', repost: 'Репост', other: 'Размещение' }

function formatDate(value: string | null): string {
  if (!value) return '—'
  try { return new Date(value).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) } catch { return value }
}

function money(value: number, currency: string): string {
  return `${Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ${currency || 'RUB'}`
}

export default function PublicReport({ token }: { token: string }) {
  const [report, setReport] = useState<Report | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [feedbackBusy, setFeedbackBusy] = useState(false)
  const [commentFor, setCommentFor] = useState<number | null>(null)
  const [comment, setComment] = useState('')

  async function sendFeedback(bookingId: number, decision: 'approved' | 'changes_requested') {
    if (decision === 'changes_requested' && !comment.trim()) return
    setFeedbackBusy(true)
    try {
      const response = await fetch(`/api/public/reports/${encodeURIComponent(token)}/bookings/${bookingId}/feedback`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision, comment: comment.trim() }),
      })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body.detail || `Ошибка ${response.status}`)
      setReport(current => current ? { ...current, feedback: [body, ...(current.feedback || [])] } : current)
      setCommentFor(null)
      setComment('')
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Не удалось отправить решение')
    } finally {
      setFeedbackBusy(false)
    }
  }

  useEffect(() => {
    fetch(`/api/public/reports/${encodeURIComponent(token)}`)
      .then(async response => {
        const body = await response.json().catch(() => ({}))
        if (!response.ok) throw new Error(body.detail || `Ошибка ${response.status}`)
        return body as Report
      })
      .then(setReport)
      .catch(error => setError(error instanceof Error ? error.message : 'Не удалось загрузить отчёт'))
      .finally(() => setLoading(false))
  }, [token])

  if (loading) return <main className="public-report-page"><div className="public-report-state">Загружаю отчёт…</div></main>
  if (error || !report) return <main className="public-report-page"><div className="public-report-state"><XCircle size={30} /><strong>Отчёт недоступен</strong><span>{error || 'Ссылка не найдена'}</span></div></main>

  return <main className="public-report-page">
    <section className="public-report-shell">
      <div className="public-report-brand"><span className="public-report-logo">CD</span><span>ChannelDesk</span></div>
      <div className="public-report-heading"><div><span className="public-report-eyebrow">ОТЧЁТ ПО РАЗМЕЩЕНИЯМ</span><h1>{report.advertiser_name}</h1></div><FileText size={24} /></div>
      <p className="public-report-muted">Сводка рекламных размещений и их статусов.</p>
      <div className="public-report-summary"><span><b>{report.bookings.length}</b> размещений</span><span>Обновлено {formatDate(report.generated_at)}</span></div>
      <div className="public-report-list">
        {report.bookings.length === 0 ? <div className="public-report-empty">Размещений пока нет.</div> : report.bookings.map(booking => {
          const canReview = !!booking.post_id && !!booking.post_status && !['published', 'cancelled'].includes(booking.post_status)
          const latestFeedback = (report.feedback || []).find(item => item.booking_id === booking.id)
          return <article className="public-booking" key={booking.id}>
            <div className="public-booking-head"><strong>{booking.channel_title || 'Канал не указан'}</strong><span className={`public-status status-${booking.status}`}>{STATUS[booking.status] || booking.status}</span></div>
            <div className="public-booking-meta"><span>{FORMAT[booking.format] || booking.format}</span><span>{money(booking.cost, booking.currency)}</span><span>{PAYMENT[booking.payment_status] || booking.payment_status}</span></div>
            <div className="public-booking-dates"><span><Clock3 size={13} /> {formatDate(booking.publish_at)}</span>{booking.delete_at && <span>до {formatDate(booking.delete_at)}</span>}</div>
            {booking.post_title && <div className="public-post-preview"><strong>{booking.post_title}</strong><p>{booking.post_text || 'Текст поста пока не добавлен.'}</p></div>}
            {canReview && <div className="public-feedback"><div className="public-feedback-title">Согласование поста</div>{latestFeedback && <div className={`public-feedback-state ${latestFeedback.decision}`}><CheckCircle2 size={14} /> {latestFeedback.decision === 'approved' ? 'Вы одобрили пост' : 'Запрошены правки'}{latestFeedback.comment ? `: ${latestFeedback.comment}` : ''}</div>}<div className="public-feedback-actions"><button onClick={() => void sendFeedback(booking.id, 'approved')} disabled={feedbackBusy}>Одобрить</button><button onClick={() => setCommentFor(booking.id)} disabled={feedbackBusy}>Нужны правки</button></div>{commentFor === booking.id && <div className="public-feedback-form"><textarea placeholder="Что нужно исправить?" value={comment} onChange={event => setComment(event.target.value)} /><button onClick={() => void sendFeedback(booking.id, 'changes_requested')} disabled={feedbackBusy || !comment.trim()}>Отправить правки</button></div>}</div>}
            {booking.status === 'done' && <div className="public-booking-ok"><CheckCircle2 size={14} /> Размещение завершено</div>}
          </article>
        })}
      </div>
      {report.links.length > 0 && <section className="public-report-links"><h2>Результаты кампаний</h2>{report.links.map(link => <article className="public-report-link" key={link.id}><div><strong>{link.name}</strong><span>{link.channel_title || 'Канал не указан'} · <a href={link.target_url} target="_blank" rel="noreferrer">{link.target_url}</a></span></div><b>{link.clicks.toLocaleString('ru-RU')} переходов</b></article>)}</section>}
      <p className="public-report-footer">Ссылка действительна до {formatDate(report.expires_at)}.</p>
    </section>
  </main>
}
