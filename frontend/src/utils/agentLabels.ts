export const SUBAGENT_LABELS: Record<string, string> = {
  'clinical-assistant': '临床辅助',
  'followup-executor': '随访执行',
  main: '主助理',
}

const TOOL_LABELS: Record<string, string> = {
  patient_list: '患者列表',
  patient_summary: '接诊概况',
  patient_get: '患者档案',
  patient_start_consult: '开始接诊',
  patient_complete_consult: '结束接诊',
  consult_get_messages: '问诊记录',
  consult_send_message: '问诊消息',
  followup_list_plans: '随访计划',
  followup_create_plan: '创建随访',
  followup_pending_tasks: '待办随访',
  followup_execute_task: '执行随访',
  skill_list: '技能列表',
  skill_get: '技能详情',
  notification_list: '消息通知',
  notification_create: '发送通知',
  his_queue_summary: 'HIS 门诊队列',
  his_get_outpatient_queue: 'HIS 排队列表',
  his_get_labs: '检查结果',
  his_get_history: '既往病史',
  his_write_record: '病历写入',
  read_file: '读取资料',
  write_file: '保存资料',
  task: '任务编排',
}

export function humanizeToolName(toolName: string): string {
  return TOOL_LABELS[toolName] ?? '业务数据'
}

export function toolCallLabel(toolName: string): string {
  return `正在查询${humanizeToolName(toolName)}…`
}

export function toolResultLabel(toolName: string): string {
  return `${humanizeToolName(toolName)}已返回`
}

export function subagentLabel(source: string): string {
  const name = SUBAGENT_LABELS[source] ?? '专业模块'
  return `已转交${name}处理`
}

export function friendlyAgentError(message: string): string {
  const lower = message.toLowerCase()
  if (lower.includes('not found') || lower.includes('404')) {
    return '智能助理服务暂不可用，请稍后重试或联系管理员'
  }
  if (lower.includes('503') || lower.includes('未就绪')) {
    return '智能助理正在准备中，请稍后重试'
  }
  if (lower.includes('network') || lower.includes('failed to fetch')) {
    return '网络连接异常，请检查网络后重试'
  }
  if (lower.includes('api key') || lower.includes('unauthorized')) {
    return '智能助理未正确配置，请联系管理员'
  }
  return '智能助理暂时无法完成请求，请稍后重试'
}
