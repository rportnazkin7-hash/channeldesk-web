import { useEffect, useMemo, useState } from 'react'
import { BarChart3, Link2, Plus, RefreshCw, Trash2, TrendingUp } from 'lucide-react'
import { api, type AnalyticsOverview, type Channel } from './api'

type Props = {
  workspaceId: number
  channels: Channel[]
  onBack: () => void
  onError: (message: string) => void
}

type MetricNumberKey = 'subscribers' | 'views' | 'reach' | 'reactions' | 'forwards' | 'posts_count'

type MetricDraft = {
  channel_id: number
  metric_date: string
  subscribers: string
  views: string
  reach: string
  reactions: string
  forwards: string
  posts_count: string
  notes: string
}

const METRIC_FIELDS: Array<[MetricNumberKey, string]> = [
  ['subscribers', 'Подписчики'],
  ['views', 'Просмотры'],
  ['reach', 'Охват'],
  ['reactions', 'Реакции'],
  ['forwards', 'Пересылки'],
  ['posts_count', 'Посты'],
]

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

function metricFormDefaults(channelId: number | null): MetricDraft {
  return {
    channel_id: channelId || 0,
    metric_date: dateValue(new Date()),
    subscribers: '',
    views: '',
    reach: '',
    reactions: '',
    forwards: '',
    posts_count: '',
    notes: '',
  }
}

