import { useEffect, useMemo, useState } from 'react'
import { BarChart3, ChevronLeft, ChevronRight, Download, Plus, RefreshCw, TrendingDown, TrendingUp, Wallet } from 'lucide-react'
import { api, type FinanceSummary, type FinanceTx } from './api'

type ExportFormat = 'csv' | 'xlsx' | 'pdf'

type Props = {
  workspaceId: number
  onBack: () => void
  onExport: (format: ExportFormat, year: number, month: number) => void
  onError: (message: string) => void
}

const MONTHS = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
const CATEGORY_LABEL: Record<string, string> = {
  advertising: 'Реклама',
  payroll: 'Зарплата',
  services: 'Сервисы',
  tax: 'Налоги',
  rent: 'Аренда',
  other: 'Другое',
}
const YEARS = Array.from({ length: 11 }, (_, index) => new Date().getFullYear() - 5 + index)

function dateInputValue(date = new Date()): string {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 10)
}

function money(value: number): string {
  return `${Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ₽`
}

function transactionDate(value: string): string {
  try {
    return new Date(value).toLocaleDateString('ru-RU', { day: '2-digit', month: 'short', year: 'numeric' })
  } catch {
    return value
  }
}

export default function Statistics({ workspaceId, onBack, onExport, onError }: Props) {
  const now = new Date()
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [summary, setSummary] = useState<FinanceSummary | null>(null)
  const [transactions, setTransactions] = useState<FinanceTx[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [type, setType] = useState<'income' | 'expense'>('income')
  const [amount, setAmount] = useState('')
  const [category, setCategory] = useState('advertising')
  const [description, setDescription] = useState('')
  const [occurredAt, setOccurredAt] = useState(dateInputValue())

  async function load() {
    setLoading(true)
    try {
      const [nextSummary, nextTransactions] = await Promise.all([
        api.financeSummary(workspaceId, year, month),
        api.financeTransactions(workspaceId, year, month),
      ])
      setSummary(nextSummary)
      setTransactions(nextTransactions)
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Не удалось загрузить статистику')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [workspaceId, year, month])

  function shiftPeriod(offset: number) {
    const date = new Date(year, month - 1 + offset, 1)
    setYear(date.getFullYear())
    setMonth(date.getMonth() + 1)
  }

  async function addTransaction() {
    const parsedAmount = Number(amount.replace(',', '.'))
    if (!Number.isFinite(parsedAmount) || parsedAmount <= 0) {
      onError('Введите сумму больше нуля')
      return
    }
    setSaving(true)
    try {
      await api.createTransaction(workspaceId, {
        type,
        amount: parsedAmount,
        category,
        description: description.trim(),
        occurred_at: occurredAt ? new Date(`${occurredAt}T12:00:00`).toISOString() : undefined,
      })
      setAmount('')
      setDescription('')
      await load()
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Не удалось добавить операцию')
    } finally {
      setSaving(false)
    }
  }

  const trend = summary?.trend || []
  const trendMax = useMemo(
    () => Math.max(1, ...trend.flatMap(point => [point.income, point.expense].map(value => Math.abs(value)))),
    [trend],
  )

  return <section className="panel statistics-panel">
    <div className="panel-title">
      <h2><BarChart3 size={17} style={{ verticalAlign: 'middle', marginRight: 6 }} /> Статистика</h2>
      <button className="icon-btn" onClick={() => void load()} disabled={loading} title="Обновить">
        <RefreshCw size={14} />
      </button>
    </div>
    <button className="icon-btn" onClick={onBack} style={{ margin: '10px 0 4px' }}>← Назад</button>

    <div className="period-picker">
      <button className="icon-btn" onClick={() => shiftPeriod(-1)} aria-label="Предыдущий месяц"><ChevronLeft size={15} /></button>
      <select className="field" value={month} onChange={event => setMonth(Number(event.target.value))}>
        {MONTHS.map((name, index) => <option key={name} value={index + 1}>{name}</option>)}
      </select>
      <select className="field" value={year} onChange={event => setYear(Number(event.target.value))}>
        {YEARS.map(value => <option key={value} value={value}>{value}</option>)}
      </select>
      <button className="icon-btn" onClick={() => shiftPeriod(1)} aria-label="Следующий месяц"><ChevronRight size={15} /></button>
    </div>

    {loading && !summary ? <div className="empty"><p>Считаю деньги. Калькулятор не дымится — уже хорошо.</p></div> : <>
      <div className="fin-cards statistics-cards">
        <div><span>Доход</span><strong className="stat-income">{money(summary?.income || 0)}</strong></div>
        <div><span>Расход</span><strong className="stat-expense">{money(summary?.expense || 0)}</strong></div>
        <div><span>Прибыль</span><strong className={(summary?.profit || 0) >= 0 ? 'stat-income' : 'stat-expense'}>{money(summary?.profit || 0)}</strong></div>
      </div>
      <p className="statistics-caption">{summary?.count || 0} операций за {MONTHS[month - 1].toLowerCase()} {year}</p>

      <div className="trend-card">
        <div className="panel-title"><strong>Динамика за 6 месяцев</strong><span className="trend-legend"><i className="legend-income" /> доход <i className="legend-expense" /> расход</span></div>
        <div className="trend-chart">
          {trend.map(point => <div className="trend-column" key={`${point.year}-${point.month}`} title={`${MONTHS[point.month - 1]} ${point.year}: доход ${money(point.income)}, расход ${money(point.expense)}`}>
            <div className="trend-bars">
              <i className="trend-income" style={{ height: `${Math.max(point.income ? 5 : 0, Math.abs(point.income) / trendMax * 100)}%` }} />
              <i className="trend-expense" style={{ height: `${Math.max(point.expense ? 5 : 0, Math.abs(point.expense) / trendMax * 100)}%` }} />
            </div>
            <span>{MONTHS[point.month - 1].slice(0, 3)}</span>
          </div>)}
        </div>
      </div>

      <div className="statistics-actions">
        <strong>Экспорт финансов</strong>
        <span>Файл придёт от бота в Telegram</span>
        <div className="btn-row">
          <button className="icon-btn" onClick={() => onExport('csv', year, month)}><Download size={14} /> CSV</button>
          <button className="icon-btn" onClick={() => onExport('xlsx', year, month)}><Download size={14} /> XLSX</button>
          <button className="icon-btn" onClick={() => onExport('pdf', year, month)}><Download size={14} /> PDF</button>
        </div>
      </div>

      <div className="statistics-form">
        <div className="panel-title"><strong>Добавить операцию</strong><Wallet size={16} /></div>
        <div className="seg" style={{ marginTop: 10 }}>
          <button className={type === 'income' ? 'seg-on' : ''} onClick={() => setType('income')}><TrendingUp size={13} /> Доход</button>
          <button className={type === 'expense' ? 'seg-on' : ''} onClick={() => setType('expense')}><TrendingDown size={13} /> Расход</button>
        </div>
        <div className="btn-row" style={{ marginTop: 10 }}>
          <input className="field" type="number" min="0" step="0.01" placeholder="Сумма, ₽" value={amount} onChange={event => setAmount(event.target.value)} />
          <input className="field" type="date" value={occurredAt} onChange={event => setOccurredAt(event.target.value)} />
        </div>
        <div className="btn-row" style={{ marginTop: 8 }}>
          <select className="field" value={category} onChange={event => setCategory(event.target.value)}>
            {Object.entries(CATEGORY_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          <input className="field" placeholder="Комментарий" value={description} onChange={event => setDescription(event.target.value)} />
        </div>
        <button className="primary-btn" onClick={() => void addTransaction()} disabled={saving || !amount.trim()}><Plus size={16} /> {saving ? 'Сохраняю…' : 'Добавить'}</button>
      </div>

      <div className="statistics-list">
        <div className="panel-title"><strong>Операции за месяц</strong><span>{transactions.length}</span></div>
        {transactions.length === 0 ? <div className="empty"><p>Операций пока нет. Финансовый гоблин отдыхает.</p></div> : transactions.map(transaction => <article className="transaction-row" key={transaction.id}>
          <div className="transaction-main">
            <span className={`transaction-dot ${transaction.type}`} />
            <div><strong>{transaction.description || CATEGORY_LABEL[transaction.category] || transaction.category}</strong><span>{CATEGORY_LABEL[transaction.category] || transaction.category} · {transactionDate(transaction.occurred_at)}{transaction.advertiser_name ? ` · ${transaction.advertiser_name}` : ''}</span></div>
          </div>
          <strong className={transaction.type === 'income' ? 'stat-income' : 'stat-expense'}>{transaction.type === 'income' ? '+' : '−'}{money(transaction.amount)}</strong>
        </article>)}
      </div>
    </>}
  </section>
}
