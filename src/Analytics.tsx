import { useEffect, useMemo, useState } from 'react'
import { BarChart3, Link2, Plus, RefreshCw, Trash2, TrendingUp } from 'lucide-react'
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

function numberValue(value: string): number {
  return Math.max(0, Number.parseInt(value || '0', 10) || 0)
}

function shortDate(value: string): string {
  try {
    return new Date(`${value}T12:00:00`).toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' })
  } catch {
    return value
  }
}

function metricFormDefaults(channelId: number | null) {
  return { channel_id: channelId || 0, metric_date: dateValue(new Date()), subscribers: '', views: '', reach: '', reactions: '', forwards: '', posts_count: '', notes: '' }
}

export default function Analytics({ workspaceId, channels, onBack, onError }: Props) {
  const firstChannel = channels[0]?.id || null
  const [fromDate, setFromDate] = useState(daysAgo(29))
  const [toDate, setToDate] = useState(dateValue(new Date()))
  const [channelFilter, setChannelFilter] = useState<number | null>(null)
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [savingMetric, setSavingMetric] = useState(false)
  const [savingLink, setSavingLink] = useState(false)
  const [metric, setMetric] = useState(() => metricFormDefaults(firstChannel))
  const [link, setLink] = useState({ channel_id: firstChannel || 0, name: '', url: '', clicks: '', conversions: '', notes: '' })

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
    if (metric.channel_id === 0 && firstChannel) setMetric(current => ({ ...current, channel_id: firstChannel }))
    if (link.channel_id === 0 && firstChannel) setLink(current => ({ ...current, channel_id: firstChannel }))
  }, [firstChannel])

  useEffect(() => {
    void load()
  }, [workspaceId, fromDate, toDate, channelFilter])

  async function saveMetric() {
    if (!metric.channel_id) {
      onError('Выберите канал для метрики')
      return
    }
    setSavingMetric(true)
    try {
      await api.createMetric(workspaceId, {
        channel_id: metric.channel_id,
        metric_date: metric.metric_date,
        subscribers: numberValue(metric.subscribers),
        views: numberValue(metric.views),
        reach: numberValue(metric.reach),
        reactions: numberValue(metric.reactions),
        forwards: numberValue(metric.forwards),
        posts_count: numberValue(metric.posts_count),
        notes: metric.notes.trim(),
      })
      setMetric(current => ({ ...current, subscribers: '', views: '', reach: '', reactions: '', forwards: '', posts_count: '', notes: '' }))
      await load()
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Не удалось сохранить метрику')
    } finally {
      setSavingMetric(false)
    }
  }

  async function saveLink() {
    if (!link.channel_id || !link.name.trim() || !link.url.trim()) {
      onError('Заполните канал, название и ссылку')
      return
    }
    setSavingLink(true)
    try {
      await api.createAnalyticsLink(workspaceId, {
        channel_id: link.channel_id,
        name: link.name.trim(),
        url: link.url.trim(),
        clicks: numberValue(link.clicks),
        conversions: numberValue(link.conversions),
        notes: link.notes.trim(),
      })
      setLink(current => ({ ...current, name: '', url: '', clicks: '', conversions: '', notes: '' }))
      await load()
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Не удалось сохранить ссылку')
    } finally {
      setSavingLink(false)
    }
  }

  async function removeLink(id: number) {
    try {
      await api.deleteAnalyticsLink(workspaceId, id)
      await load()
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Не удалось удалить ссылку')
    }
  }

  const summary = overview?.summary
  const series = summary?.series || []
  const chartMax = useMemo(() => Math.max(1, ...series.flatMap(point => [point.views, point.reach])), [series])
  const channelName = (id: number) => channels.find(channel => channel.id === id)?.title || `Канал #${id}`
  const field = (key: keyof typeof metric, placeholder: string) => <input className="field" type="number" min="0" placeholder={placeholder} value={String(metric[key] ?? '')} onChange={event => setMetric(current => ({ ...current, [key]: event.target.value }))} />

  return <section className="panel analytics-panel">
    <div className="panel-title"><h2><BarChart3 size={17} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Аналитика каналов</h2><button className="icon-btn" onClick={() => void load()} disabled={loading}><RefreshCw size={14} /></button></div>
    <p className="analytics-note">Данные вводятся вручную или из доступных событий Bot API. Полной нативной статистики Telegram обычному боту не выдаёт — он тоже не волшебник.</p>
    <button className="icon-btn" onClick={onBack} style={{ margin: '8px 0 10px' }}>← Назад</button>

    <div className="analytics-filters">
      <input className="field" type="date" value={fromDate} onChange={event => setFromDate(event.target.value)} />
      <input className="field" type="date" value={toDate} onChange={event => setToDate(event.target.value)} />
      <select className="field" value={channelFilter ?? ''} onChange={event => setChannelFilter(event.target.value ? Number(event.target.value) : null)}>
        <option value="">Все каналы</option>
        {channels.map(channel => <option key={channel.id} value={channel.id}>{channel.title}</option>)}
      </select>
    </div>

    {loading && !overview ? <div className="empty"><p>Собираю цифры. Они пока не разбежались.</p></div> : <>
      <div className="fin-cards analytics-cards">
        <div><span>Просмотры</span><strong>{(summary?.views || 0).toLocaleString('ru-RU')}</strong></div>
        <div><span>Охват</span><strong>{(summary?.reach || 0).toLocaleString('ru-RU')}</strong></div>
        <div><span>Подписчики</span><strong>{(summary?.subscribers || 0).toLocaleString('ru-RU')}</strong></div>
        <div><span>Переходы</span><strong>{(summary?.clicks || 0).toLocaleString('ru-RU')}</strong></div>
      </div>

      <div className="trend-card analytics-chart">
        <div className="panel-title"><strong>Динамика</strong><span className="trend-legend"><i className="legend-income" /> просмотры <i className="legend-expense" /> охват</span></div>
        <div className="trend-chart">
          {series.length === 0 ? <div className="analytics-empty-chart">Нет данных за период</div> : series.map(point => <div className="trend-column" key={point.date} title={`${point.date}: ${point.views.toLocaleString('ru-RU')} просмотров, ${point.reach.toLocaleString('ru-RU')} охвата`}>
            <div className="trend-bars"><i className="trend-income" style={{ height: `${Math.max(point.views ? 5 : 0, point.views / chartMax * 100)}%` }} /><i className="trend-expense" style={{ height: `${Math.max(point.reach ? 5 : 0, point.reach / chartMax * 100)}%` }} /></div>
            <span>{shortDate(point.date)}</span>
          </div>)}
        </div>
      </div>

      <div className="analytics-form-block">
        <div className="panel-title"><strong>Добавить дневную метрику</strong><TrendingUp size={16} /></div>
        <div className="analytics-form-grid">
          <select className="field" value={metric.channel_id || ''} onChange={event => setMetric(current => ({ ...current, channel_id: Number(event.target.value) || 0 }))}><option value="">Канал</option>{channels.map(channel => <option key={channel.id} value={channel.id}>{channel.title}</option>)}</select>
          <input className="field" type="date" value={metric.metric_date} onChange={event => setMetric(current => ({ ...current, metric_date: event.target.value }))} />
          {field('subscribers', 'Подписчики')}{field('views', 'Просмотры')}{field('reach', 'Охват')}{field('reactions', 'Реакции')}{field('forwards', 'Пересылки')}{field('posts_count', 'Посты')}
        </div>
        <input className="field" placeholder="Заметка (необязательно)" value={metric.notes} onChange={event => setMetric(current => ({ ...current, notes: event.target.value }))} style={{ marginTop: 8 }} />
        <button className="primary-btn" onClick={() => void saveMetric()} disabled={savingMetric || !channels.length}><Plus size={16} /> {savingMetric ? 'Сохраняю…' : 'Сохранить метрику'}</button>
      </div>

      <div className="analytics-form-block">
        <div className="panel-title"><strong>Своя ссылка</strong><Link2 size={16} /></div>
        <div className="analytics-form-grid">
          <select className="field" value={link.channel_id || ''} onChange={event => setLink(current => ({ ...current, channel_id: Number(event.target.value) || 0 }))}><option value="">Канал</option>{channels.map(channel => <option key={channel.id} value={channel.id}>{channel.title}</option>)}</select>
          <input className="field" placeholder="Название ссылки" value={link.name} onChange={event => setLink(current => ({ ...current, name: event.target.value }))} />
          <input className="field analytics-span-2" type="url" placeholder="https://t.me/..." value={link.url} onChange={event => setLink(current => ({ ...current, url: event.target.value }))} />
          <input className="field" type="number" min="0" placeholder="Переходы" value={link.clicks} onChange={event => setLink(current => ({ ...current, clicks: event.target.value }))} />
          <input className="field" type="number" min="0" placeholder="Конверсии" value={link.conversions} onChange={event => setLink(current => ({ ...current, conversions: event.target.value }))} />
        </div>
        <input className="field" placeholder="Заметка (необязательно)" value={link.notes} onChange={event => setLink(current => ({ ...current, notes: event.target.value }))} style={{ marginTop: 8 }} />
        <button className="primary-btn" onClick={() => void saveLink()} disabled={savingLink || !channels.length}><Plus size={16} /> {savingLink ? 'Сохраняю…' : 'Добавить ссылку'}</button>
      </div>

      <div className="analytics-list-block">
        <div className="panel-title"><strong>Метрики</strong><span>{overview?.metrics.length || 0}</span></div>
        {(overview?.metrics || []).length === 0 ? <div className="empty"><p>Метрик пока нет. Добавьте первую — статистика не кусается.</p></div> : overview?.metrics.slice().reverse().slice(0, 20).map(row => <article className="analytics-row" key={row.id}>
          <div><strong>{shortDate(row.metric_date)} · {row.channel_title || channelName(row.channel_id)}</strong><span>{row.subscribers.toLocaleString('ru-RU')} подписчиков · {row.views.toLocaleString('ru-RU')} просмотров · охват {row.reach.toLocaleString('ru-RU')}</span></div>
          <span className="status status-in_progress">{row.source === 'bot_api' ? 'Bot API' : 'вручную'}</span>
        </article>)}
      </div>

      <div className="analytics-list-block">
        <div className="panel-title"><strong>Ссылки</strong><span>{overview?.links.length || 0}</span></div>
        {(overview?.links || []).length === 0 ? <div className="empty"><p>Ссылок пока нет.</p></div> : overview?.links.map(row => <article className="analytics-row" key={row.id}>
          <div><strong>{row.name} · {row.channel_title || channelName(row.channel_id)}</strong><span><a href={row.url} target="_blank" rel="noreferrer">{row.url}</a> · {row.clicks.toLocaleString('ru-RU')} переходов · {row.conversions.toLocaleString('ru-RU')} конверсий</span></div>
          <button className="icon-btn danger" onClick={() => void removeLink(row.id)} title="Удалить"><Trash2 size={14} /></button>
        </article>)}
      </div>
    </>}
  </section>
}
