function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function formatInline(text: string): string {
  return escapeHtml(text).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
}

function isTableSeparator(line: string): boolean {
  const trimmed = line.trim()
  if (!trimmed.includes('-')) return false
  return /^\|?(?:\s*\|?\s*:?-{3,}:?\s*)+\|?\s*$/.test(trimmed)
}

function isAlignmentFragment(line: string): boolean {
  const trimmed = line.trim()
  if (!trimmed.includes('-')) return false
  if (isTableSeparator(trimmed)) return true
  return /^\|?\s*:?-{3,}:?\s*\|?\s*$/.test(trimmed)
}

function parseTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => cell.trim())
}

function isTableHeaderRow(line: string): boolean {
  const trimmed = line.trim()
  if (!trimmed.startsWith('|')) return false
  const cells = parseTableRow(trimmed).filter(Boolean)
  return cells.length >= 2
}

function isTableDataRow(line: string): boolean {
  const trimmed = line.trim()
  if (!trimmed.startsWith('|')) return false
  if (isAlignmentFragment(trimmed)) return false
  return parseTableRow(trimmed).filter(Boolean).length >= 2
}

function renderTableBlock(headerLine: string, bodyLines: string[]): string {
  const headerCells = parseTableRow(headerLine).filter((cell, idx, arr) => cell || idx < arr.length)
  const thead = `<thead><tr>${headerCells.map((cell) => `<th>${formatInline(cell)}</th>`).join('')}</tr></thead>`
  const tbody = bodyLines.length
    ? `<tbody>${bodyLines
        .map((line) => {
          const cells = parseTableRow(line)
          return `<tr>${cells.map((cell) => `<td>${formatInline(cell)}</td>`).join('')}</tr>`
        })
        .join('')}</tbody>`
    : ''

  return `<div class="md-table-wrap"><table class="md-table">${thead}${tbody}</table></div>`
}

function stripAlignmentSyntax(text: string): string {
  return text
    .replace(/(?:\|\s*)+\|?\s*:?-{3,}:?\s*(?:\|\s*\|?\s*:?-{3,}:?\s*)+/g, '')
    .replace(/^\s*\|?\s*:?-{3,}:?\s*\|?\s*$/gm, '')
}

function stripInlineAlignmentSegments(text: string): string {
  return stripAlignmentSyntax(text)
}

function normalizeSingleLineTable(line: string): string {
  if (!line.includes('|')) return line

  let normalized = stripAlignmentSyntax(line)
  normalized = normalized.replace(/\|\s*\|\s*(?=\|\s*\d+\s*\|)/g, '|\n')
  normalized = normalized.replace(/\|\s+(?=\|\s*\d+\s*\|)/g, '|\n')
  return normalized
}

function normalizeInlineTables(text: string): string {
  return stripAlignmentSyntax(text)
    .replace(/\r\n/g, '\n')
    .replace(/([：:。!?])\s*(\|)/g, '$1\n$2')
    .split('\n')
    .map((line) => normalizeSingleLineTable(line))
    .join('\n')
}

function formatMarkdownTables(text: string): string {
  const lines = normalizeInlineTables(text).split('\n')
  const out: string[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    if (isTableHeaderRow(line)) {
      const header = line
      i += 1
      const body: string[] = []

      while (i < lines.length) {
        const current = lines[i]
        if (isAlignmentFragment(current) || isTableSeparator(current)) {
          i += 1
          continue
        }
        if (isTableDataRow(current)) {
          body.push(current)
          i += 1
          continue
        }
        break
      }

      if (body.length > 0) {
        out.push(renderTableBlock(header, body))
        continue
      }
    }

    if (isAlignmentFragment(line) || isTableSeparator(line)) {
      i += 1
      continue
    }

    out.push(line)
    i += 1
  }

  return out.join('\n')
}

function formatMarkdownHeadings(text: string): string {
  return text.replace(/^#{1,6}\s+(.+)$/gm, (_, title: string) => {
    return `<div class="md-section-title">${formatInline(title.trim())}</div>`
  })
}

function stripResidualAlignmentMarkup(html: string): string {
  return html
    .replace(/(?:<br\/>|\n)?\s*\|?\s*:?-{3,}:?\s*(?:\|?\s*:?-{3,}:?\s*)*(?:<br\/>|\||$)/g, '')
    .replace(/\|\s*\|\s*/g, '| ')
    .replace(/(<br\/>){3,}/g, '<br/><br/>')
}

/** 轻量 Markdown 渲染：标题、加粗、列表、分隔线、表格 */
export function formatMarkdown(text: string): string {
  let html = formatMarkdownTables(text)
  html = formatMarkdownHeadings(html)
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/^---$/gm, '<hr class="md-divider"/>')
  html = html.replace(/^- (.+)$/gm, '<li>$1</li>')
  html = html.replace(/(<li>.*<\/li>\n?)+/g, (match) => `<ul class="md-list">${match}</ul>`)
  html = html.replace(/\n/g, '<br/>')
  html = stripResidualAlignmentMarkup(html)
  return html
}
