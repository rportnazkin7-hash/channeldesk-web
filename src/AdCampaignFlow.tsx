import { useMemo, useState } from 'react'
import { ArrowLeft, ArrowRight, CheckCircle2, Link2, Paperclip, Plus, X } from 'lucide-react'
import { api, type Advertiser, type Asset, type Booking, type Button, type Channel, type Post } from './api'

type Props = {
  workspaceId: number
  channels: Channel[]
  advertisers: Advertiser[]
  onBack: () => void
  onDone: () => void
  onError: (message: string) => void
}

type Step = 1 | 2 | 3

function dateValue(date: Date): string {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 10)
}

function formatDate(value: string | null): string {
  if (!value) return '—'
  try { return new Date(value).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) } catch { return value }
}

export default function AdCampaignFlow({ workspaceId, channels, advertisers, onBack, onDone, onError }: Props) {
  const today = dateValue(new Date())
  const [step, setStep] = useState<Step>(1)
  const [advertiserId, setAdvertiserId] = useState<number | null>(null)
  const [channelId, setChannelId] = useState<number | null>(null)
  const [cost, setCost] = useState('')
  const [publishDate, setPublishDate] = useState(today)
  const [publishTime, setPublishTime] = useState('12:00')
  const [deleteDate, setDeleteDate] = useState(today)
  const [deleteTime, setDeleteTime] = useState('12:00')
  const [erid, setErid] = useState('')
  const [noErid, setNoErid] = useState(false)
  const [booking, setBooking] = useState<Booking | null>(null)
  const [post, setPost] = useState<Post | null>(null)
  const [assets, setAssets] = useState<Asset[]>([])
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [buttons, setButtons] = useState<Button[][]>([])
  const [buttonText, setButtonText] = useState('')
  const [buttonUrl, setButtonUrl] = useState('')
  const [saving, setSaving] = useState(false)

  const advertiser = advertisers.find(item => item.id === advertiserId)
  const channel = channels.find(item => item.id === channelId)
  const uploadedNames = useMemo(() => new Set(assets.map(asset => asset.file_name)), [assets])

  async function createBooking() {
    if (!advertiserId || !channelId || !publishDate || !publishTime || !deleteDate || !deleteTime || !Number(cost)) {
      onError('Заполните рекламодателя, канал, стоимость, даты и время')
      return
    }
    const startsAt = new Date(`${publishDate}T${publishTime}`)
    const endsAt = new Date(`${deleteDate}T${deleteTime}`)
    if (endsAt <= startsAt) {
      onError('Окончание рекламы должно быть позже начала')
      return
    }
    setSaving(true)
    try {
      const created = await api.createBooking(workspaceId, {
        advertiser_id: advertiserId,
        channel_id: channelId,
        cost: Number(cost),
        publish_at: startsAt.toISOString(),
        delete_at: endsAt.toISOString(),
        erid: noErid ? null : (erid.trim() || null),
        erid_required: !noErid,
      })
      if (!created.post_id) throw new Error('Не удалось создать рекламный пост для брони')
      const details = await api.getPost(workspaceId, created.post_id)
      const postAssets = await api.assets(workspaceId, created.post_id)
      setBooking(created)
      setPost(details.post)
      setAssets(postAssets)
      setTitle(details.post.title || '')
      setText(details.post.text || '')
      setButtons(details.post.buttons || [])
      setStep(2)
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Ошибка создания рекламной кампании')
    } finally {
      setSaving(false)
    }
  }

  async function savePost() {
    if (!post) return
    if (!title.trim() || !text.trim()) {
      onError('Заполните заголовок и текст рекламного поста')
      return
    }
    setSaving(true)
    try {
      const updated = await api.updatePost(workspaceId, post.id, { title: title.trim(), text, buttons })
      setPost(updated)
      setStep(3)
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Ошибка сохранения рекламного поста')
    } finally {
      setSaving(false)
    }
  }

  async function uploadFiles(files: FileList | null) {
    if (!post || !files?.length) return
    setSaving(true)
    try {
      for (const file of Array.from(files).slice(0, 10)) {
        if (uploadedNames.has(file.name)) continue
        const ticket = await api.uploadTicket(workspaceId, {
          post_id: post.id,
          file_name: file.name,
          content_type: file.type || 'application/octet-stream',
          size: file.size,
        })
        await api.uploadDirect(ticket, file)
      }
      setAssets(await api.assets(workspaceId, post.id))
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Ошибка загрузки вложения')
    } finally {
      setSaving(false)
    }
  }

  async function removeAsset(assetId: number) {
    if (!post) return
    setSaving(true)
    try {
      await api.deleteAsset(assetId)
      setAssets(await api.assets(workspaceId, post.id))
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Ошибка удаления вложения')
    } finally {
      setSaving(false)
    }
  }

  function addButton() {
    const buttonName = buttonText.trim()
    const url = buttonUrl.trim()
    if (!buttonName || !url) return
    if (!/^(https?:\/\/|tg:\/\/)/i.test(url)) {
      onError('URL кнопки должен начинаться с https://, http:// или tg://')
      return
    }
    setButtons(current => [...current, [{ text: buttonName, url }]])
    setButtonText('')
    setButtonUrl('')
  }

  function removeButton(rowIndex: number, buttonIndex: number) {
    setButtons(current => current.map((row, rowNo) => row.filter((_, buttonNo) => rowNo !== rowIndex || buttonNo !== buttonIndex)).filter(row => row.length))
  }

  return <section className="panel campaign-flow">
    <div className="campaign-flow-head"><div><span className="eyebrow">НОВАЯ КАМПАНИЯ</span><h2>{step === 1 ? 'Рекламная бронь' : step === 2 ? 'Рекламный пост' : 'Проверка публикации'}</h2></div><button className="back-btn" onClick={onBack}>← Назад</button></div>
    <div className="campaign-stepper"><span className={step >= 1 ? 'done' : ''}>1. Бронь{step > 1 ? ' ✓' : ''}</span><span className={step >= 2 ? 'active' : ''}>2. Пост{step > 2 ? ' ✓' : ''}</span><span className={step >= 3 ? 'active' : ''}>3. Проверка</span></div>

    {step === 1 && <>
      <div className="campaign-card"><div className="campaign-card-title"><strong>Клиент и размещение</strong><span className="campaign-icon">↗</span></div>
        <label className="form-label">Рекламодатель</label>
        <select className="field" value={advertiserId ?? ''} onChange={event => setAdvertiserId(event.target.value ? Number(event.target.value) : null)}><option value="">Выберите рекламодателя</option>{advertisers.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
        <div className="campaign-form-row"><div><label className="form-label">Канал</label><select className="field" value={channelId ?? ''} onChange={event => setChannelId(event.target.value ? Number(event.target.value) : null)}><option value="">Выберите канал</option>{channels.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select></div><div><label className="form-label">Формат</label><select className="field" defaultValue="post"><option value="post">Пост</option><option value="mention">Упоминание</option><option value="repost">Репост</option></select></div></div>
        <div className="campaign-form-row"><div><label className="form-label">Начало рекламы</label><input className="field" type="date" value={publishDate} onChange={event => setPublishDate(event.target.value)} /></div><div><label className="form-label">Окончание рекламы</label><input className="field" type="date" value={deleteDate} onChange={event => setDeleteDate(event.target.value)} /></div></div>
        <div className="campaign-form-row"><div><label className="form-label">Время начала</label><input className="field" type="time" value={publishTime} onChange={event => setPublishTime(event.target.value)} /></div><div><label className="form-label">Время окончания</label><input className="field" type="time" value={deleteTime} onChange={event => setDeleteTime(event.target.value)} /></div></div>
        <label className="form-label">Стоимость, ₽</label><input className="field" type="number" min="0" value={cost} onChange={event => setCost(event.target.value)} placeholder="15000" />
        <p className="campaign-hint">Размещение будет занято ровно на выбранный период.</p>
      </div>
      <div className="campaign-card"><div className="campaign-card-title"><strong>Оплата</strong><span className="status status-cancelled">Не оплачено</span></div><p className="campaign-hint">Пост не уйдёт в канал, пока бронь не будет оплачена.</p></div>
      <label className="campaign-checkbox"><input type="checkbox" checked={noErid} onChange={event => setNoErid(event.target.checked)} /><span>ERID не требуется</span></label>
      {!noErid && <><label className="form-label">ERID</label><input className="field" value={erid} onChange={event => setErid(event.target.value)} placeholder="erid: ..." /></>}
      <button className="primary-btn campaign-submit" onClick={() => void createBooking()} disabled={saving}><ArrowRight size={16} /> {saving ? 'Создаю…' : 'Продолжить к посту'}</button>
    </>}

    {step === 2 && <>
      <div className="campaign-card"><div className="campaign-card-title"><strong>Содержание</strong><span className="campaign-hint">Черновик</span></div>
        <label className="form-label">Заголовок</label><input className="field" value={title} onChange={event => setTitle(event.target.value)} placeholder="Заголовок рекламного поста" />
        <label className="form-label">Текст публикации</label><textarea className="field campaign-textarea" value={text} onChange={event => setText(event.target.value)} placeholder="Напишите рекламный текст…" />
        <label className="form-label">Вложения</label><div className="campaign-chips">{assets.map(asset => <span className="btn-chip" key={asset.id}>📎 {asset.file_name}<button onClick={() => void removeAsset(asset.id)} disabled={saving}><X size={11} /></button></span>)}<label className="file-btn"><Paperclip size={14} /> Добавить<input type="file" multiple accept="image/*,video/*,.pdf,.doc,.docx,.xls,.xlsx,.txt" style={{display:'none'}} onChange={event => {void uploadFiles(event.target.files);event.target.value=''}} /></label></div>
        <label className="form-label">Кнопки</label><div className="campaign-chips">{buttons.map((row,rowIndex)=>row.map((button,buttonIndex)=><span className="btn-chip" key={`${rowIndex}-${buttonIndex}`}>🔗 {button.text}<button onClick={() => removeButton(rowIndex,buttonIndex)}><X size={11} /></button></span>))}</div>
        <div className="campaign-form-row" style={{marginTop:8}}><input className="field" placeholder="Текст кнопки" value={buttonText} onChange={event => setButtonText(event.target.value)} /><input className="field" placeholder="https://..." value={buttonUrl} onChange={event => setButtonUrl(event.target.value)} /><button className="icon-btn" onClick={addButton} disabled={!buttonText.trim() || !buttonUrl.trim()}><Plus size={15} /></button></div>
      </div>
      <div className="campaign-card"><div className="campaign-card-title"><strong>Кампания</strong><span className="status status-review">Ожидает оплаты</span></div><p className="campaign-hint">{advertiser?.name || 'Рекламодатель'} · {channel?.title || 'Канал'} · {formatDate(booking?.publish_at || null)}</p></div>
      <div className="campaign-flow-actions"><button className="back-btn" onClick={() => setStep(1)}><ArrowLeft size={15} /> Назад</button><button className="primary-btn campaign-submit" onClick={() => void savePost()} disabled={saving}><ArrowRight size={16} /> {saving ? 'Сохраняю…' : 'Сохранить и проверить'}</button></div>
    </>}

    {step === 3 && <>
      <div className="campaign-card campaign-success"><div className="campaign-card-title"><strong>Кампания готова</strong><CheckCircle2 size={21} /></div><h3>{advertiser?.name || 'Рекламодатель'}</h3><p className="campaign-hint">{channel?.title || 'Канал'} · Пост · {formatDate(booking?.publish_at || null)}</p><p className="campaign-hint">{Number(cost || 0).toLocaleString('ru-RU')} ₽ · ожидает оплаты</p></div>
      <div className="campaign-card"><div className="campaign-card-title"><strong>Чек-лист</strong><span className="campaign-hint">4 из 4</span></div><div className="campaign-check"><b>✓</b><span>Текст рекламного поста заполнен</span></div><div className="campaign-check"><b>✓</b><span>{assets.length ? `${assets.length} влож. добавлено` : 'Вложения можно добавить позже'}</span></div><div className="campaign-check"><b>✓</b><span>{buttons.length ? 'Кнопки добавлены' : 'Кнопок нет'}</span></div><div className="campaign-check"><b>✓</b><span>Дата и канал забронированы</span></div></div>
      <div className="campaign-flow-actions"><button className="icon-btn" onClick={() => setStep(2)}><ArrowLeft size={15} /> Изменить пост</button><button className="primary-btn campaign-submit" onClick={onDone}>Готово</button></div>
    </>}
  </section>
}
