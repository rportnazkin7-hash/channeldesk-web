import { useEffect, useMemo, useState } from 'react'
import { BarChart3, RefreshCw } from 'lucide-react'
import { api, type AnalyticsOverview, type Channel } from './api'

type Props = {
  workspaceId: number
  channels: Channel[]
  onBack: () => void
  onError: (message: string) => void
}

function dateValue(date: Date): string {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 10)
}

function daysAgo(days: number): string {
  const date = new Date()
  date.setDate(date.getDate() - days)
  return dateValue(date)
}

function formattedNumber(value: number): string {
  return Number(value || 0).toLocaleString('ru-RU')
}

function shortDate(value: string): string {
  try {
    return new Date(`${value}T12:00:00`).toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' })
  } catch {
    return value
  }
}

export default function Analytics({ workspaceId, channels, onBack, onError }: Props) {
  const [fromDate, setFromDate] = useState(daysAgo(29))
  const [toDate, setToDate] = useState(dateValue(new Date()))
  const [channelFilter, setChannelFilter] = useState<number | null>(null)
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null)
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true)
    try {
      const data = await api.analytics(workspaceId, {
        from_date: fromDate,
        to_date: toDate,
        channel_id: channelFilter || undefined,
      })
      setOverview(data)
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Не удалось загрузить аналитику')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [workspaceId, fromDate, toDate, channelFilter])

  const summary = overview?.summary
  const series = summary?.series || []
  const chartMax = useMemo(() => Math.max(1, ...series.flatMap(point => [point.posts_count, point.reactions])), [series])
  const channelName = (id: number) => channels.find(channel => channel.id === id)?.title || `Канал #${id}`

  return <section className="panel analytics-panel">
    <div className="analytics-heading">
      <div className="analytics-heading-title"><BarChart3 size={18} /><h2>Аналитика каналов</h2></div>
      <button className="icon-btn" onClick={() => void load()} disabled={loading} title="Обновить"><RefreshCw size={14} /></button>
    </div>
    <p className="analytics-note">Здесь только автоматические данные, которые Telegram отдаёт нашему боту. Никаких ручных таблиц: бот сам считает новые посты, реакции и подписчиков.</p>
    <button className="back-btn" onClick={onBack}>← Назад</button>

    <div className="analytics-filters">
      <label className="analytics-control"><span>Период от</span><input className="field" type="date" value={fromDate} onChange={event => setFromDate(event.target.value)} /></label>
      <label className="analytics-control"><span>Период до</span><input className="field" type="date" value={toDate} onChange={event => setToDate(event.target.value)} /></label>
      <label className="analytics-control analytics-filter-channel"><span>Канал</span><select className="field" value={channelFilter ?? ''} onChange={event => setChannelFilter(event.target.value ? Number(event.target.value) : null)}><option value="">Все каналы</option>{channels.map(channel => <option key={channel.id} value={channel.id}>{channel.title}</option>)}</select></label>
    </div>

    {loading && !overview ? <div className="empty"><p>Собираю данные от Telegram. Бот на проводе.</p></div> : <>
      <div className="analytics-kpis">
        <article className="analytics-kpi"><span>Подписчики</span><strong>{formattedNumber(summary?.subscribers || 0)}</strong></article>
        <article className="analytics-kpi"><span>Новые посты</span><strong>{formattedNumber(summary?.posts_count || 0)}</strong></article>
        <article className="analytics-kpi"><span>Реакции</span><strong>{formattedNumber(summary?.reactions || 0)}</strong></article>
        <article className="analytics-kpi"><span>Переходы</span><strong>{formattedNumber(summary?.clicks || 0)}</strong></article>
      </div>

      <section className="analytics-card analytics-availability-card">
        <div className="analytics-section-heading"><div><strong>Что умеет Bot API</strong><span>Данные обновляются автоматически в фоне</span></div><span className="analytics-source-badge">Bot API</span></div>
        <div className="analytics-availability-grid">
          {(summary?.available || []).map(item => <span className="analytics-available" key={item}>✓ {item === 'subscribers' ? 'подписчики' : item === 'posts_count' ? 'новые посты' : 'реакции'}</span>)}
          {(summary?.unavailable || []).map(item => <span className="analytics-unavailable" key={item}>— {item === 'views' ? 'просмотры' : item === 'reach' ? 'охват' : 'пересылки'} недоступны</span>)}
        </div>
      </section>

      <section className="analytics-card analytics-chart-card">
        <div className="analytics-section-heading"><div><strong>Активность по дням</strong><span>Новые посты и реакции, полученные ботом</span></div><span className="analytics-legend"><i className="legend-income" /> посты <i className="legend-expense" /> реакции</span></div>
        <div className={`analytics-chart-scroll${series.length === 0 ? ' is-empty' : ''}`}>
          {series.length === 0 ? <div className="analytics-empty-chart">Данных за период пока нет</div> : <div className="analytics-chart-columns">{series.map(point => <div className="analytics-chart-column" key={point.date} title={`${point.date}: ${point.posts_count} постов, ${point.reactions} реакций`}>
            <div className="analytics-chart-bars"><i className="trend-income" style={{ height: `${Math.max(point.posts_count ? 5 : 0, point.posts_count / chartMax * 100)}%` }} /><i className="trend-expense" style={{ height: `${Math.max(point.reactions ? 5 : 0, point.reactions / chartMax * 100)}%` }} /></div>
            <span>{shortDate(point.date)}</span>
          </div>)}</div>}
        </div>
      </section>

      <section className="analytics-card analytics-list-card">
        <div className="analytics-section-heading"><div><strong>Дневные снимки</strong><span>Последние данные, пришедшие от Telegram</span></div><span className="analytics-count">{overview?.metrics.length || 0}</span></div>
        {(overview?.metrics || []).length === 0 ? <div className="empty"><p>Telegram ещё не прислал данных. После следующего поста или фонового снимка они появятся здесь.</p></div> : overview?.metrics.slice().reverse().slice(0, 30).map(row => <article className="analytics-row" key={row.id}>
          <div className="analytics-row-main"><strong>{shortDate(row.metric_date)} · {row.channel_title || channelName(row.channel_id)}</strong><span>{formattedNumber(row.subscribers)} подписчиков · {formattedNumber(row.posts_count)} постов · {formattedNumber(row.reactions)} реакций</span></div>
          <span className="status status-in_progress">Bot API</span>
        </article>)}
      </section>

      <section className="analytics-card analytics-list-card">
        <div className="analytics-section-heading"><div><strong>Ссылки кампаний</strong><span>Переходы считаются автоматически через ChannelDesk</span></div><span className="analytics-count">{overview?.links.length || 0}</span></div>
        {(overview?.links || []).length === 0 ? <div className="empty"><p>Ссылок пока нет. Создайте первую в разделе «Клиенты».</p></div> : overview?.links.map(link => <article className="analytics-row" key={link.id}>
          <div className="analytics-row-main"><strong>{link.name}{link.advertiser_name ? ` · ${link.advertiser_name}` : ''}</strong><span>{link.channel_title || channelName(link.channel_id)} · {formattedNumber(link.clicks)} переходов · {link.target_url}</span></div>
          <span className="status status-in_progress">{formattedNumber(link.clicks)}</span>
        </article>)}
      </section>
    </>}
  </section>
}
