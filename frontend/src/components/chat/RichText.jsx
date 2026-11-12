import { Fragment } from 'react'

/*
  Renderizador markdown mínimo, sin HTML crudo (el texto del modelo nunca se
  interpreta como HTML). Soporta párrafos, negrita, cursiva, código en línea,
  enlaces, listas, tablas, encabezados, citas y bloques de código.
*/

const INLINE_PATTERN =
  /(\*\*[^*\n]+\*\*|__[^_\n]+__|`[^`\n]+`|\[[^\]\n]+\]\([^)\s]+\)|\*[^*\n]+\*)/g

const SAFE_URL = /^(https?:\/\/|mailto:)/i

function renderInline(text) {
  const nodes = []
  let last = 0
  let key = 0
  const re = new RegExp(INLINE_PATTERN.source, 'g')
  let match

  while ((match = re.exec(text)) !== null) {
    if (match.index > last) {
      nodes.push(<Fragment key={key++}>{text.slice(last, match.index)}</Fragment>)
    }
    nodes.push(renderInlineToken(match[0], key++))
    last = match.index + match[0].length
  }
  if (last < text.length) {
    nodes.push(<Fragment key={key++}>{text.slice(last)}</Fragment>)
  }
  return nodes
}

function renderInlineToken(token, key) {
  if (token.startsWith('**') && token.endsWith('**')) {
    return <strong key={key}>{renderInline(token.slice(2, -2))}</strong>
  }
  if (token.startsWith('__') && token.endsWith('__')) {
    return <strong key={key}>{renderInline(token.slice(2, -2))}</strong>
  }
  if (token.startsWith('`') && token.endsWith('`')) {
    return <code key={key} className="md-inline-code">{token.slice(1, -1)}</code>
  }
  if (token.startsWith('[')) {
    const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(token)
    if (!link || !SAFE_URL.test(link[2])) return token
    return (
      <a key={key} href={link[2]} target="_blank" rel="noreferrer noopener">
        {renderInline(link[1])}
      </a>
    )
  }
  if (token.startsWith('*') && token.endsWith('*')) {
    return <em key={key}>{renderInline(token.slice(1, -1))}</em>
  }
  return token
}

function matchListLine(line) {
  const bullet = /^(\s*)[-*+•·]\s+(.*)$/.exec(line)
  if (bullet) return { indent: bullet[1].length, ordered: false, text: bullet[2] }
  const numbered = /^(\s*)\d+[.)]\s+(.*)$/.exec(line)
  if (numbered) return { indent: numbered[1].length, ordered: true, text: numbered[2] }
  return null
}

function splitRow(line) {
  let value = line.trim()
  if (value.startsWith('|')) value = value.slice(1)
  if (value.endsWith('|')) value = value.slice(0, -1)
  return value.split('|').map((cell) => cell.trim())
}

function isTableSeparator(line) {
  const cells = splitRow(line)
  return cells.length > 0 && cells.every((cell) => /^:?-{3,}:?$/.test(cell))
}

function isTableStart(lines, index) {
  return (
    lines[index].includes('|') &&
    index + 1 < lines.length &&
    isTableSeparator(lines[index + 1])
  )
}

function alignmentFor(cell) {
  const left = cell.startsWith(':')
  const right = cell.endsWith(':')
  if (left && right) return 'center'
  if (right) return 'right'
  return 'left'
}

function parseTable(lines, start) {
  const headers = splitRow(lines[start])
  const aligns = splitRow(lines[start + 1]).map(alignmentFor)
  const rows = []
  let index = start + 2
  while (index < lines.length && lines[index].trim() && lines[index].includes('|')) {
    const cells = splitRow(lines[index])
    rows.push(headers.map((_, column) => cells[column] ?? ''))
    index++
  }
  return {
    block: { type: 'table', headers, aligns, rows },
    next: index,
  }
}

function parseList(lines, start) {
  const first = matchListLine(lines[start])
  const ordered = first.ordered
  const items = []
  let index = start
  while (index < lines.length) {
    const item = matchListLine(lines[index])
    if (!item || item.ordered !== ordered) break
    const parts = [item.text]
    index++
    while (index < lines.length && lines[index].trim() && !matchListLine(lines[index])) {
      if (!/^\s{2,}/.test(lines[index])) break
      parts.push(lines[index].trim())
      index++
    }
    items.push(parts.join(' '))
  }
  return { block: { type: 'list', ordered, items }, next: index }
}

function isBlockStart(lines, index) {
  const line = lines[index]
  if (!line.trim()) return true
  if (/^```/.test(line.trim())) return true
  if (/^(#{1,6})\s+/.test(line)) return true
  if (/^\s*([-*_])\1{2,}\s*$/.test(line)) return true
  if (isTableStart(lines, index)) return true
  if (matchListLine(line)) return true
  if (/^\s*>\s?/.test(line)) return true
  return false
}

function parseBlocks(text) {
  const lines = text.replace(/\r\n?/g, '\n').split('\n')
  const blocks = []
  let index = 0

  while (index < lines.length) {
    const line = lines[index]
    if (!line.trim()) {
      index++
      continue
    }

    if (/^```/.test(line.trim())) {
      const language = line.trim().slice(3).trim()
      const code = []
      index++
      while (index < lines.length && !/^```/.test(lines[index].trim())) {
        code.push(lines[index])
        index++
      }
      if (index < lines.length) index++
      blocks.push({ type: 'code', language, text: code.join('\n') })
      continue
    }

    const heading = /^(#{1,6})\s+(.*)$/.exec(line)
    if (heading) {
      blocks.push({ type: 'heading', level: heading[1].length, text: heading[2] })
      index++
      continue
    }

    if (/^\s*([-*_])\1{2,}\s*$/.test(line)) {
      blocks.push({ type: 'hr' })
      index++
      continue
    }

    if (isTableStart(lines, index)) {
      const table = parseTable(lines, index)
      blocks.push(table.block)
      index = table.next
      continue
    }

    if (matchListLine(line)) {
      const list = parseList(lines, index)
      blocks.push(list.block)
      index = list.next
      continue
    }

    if (/^\s*>\s?/.test(line)) {
      const quote = []
      while (index < lines.length && /^\s*>\s?/.test(lines[index])) {
        quote.push(lines[index].replace(/^\s*>\s?/, ''))
        index++
      }
      blocks.push({ type: 'quote', blocks: parseBlocks(quote.join('\n')) })
      continue
    }

    const paragraph = []
    while (index < lines.length && lines[index].trim() && !isBlockStart(lines, index)) {
      paragraph.push(lines[index])
      index++
    }
    blocks.push({ type: 'paragraph', text: paragraph.join('\n') })
  }

  return blocks
}

function renderTable(table, key) {
  return (
    <div className="md-table-wrap" key={key}>
      <table className="md-table">
        <thead>
          <tr>
            {table.headers.map((header, column) => (
              <th key={column} style={{ textAlign: table.aligns[column] ?? 'left' }}>
                {renderInline(header)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, column) => (
                <td key={column} style={{ textAlign: table.aligns[column] ?? 'left' }}>
                  {renderInline(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function renderParagraph(text, key) {
  // Respeta los saltos de línea aunque el modelo no use viñetas: sin esto,
  // varias líneas se muestran como un único párrafo pegado.
  const lines = text.split('\n')
  return (
    <p key={key} className="md-paragraph">
      {lines.map((line, index) => (
        <Fragment key={index}>
          {index > 0 && <br />}
          {renderInline(line)}
        </Fragment>
      ))}
    </p>
  )
}

function renderBlock(block, key) {
  switch (block.type) {
    case 'heading': {
      const Tag = `h${Math.min(block.level, 4)}`
      return (
        <Tag key={key} className={`md-heading md-h${block.level}`}>
          {renderInline(block.text)}
        </Tag>
      )
    }
    case 'hr':
      return <hr key={key} className="md-hr" />
    case 'table':
      return renderTable(block, key)
    case 'list': {
      const Tag = block.ordered ? 'ol' : 'ul'
      return (
        <Tag key={key} className={`md-list${block.ordered ? '' : ' md-list-dash'}`}>
          {block.items.map((item, index) => (
            <li key={index}>
              {block.ordered ? (
                renderInline(item)
              ) : (
                <>
                  <span className="md-dash">- </span>
                  {renderInline(item)}
                </>
              )}
            </li>
          ))}
        </Tag>
      )
    }
    case 'quote':
      return (
        <blockquote key={key} className="md-quote">
          {block.blocks.map(renderBlock)}
        </blockquote>
      )
    case 'code':
      return (
        <pre key={key} className="md-pre">
          <code>{block.text}</code>
        </pre>
      )
    default:
      return renderParagraph(block.text, key)
  }
}

export default function RichText({ text }) {
  if (!text) return null
  return <div className="md">{parseBlocks(text).map(renderBlock)}</div>
}
