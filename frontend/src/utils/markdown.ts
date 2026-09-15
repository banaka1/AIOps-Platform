/**
 * 轻量 Markdown 解析器（安全版，不使用 v-html）
 * - 支持：表格（GFM pipe 语法）、行内 **加粗**、`行内代码`
 * - 输出纯数据结构，由 Vue 模板渲染（自动 HTML 转义，无 XSS 风险）
 */

export type InlineSegment =
  | { type: 'text'; content: string }
  | { type: 'bold'; content: string }
  | { type: 'code'; content: string }

export interface TextBlock {
  type: 'text'
  segments: InlineSegment[]
}

export interface TableBlock {
  type: 'table'
  headers: string[]
  rows: string[][]
  align: Array<'left' | 'center' | 'right'>
}

export type MarkdownBlock = TextBlock | TableBlock

/** 判断是否为表格行（含 | 且拆分后至少 2 列） */
function isPipeRow(line: string): boolean {
  if (!line.includes('|')) return false
  return parseRow(line).length >= 2
}

/** 判断是否为表格分隔行（仅含 | : - 空格，且至少一个 -） */
function isSeparatorRow(line: string): boolean {
  const trimmed = line.trim()
  if (!trimmed.includes('-')) return false
  return /^[|:\-\s]+$/.test(trimmed)
}

/** 解析一行表格为单元格数组，去除首尾空单元格 */
function parseRow(line: string): string[] {
  const parts = line.split('|')
  // 去除首尾由边界 | 产生的空字符串
  if (parts[0].trim() === '') parts.shift()
  if (parts[parts.length - 1].trim() === '') parts.pop()
  return parts.map((p) => p.trim())
}

/** 解析分隔行的对齐方式 */
function parseAlign(line: string): Array<'left' | 'center' | 'right'> {
  const parts = line.split('|').filter((p) => p.trim() !== '')
  return parts.map((p) => {
    const s = p.trim()
    const left = s.startsWith(':')
    const right = s.endsWith(':')
    if (left && right) return 'center'
    if (right) return 'right'
    return 'left'
  })
}

/** 行内解析：**加粗** 与 `代码` */
function parseInline(text: string): InlineSegment[] {
  const segments: InlineSegment[] = []
  // 匹配 **bold** 或 `code`
  const regex = /(\*\*([^*]+)\*\*|`([^`]+)`)/g
  let lastIndex = 0
  let match: RegExpExecArray | null
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: 'text', content: text.slice(lastIndex, match.index) })
    }
    if (match[2] !== undefined) {
      segments.push({ type: 'bold', content: match[2] })
    } else if (match[3] !== undefined) {
      segments.push({ type: 'code', content: match[3] })
    }
    lastIndex = regex.lastIndex
  }
  if (lastIndex < text.length) {
    segments.push({ type: 'text', content: text.slice(lastIndex) })
  }
  return segments.length ? segments : [{ type: 'text', content: '' }]
}

/** 主解析入口：将 Markdown 文本拆分为块级结构 */
export function parseMarkdown(content: string): MarkdownBlock[] {
  const lines = content.split('\n')
  const blocks: MarkdownBlock[] = []
  let i = 0

  while (i < lines.length) {
    // 检测表格：当前行是 pipe 行，下一行是分隔行
    if (
      i + 1 < lines.length &&
      isPipeRow(lines[i]) &&
      isSeparatorRow(lines[i + 1])
    ) {
      const headers = parseRow(lines[i])
      const align = parseAlign(lines[i + 1])
      i += 2
      const rows: string[][] = []
      while (i < lines.length && isPipeRow(lines[i])) {
        rows.push(parseRow(lines[i]))
        i++
      }
      blocks.push({ type: 'table', headers, rows, align })
      continue
    }

    // 收集文本行（连续非表格行合并为一个 text 块）
    const textLines: string[] = []
    while (
      i < lines.length &&
      !(
        i + 1 < lines.length &&
        isPipeRow(lines[i]) &&
        isSeparatorRow(lines[i + 1])
      )
    ) {
      textLines.push(lines[i])
      i++
    }
    const segments = parseInline(textLines.join('\n'))
    blocks.push({ type: 'text', segments })
  }

  return blocks
}
