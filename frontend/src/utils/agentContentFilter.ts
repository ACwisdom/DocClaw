const CONTEXT_START = '【系统上下文】'
const CONTEXT_END = '请先 read_file 读取偏好文件（若存在）。'
const INTERNAL_NOTICE_MARKER = '【重要】以上内容为内部会话上下文'
const INTERNAL_NOTICE_END = '直接回答医生的问题即可。'
const PATIENT_INFO_HEADER = '的信息如下'
const RECENT_PREFS_KEY = '"recent_(?:patients|topics)"'
const RECENT_PREFS_JSON_FENCE_RE = new RegExp(
  `\`\`\`json\\s*\\n?\\{[\\s\\S]*?${RECENT_PREFS_KEY}[\\s\\S]*?\\}\\s*\\n?\`\`\``,
  'gi',
)
const RECENT_PREFS_JSON_BARE_RE = new RegExp(
  `\\{[\\s\\S]*?${RECENT_PREFS_KEY}[\\s\\S]*?${RECENT_PREFS_KEY}[\\s\\S]*?\\}`,
  'gi',
)
const RECENT_PREFS_JSON_INCOMPLETE_FENCE_RE = new RegExp(
  `\`\`\`json[\\s\\S]*?${RECENT_PREFS_KEY}[\\s\\S]*$`,
  'gi',
)
const RECENT_PREFS_JSON_INCOMPLETE_BARE_RE = new RegExp(
  `\\{[\\s\\S]*?${RECENT_PREFS_KEY}[\\s\\S]*$`,
  'gi',
)

function stripContextBlock(content: string): string {
  const start = content.indexOf(CONTEXT_START)
  if (start === -1) return content

  const endIdx = content.indexOf(CONTEXT_END, start)
  if (endIdx === -1) {
    return content.slice(0, start).trimEnd()
  }

  const after = content.slice(endIdx + CONTEXT_END.length).replace(/^\s+/, '')
  return (content.slice(0, start) + after).trimStart()
}

function looksLikeLeakedPatientSummaryLine(line: string): boolean {
  const stripped = line.trim()
  if (!stripped) return false
  if (stripped.startsWith('```')) return true
  if (stripped.startsWith('**') || stripped.startsWith('- ') || stripped.startsWith('* ')) {
    return true
  }
  if (stripped.startsWith('当前问诊患者姓名')) return true
  if (stripped.includes(PATIENT_INFO_HEADER)) return true
  return false
}

function stripInternalNoticeBlock(content: string): string {
  const start = content.indexOf(INTERNAL_NOTICE_MARKER)
  if (start === -1) return content

  const searchFrom = start + INTERNAL_NOTICE_MARKER.length
  const jsonMatch = content.slice(searchFrom).match(RECENT_PREFS_JSON_FENCE_RE)
  if (jsonMatch?.index != null) {
    const end = searchFrom + jsonMatch.index + jsonMatch[0].length
    const after = content.slice(end).replace(/^\s+/, '')
    return (content.slice(0, start) + after).trimStart()
  }

  const infoIdx = content.indexOf(PATIENT_INFO_HEADER, searchFrom)
  if (infoIdx !== -1) {
    let pos = infoIdx + PATIENT_INFO_HEADER.length
    while (pos < content.length && '：:\n\r \t'.includes(content[pos])) {
      pos += 1
    }

    while (pos < content.length) {
      const lineEnd = content.indexOf('\n', pos)
      const end = lineEnd === -1 ? content.length : lineEnd
      const line = content.slice(pos, end)
      if (!line.trim()) {
        pos = end < content.length ? end + 1 : content.length
        continue
      }
      if (looksLikeLeakedPatientSummaryLine(line)) {
        pos = end < content.length ? end + 1 : content.length
        continue
      }
      break
    }

    const after = content.slice(pos).replace(/^\s+/, '')
    return (content.slice(0, start) + after).trimStart()
  }

  const endIdx = content.indexOf(INTERNAL_NOTICE_END, searchFrom)
  if (endIdx === -1) {
    return content.slice(0, start).trimEnd()
  }

  let end = endIdx + INTERNAL_NOTICE_END.length
  const rest = content.slice(end)
  const trimmed = rest.trimStart()
  if (trimmed.startsWith('当前问诊患者姓名')) {
    const lineEnd = rest.indexOf('\n', rest.length - trimmed.length)
    if (lineEnd !== -1) {
      end += lineEnd + 1
    } else {
      end = content.length
    }
  }

  const after = content.slice(end).replace(/^\s+/, '')
  return (content.slice(0, start) + after).trimStart()
}

function stripRecentPreferencesJson(content: string): string {
  return content
    .replace(RECENT_PREFS_JSON_FENCE_RE, '')
    .replace(RECENT_PREFS_JSON_BARE_RE, '')
    .replace(RECENT_PREFS_JSON_INCOMPLETE_FENCE_RE, '')
    .replace(RECENT_PREFS_JSON_INCOMPLETE_BARE_RE, '')
    .replace(/[`\s]+$/, '')
}

/** 从 Agent 回复正文中移除内部会话上下文（含流式未闭合时从起始处截断） */
export function stripSystemContextDisplay(content: string): string {
  let cleaned = stripContextBlock(content)
  while (true) {
    const nextCleaned = stripRecentPreferencesJson(stripInternalNoticeBlock(cleaned))
    if (nextCleaned === cleaned) break
    cleaned = nextCleaned
  }
  return cleaned.trim()
}

/** 追加 token 并过滤系统上下文，供流式 onToken 使用 */
export function appendAgentContent(prev: string, token: string): string {
  return stripSystemContextDisplay(`${prev}${token}`)
}

/** 复制/导出时使用，与展示逻辑一致 */
export function getAgentVisibleContent(content: string): string {
  return stripSystemContextDisplay(content).trim()
}