function formattedNumber(value: number): string {
  return Number(value || 0).toLocaleString('ru-RU')
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
  const [metric, setMetric] = useState<MetricDraft>(() => metricFormDefaults(firstChannel))
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

  function updateMetricField(key: MetricNumberKey, value: string) {
    setMetric(current => ({ ...current, [key]: value }))
  }

  function renderMetricField(key: MetricNumberKey, label: string) {
    return <label className="analytics-control" key={key}>
      <span>{label}</span>
      <input className="field" type="number" min="0" inputMode="numeric" placeholder="0" value={metric[key]} onChange={event => updateMetricField(key, event.target.value)} />
    </label>
  }

  return <section className="panel analytics-panel">
    <div className="analytics-heading">
      <div className="analytics-heading-title"><BarChart3 size={18} /><h2>Аналитика каналов</h2></div>
      <button className="icon-btn" onClick={() => void load()} disabled={loading} title="Обновить"><RefreshCw size={14} /></button>
    </div>
    <p className="analytics-note">Данные вводятся вручную или из доступных событий Bot API. Полной нативной статистики Telegram обычному боту не выдаёт.</p>
    <button className="analytics-back" onClick={onBack}>← Назад</button>

    <div className="analytics-filters">
      <label className="analytics-control"><span>Период от</span><input className="field" type="date" value={fromDate} onChange={event => setFromDate(event.target.value)} /></label>
      <label className="analytics-control"><span>Период до</span><input className="field" type="date" value={toDate} onChange={event => setToDate(event.target.value)} /></label>
      <label className="analytics-control analytics-filter-channel"><span>Канал</span><select className="field" value={channelFilter ?? ''} onChange={event => setChannelFilter(event.target.value ? Number(event.target.value) : null)}><option value="">Все каналы</option>{channels.map(channel => <option key={channel.id} value={channel.id}>{channel.title}</option>)}</select></label>
    </div>

    {loading && !overview ? <div className="empty"><p>Собираю цифры. Они пока не разбежались.</p></div> : <>
      <div className="analytics-kpis">
        <article className="analytics-kpi"><span>Просмотры</span><strong>{formattedNumber(summary?.views || 0)}</strong></article>
        <article className="analytics-kpi"><span>Охват</span><strong>{formattedNumber(summary?.reach || 0)}</strong></article>
        <article className="analytics-kpi"><span>Подписчики</span><strong>{formattedNumber(summary?.subscribers || 0)}</strong></article>
        <article className="analytics-kpi"><span>Переходы</span><strong>{formattedNumber(summary?.clicks || 0)}</strong></article>
      </div>

      <section className="analytics-card analytics-telegram-card">
        <div className="analytics-section-heading"><div><strong>Статистика Telegram</strong><span>Детальные показатели через собственную MTProto-сессию</span></div><span className="analytics-source-badge">MTProto</span></div>
        {(overview?.mtproto || []).length === 0 ? <p className="analytics-telegram-empty">Сборщик ещё не подключён или статистика для канала недоступна.</p> : <div className="analytics-telegram-list">{overview?.mtproto.map(row => <article className="analytics-telegram-row" key={row.id}>
          <div className="analytics-telegram-title"><strong>{row.channel_title || channelName(row.channel_id)}</strong><span>Обновлено {shortDate(row.captured_at.slice(0, 10))}</span></div>
          <div className="analytics-telegram-values"><div><span>Подписчики</span><strong>{formattedNumber(row.followers_current)}</strong></div><div><span>Просмотров/пост</span><strong>{Number(row.views_per_post || 0).toLocaleString('ru-RU', { maximumFractionDigits: 1 })}</strong></div><div><span>Репостов/пост</span><strong>{Number(row.shares_per_post || 0).toLocaleString('ru-RU', { maximumFractionDigits: 1 })}</strong></div><div><span>Реакций/пост</span><strong>{Number(row.reactions_per_post || 0).toLocaleString('ru-RU', { maximumFractionDigits: 1 })}</strong></div></div>
        </article>)}</div>}
      </section>

      <section className="analytics-card analytics-chart-card">
        <div className="analytics-section-heading"><strong>Динамика</strong><span className="analytics-legend"><i className="legend-income" /> просмотры <i className="legend-expense" /> охват</span></div>
        <div className={`analytics-chart-scroll${series.length === 0 ? ' is-empty' : ''}`}>
          {series.length === 0 ? <div className="analytics-empty-chart">Нет данных за период</div> : <div className="analytics-chart-columns">{series.map(point => <div className="analytics-chart-column" key={point.date} title={`${point.date}: ${formattedNumber(point.views)} просмотров, ${formattedNumber(point.reach)} охвата`}>
            <div className="analytics-chart-bars"><i className="trend-income" style={{ height: `${Math.max(point.views ? 5 : 0, point.views / chartMax * 100)}%` }} /><i className="trend-expense" style={{ height: `${Math.max(point.reach ? 5 : 0, point.reach / chartMax * 100)}%` }} /></div>
            <span>{shortDate(point.date)}</span>
          </div>)}</div>}
        </div>
      </section>

      <section className="analytics-card analytics-form-card">
        <div className="analytics-section-heading"><div><strong>Добавить дневную метрику</strong><span>За одну дату и канал. Повторное сохранение обновит запись.</span></div><TrendingUp size={16} /></div>
        <div className="analytics-form-grid">
          <label className="analytics-control analytics-form-primary"><span>Канал</span><select className="field" value={metric.channel_id || ''} onChange={event => setMetric(current => ({ ...current, channel_id: Number(event.target.value) || 0 }))}><option value="">Выберите канал</option>{channels.map(channel => <option key={channel.id} value={channel.id}>{channel.title}</option>)}</select></label>
          <label className="analytics-control analytics-form-primary"><span>Дата</span><input className="field" type="date" value={metric.metric_date} onChange={event => setMetric(current => ({ ...current, metric_date: event.target.value }))} /></label>
          {METRIC_FIELDS.map(([key, label]) => renderMetricField(key, label))}
        </div>
        <label className="analytics-control analytics-control-wide"><span>Заметка</span><input className="field" placeholder="Необязательно" value={metric.notes} onChange={event => setMetric(current => ({ ...current, notes: event.target.value }))} /></label>
        <button className="primary-btn analytics-submit" onClick={() => void saveMetric()} disabled={savingMetric || !channels.length}><Plus size={16} /> {savingMetric ? 'Сохраняю…' : 'Сохранить метрику'}</button>
      </section>

      <section className="analytics-card analytics-form-card">
        <div className="analytics-section-heading"><div><strong>Собственная ссылка</strong><span>Переходы и конверсии заполняются вручную.</span></div><Link2 size={16} /></div>
        <div className="analytics-form-grid analytics-link-grid">
          <label className="analytics-control"><span>Канал</span><select className="field" value={link.channel_id || ''} onChange={event => setLink(current => ({ ...current, channel_id: Number(event.target.value) || 0 }))}><option value="">Выберите канал</option>{channels.map(channel => <option key={channel.id} value={channel.id}>{channel.title}</option>)}</select></label>
          <label className="analytics-control"><span>Название</span><input className="field" placeholder="Например, лид-форма" value={link.name} onChange={event => setLink(current => ({ ...current, name: event.target.value }))} /></label>
          <label className="analytics-control analytics-control-wide"><span>URL</span><input className="field" type="url" placeholder="https://t.me/..." value={link.url} onChange={event => setLink(current => ({ ...current, url: event.target.value }))} /></label>
          <label className="analytics-control"><span>Переходы</span><input className="field" type="number" min="0" inputMode="numeric" placeholder="0" value={link.clicks} onChange={event => setLink(current => ({ ...current, clicks: event.target.value }))} /></label>
          <label className="analytics-control"><span>Конверсии</span><input className="field" type="number" min="0" inputMode="numeric" placeholder="0" value={link.conversions} onChange={event => setLink(current => ({ ...current, conversions: event.target.value }))} /></label>
        </div>
        <label className="analytics-control analytics-control-wide"><span>Заметка</span><input className="field" placeholder="Необязательно" value={link.notes} onChange={event => setLink(current => ({ ...current, notes: event.target.value }))} /></label>
        <button className="primary-btn analytics-submit" onClick={() => void saveLink()} disabled={savingLink || !channels.length}><Plus size={16} /> {savingLink ? 'Сохраняю…' : 'Добавить ссылку'}</button>
      </section>

      <section className="analytics-card analytics-list-card">
        <div className="analytics-section-heading"><strong>Метрики</strong><span className="analytics-count">{overview?.metrics.length || 0}</span></div>
        {(overview?.metrics || []).length === 0 ? <div className="empty"><p>Метрик пока нет. Добавьте первую — статистика не кусается.</p></div> : overview?.metrics.slice().reverse().slice(0, 20).map(row => <article className="analytics-row" key={row.id}>
          <div className="analytics-row-main"><strong>{shortDate(row.metric_date)} · {row.channel_title || channelName(row.channel_id)}</strong><span>{formattedNumber(row.subscribers)} подписчиков · {formattedNumber(row.views)} просмотров · охват {formattedNumber(row.reach)}</span></div>
          <span className="status status-in_progress">{row.source === 'mtproto' ? 'MTProto' : row.source === 'bot_api' ? 'Bot API' : 'вручную'}</span>
        </article>)}
      </section>

      <section className="analytics-card analytics-list-card">
        <div className="analytics-section-heading"><strong>Ссылки</strong><span className="analytics-count">{overview?.links.length || 0}</span></div>
        {(overview?.links || []).length === 0 ? <div className="empty"><p>Ссылок пока нет.</p></div> : overview?.links.map(row => <article className="analytics-row" key={row.id}>
          <div className="analytics-row-main"><strong>{row.name} · {row.channel_title || channelName(row.channel_id)}</strong><span className="analytics-row-url"><a href={row.url} target="_blank" rel="noreferrer">{row.url}</a></span><span>{formattedNumber(row.clicks)} переходов · {formattedNumber(row.conversions)} конверсий</span></div>
          <button className="icon-btn danger" onClick={() => void removeLink(row.id)} title="Удалить"><Trash2 size={14} /></button>
        </article>)}
      </section>
    </>}
  </section>
}
