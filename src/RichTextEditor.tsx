import { useEffect, useRef, useState } from 'react'

type Props = {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  minHeight?: number
}

type ToolbarPosition = { left: number; top: number } | null

const ALLOWED_TAGS = new Set(['B', 'STRONG', 'I', 'EM', 'U', 'S', 'STRIKE', 'CODE', 'PRE', 'BLOCKQUOTE', 'A', 'BR', 'DIV', 'P'])

function escapeText(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function cleanHtml(html: string): string {
  const doc = new DOMParser().parseFromString(html, 'text/html')
  function serialize(node: Node): string {
    if (node.nodeType === Node.TEXT_NODE) return escapeText(node.textContent || '')
    if (node.nodeType !== Node.ELEMENT_NODE) return ''
    const element = node as HTMLElement
    const tag = element.tagName.toUpperCase()
    const children = Array.from(element.childNodes).map(serialize).join('')
    if (!ALLOWED_TAGS.has(tag)) return children
    if (tag === 'BR') return '<br>'
    if (tag === 'DIV' || tag === 'P') return `${children}<br>`
    if (tag === 'STRONG') return `<b>${children}</b>`
    if (tag === 'EM') return `<i>${children}</i>`
    if (tag === 'STRIKE') return `<s>${children}</s>`
    if (tag === 'A') {
      const href = element.getAttribute('href') || ''
      if (!/^(https?:\/\/|tg:\/\/)/i.test(href)) return children
      return `<a href="${escapeText(href)}">${children}</a>`
    }
    return `<${tag.toLowerCase()}>${children}</${tag.toLowerCase()}>`
  }
  return Array.from(doc.body.childNodes).map(serialize).join('').replace(/(<br>){3,}/g, '<br><br>').replace(/(<br>)$/i, '')
}

export default function RichTextEditor({ value, onChange, placeholder = 'Текст публикации…', minHeight = 150 }: Props) {
  const rootRef = useRef<HTMLDivElement>(null)
  const editorRef = useRef<HTMLDivElement>(null)
  const rangeRef = useRef<Range | null>(null)
  const [toolbar, setToolbar] = useState<ToolbarPosition>(null)

  useEffect(() => {
    const editor = editorRef.current
    if (editor && document.activeElement !== editor && editor.innerHTML !== value) editor.innerHTML = value || ''
  }, [value])

  useEffect(() => {
    function updateSelection() {
      const editor = editorRef.current
      const root = rootRef.current
      const selection = window.getSelection()
      if (!editor || !root || !selection || selection.rangeCount === 0 || selection.isCollapsed) {
        setToolbar(null)
        return
      }
      const range = selection.getRangeAt(0)
      if (!editor.contains(range.commonAncestorContainer)) {
        setToolbar(null)
        return
      }
      rangeRef.current = range.cloneRange()
      const rect = range.getBoundingClientRect()
      const rootRect = root.getBoundingClientRect()
      const left = Math.max(4, Math.min(rect.left - rootRect.left + rect.width / 2 - 116, rootRect.width - 236))
      const top = Math.max(4, rect.top - rootRect.top - 42)
      setToolbar({ left, top })
    }
    document.addEventListener('selectionchange', updateSelection)
    return () => document.removeEventListener('selectionchange', updateSelection)
  }, [])

  function restoreSelection() {
    const selection = window.getSelection()
    if (!selection || !rangeRef.current) return
    selection.removeAllRanges()
    selection.addRange(rangeRef.current)
  }

  function command(name: string, valueArg?: string) {
    restoreSelection()
    document.execCommand(name, false, valueArg)
    const editor = editorRef.current
    if (editor) onChange(cleanHtml(editor.innerHTML))
    setToolbar(null)
    editor?.focus()
  }

  function addLink() {
    restoreSelection()
    const url = window.prompt('Ссылка', 'https://')?.trim() || ''
    if (!/^(https?:\/\/|tg:\/\/)/i.test(url)) return
    document.execCommand('createLink', false, url)
    const editor = editorRef.current
    if (editor) onChange(cleanHtml(editor.innerHTML))
    setToolbar(null)
    editor?.focus()
  }

  return <div className="rich-editor" ref={rootRef}>
    {toolbar && <div className="rich-toolbar" style={{ left: toolbar.left, top: toolbar.top }} onMouseDown={event => event.preventDefault()}>
      <button title="Жирный" onClick={() => command('bold')}><b>B</b></button>
      <button title="Курсив" onClick={() => command('italic')}><i>I</i></button>
      <button title="Подчёркивание" onClick={() => command('underline')}><u>U</u></button>
      <button title="Зачёркивание" onClick={() => command('strikeThrough')}><s>S</s></button>
      <button title="Код" onClick={() => command('formatBlock', 'pre')}>{'<>'}</button>
      <button title="Цитата" onClick={() => command('formatBlock', 'blockquote')}>❝</button>
      <button title="Ссылка" onClick={addLink}>🔗</button>
      <button title="Очистить форматирование" onClick={() => { command('removeFormat'); command('formatBlock', 'div') }}>×</button>
    </div>}
    <div className="rich-editor-label">Выделите текст — появится форматирование</div>
    <div className="rich-editor-field" ref={editorRef} contentEditable suppressContentEditableWarning data-placeholder={placeholder} style={{ minHeight }} onInput={event => onChange(cleanHtml(event.currentTarget.innerHTML))} onFocus={() => {}} />
  </div>
}
