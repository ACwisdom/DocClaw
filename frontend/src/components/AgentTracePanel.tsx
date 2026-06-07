import type { AgentTraceStep } from '../types'
import { SUBAGENT_LABELS } from '../utils/agentLabels'

const STEP_ICONS: Record<string, string> = {
  tool_call: 'search',
  tool_result: 'check_circle',
  subagent: 'hub',
  status: 'pending',
  context: 'tune',
}

function buildTraceSummary(
  steps: AgentTraceStep[],
  streaming?: boolean,
  statusText?: string,
): string {
  if (!steps.length) {
    if (statusText) return statusText
    return streaming ? '正在分析…' : ''
  }

  const lookups = steps.filter((s) => s.kind === 'tool_call').length
  const subagents = steps.filter((s) => s.kind === 'subagent')
  const hasContext = steps.some((s) => s.kind === 'context')
  const parts: string[] = []

  if (hasContext) parts.push('会话上下文')
  if (lookups > 0) parts.push(`已查询 ${lookups} 项资料`)
  if (subagents.length > 0) {
    const labels = subagents.map(
      (s) => SUBAGENT_LABELS[s.agent_source ?? ''] ?? '专业模块',
    )
    parts.push(`已协同 ${[...new Set(labels)].join('、')}`)
  }
  if (streaming) {
    parts.push(statusText || '处理中…')
  }

  return parts.join(' · ') || '处理过程'
}

interface AgentTracePanelProps {
  steps: AgentTraceStep[]
  streaming?: boolean
  statusText?: string
  expanded: boolean
  onToggle: () => void
}

export default function AgentTracePanel({
  steps,
  streaming,
  statusText,
  expanded,
  onToggle,
}: AgentTracePanelProps) {
  const summary = buildTraceSummary(steps, streaming, statusText)
  if (!summary && steps.length === 0) return null

  return (
    <div className={`agent-trace-panel${expanded ? ' expanded' : ''}${streaming ? ' streaming' : ''}`}>
      <button type="button" className="agent-trace-toggle" onClick={onToggle} aria-expanded={expanded}>
        <span className="material-symbols-outlined agent-trace-lead-icon">psychology</span>
        <span className="agent-trace-summary">{summary}</span>
        {streaming && <span className="streaming-spinner agent-trace-spinner" />}
        <span className="material-symbols-outlined agent-trace-chevron">
          {expanded ? 'expand_less' : 'expand_more'}
        </span>
      </button>
      {expanded && (
        <ol className="agent-trace-steps">
          {steps.length === 0 && streaming && (
            <li className="agent-trace-step kind-status active">
              <span className="streaming-spinner agent-trace-step-icon" />
              <span>{statusText || '正在分析…'}</span>
            </li>
          )}
          {steps.map((step) => (
            <li key={step.id} className={`agent-trace-step kind-${step.kind}`}>
              <span className="material-symbols-outlined agent-trace-step-icon">
                {STEP_ICONS[step.kind] ?? 'info'}
              </span>
              <div className="agent-trace-step-body">
                <div className="agent-trace-step-head">
                  <span>{step.content}</span>
                  {step.agent_source && step.agent_source !== 'main' && (
                    <span className="agent-source-badge inline">
                      {SUBAGENT_LABELS[step.agent_source] ?? '专业模块'}
                    </span>
                  )}
                </div>
                {step.detail && (
                  <pre className="agent-trace-step-detail">{step.detail}</pre>
                )}
              </div>
            </li>
          ))}
          {streaming && statusText && (
            <li className="agent-trace-step kind-status active">
              <span className="streaming-spinner agent-trace-step-icon" />
              <span>{statusText}</span>
            </li>
          )}
        </ol>
      )}
    </div>
  )
}
