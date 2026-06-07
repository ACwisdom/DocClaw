import PageTopbar from '../components/PageTopbar'

export default function SettingsPage() {
  return (
    <div className="med-page">
      <PageTopbar />
      <div className="page-body">
        <span className="page-kicker">设置</span>
        <h1 className="page-title">设置</h1>
        <div className="form-card">
          <h3>医生信息</h3>
          <p>李医生 · 主治医师 · 呼吸内科门诊</p>
          <h3>AI 配置</h3>
          <p>智能助理已链接，默认使用「智能病历助手」技能。</p>
          <h3>科室设置</h3>
          <p>呼吸内科门诊 · 市一院</p>
        </div>
      </div>
    </div>
  )
}
