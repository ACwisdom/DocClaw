import type { Dispatch, SetStateAction } from 'react'

import type { AgentTraceStep, Message } from '../types'

export function appendAgentTraceStep(
  setAgentMessages: Dispatch<SetStateAction<Message[]>>,
  assistantMessageId: string,
  step: Omit<AgentTraceStep, 'id' | 'created_at'>,
) {
  const fullStep: AgentTraceStep = {
    ...step,
    id: `trace-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    created_at: new Date().toISOString(),
  }

  setAgentMessages((prev) => {
    let targetIdx = prev.findIndex((m) => m.id === assistantMessageId)
    if (targetIdx < 0) {
      for (let i = prev.length - 1; i >= 0; i -= 1) {
        if (prev[i].role === 'assistant' && prev[i].streaming) {
          targetIdx = i
          break
        }
      }
    }
    if (targetIdx < 0) return prev

    return prev.map((msg, i) =>
      i === targetIdx
        ? { ...msg, agent_trace: [...(msg.agent_trace ?? []), fullStep] }
        : msg,
    )
  })
}

export function finalizeAgentTrace(
  setAgentMessages: Dispatch<SetStateAction<Message[]>>,
  assistantMessageId: string,
  patch: Partial<Message> = {},
) {
  setAgentMessages((prev) =>
    prev.map((msg) =>
      msg.id === assistantMessageId
        ? { ...msg, ...patch, streaming: false }
        : msg,
    ),
  )
}
