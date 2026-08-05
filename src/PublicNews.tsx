import { useEffect, useState } from 'react'
import { CheckCircle2, FileText, Paperclip, Send, XCircle } from 'lucide-react'
import { api } from './api'

const MAX_FILE_SIZE = 50 * 1024 * 1024

type PageState = Awaited<ReturnType<typeof api.publicNewsPage>>
type Uploaded = { id: number; name: string }

export default function PublicNews({ token }: { token: string }) {
  const [page, setPage] = useState<PageState | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [name, setName] = useState('')
  const [telegram, setTelegram] = useState('')
  const [email, setEmail] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [anonymous, setAnonymous] = useState(false)
  const [uploaded, setUploaded] = useState<Uploaded[]>([])
  const [uploading, setUploading] = useState(false)
  const [sending, setSending] = useState(false)

  useEffect(() => {
    void api.publicNewsPage(token)
      .then(setPage)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Страница недоступна'))
      .finally(() => setLoading(false))
  }, [token])

  async function addFiles(files: FileList | null) {
    if (!files?.length) return
    setError('')
    setUploading(true)
    try {
      for (const file of Array.from(files).slice(0, 10 - uploaded.length)) {
        if (file.size > MAX_FILE_SIZE) throw new Error(`Файл «${file.name}» больше 50 МБ`)
        const ticket = await api.publicNewsUploadUrl(token, {
          file_name: file.name,
          content_type: file.type || 'application/octet-stream',
          size: file.size,
        })
        await api.uploadDirect(ticket, file)
        setUploaded(current => [...current, { id: ticket.asset_id, name: file.name }])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось загрузить файл')
    } finally {
      setUploading(false)
    }
  }

  async function submit() {
    setError('')
    setSuccess('')
    if (!text.trim() && uploaded.length === 0) {
      setError('Добавьте текст или хотя бы один файл')
      return
    }
    setSending(true)
    try {
      const result = await api.publicNewsSubmit(token, {
        title,
        text,
        contact_name: name,
        contact_telegram: telegram,
        contact_email: email,
        source_url: sourceUrl,
        is_anonymous: anonymous,
        asset_ids: uploaded.map(file => file.id),
      })
      setSuccess(result.message || 'Материал отправлен редактору')
      setTitle('')
      setText('')
      setName('')
      setTelegram('')
      setEmail('')
      setSourceUrl('')
      setAnonymous(false)
      setUploaded([])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось отправить материал')
    } finally {
      setSending(false)
    }
  }

  if (loading) return <main className="public-report-page"><div className="public-report-state">Загружаю форму…</div></main>
  if (error && !page) return <main className="public-report-page"><div className="public-report-state"><XCircle size={30} /><strong>Форма недоступна</strong><span>{error}</span></div></main>
  if (!page) return null

  return <main className="public-report-page">
    <section className="public-report-shell slots-shell">
      <div className="public-report-brand"><span className="public-report-logo">CD</span><span>ChannelDesk</span></div>
      <div className="public-report-heading"><div><span className="public-report-eyebrow">РЕДАКЦИЯ</span><h1>{page.title}</h1></div><FileText size={24} /></div>
      <p className="public-report-muted">{page.description || 'Есть новость, фото или видео? Отправьте материал редакции.'}</p>
      {page.channel_title && <div className="slots-price"><span>Материал отправится в редакцию канала</span><strong>{page.channel_title}</strong></div>}
      {success && <div className="public-slot-success"><CheckCircle2 size={18} /><span>{success}</span></div>}
      {error && <div className="public-slot-error"><XCircle size={16} /><span>{error}</span></div>}

      <section className="public-slot-form">
        <h2>Материал</h2>
        <label>Заголовок<input placeholder="Короткий заголовок" value={title} onChange={event => setTitle(event.target.value)} /></label>
        <label>Что произошло?<textarea rows={7} placeholder="Опишите новость или ситуацию…" value={text} onChange={event => setText(event.target.value)} /></label>
        <label>Фото, видео или документы</label>
        <label className="file-btn"><Paperclip size={15} /> {uploading ? 'Загружаю…' : 'Добавить файлы'}<input type="file" multiple accept="image/*,video/*,.pdf,.doc,.docx,.xls,.xlsx,.txt" style={{ display: 'none' }} onChange={event => { void addFiles(event.target.files); event.target.value = '' }} /></label>
        {uploaded.length > 0 && <div className="chip-wrap">{uploaded.map(file => <span className="btn-chip" key={file.id}>📎 {file.name}<button onClick={() => setUploaded(current => current.filter(item => item.id !== file.id))} style={{ background: 'none', border: 0, color: 'var(--danger)', padding: '0 2px' }}><XCircle size={12} /></button></span>)}</div>}
        <label>Ссылка на источник<input type="url" placeholder="https://example.com" value={sourceUrl} onChange={event => setSourceUrl(event.target.value)} /></label>
      </section>

      <section className="public-slot-form">
        <h2>Контакт</h2>
        <label>Имя или организация<input placeholder="Как к вам обращаться?" value={name} onChange={event => setName(event.target.value)} /></label>
        <label>Telegram<input placeholder="@username" value={telegram} onChange={event => setTelegram(event.target.value)} /></label>
        <label>Email<input type="email" placeholder="mail@example.com" value={email} onChange={event => setEmail(event.target.value)} /></label>
        <label className="campaign-checkbox"><input type="checkbox" checked={anonymous} onChange={event => setAnonymous(event.target.checked)} /><span>Отправить материал анонимно</span></label>
        <p className="campaign-hint">Материал сначала попадёт редактору на проверку и не будет опубликован автоматически.</p>
        <button className="public-slot-submit" onClick={() => void submit()} disabled={sending || uploading}><Send size={15} />{sending ? 'Отправляю…' : 'Отправить редактору'}</button>
      </section>
      <p className="public-report-footer">ChannelDesk Newsdesk</p>
    </section>
  </main>
}
