import PageTopbar from '../components/PageTopbar'

export default function HelpPage() {
  return (
    <div className="med-page">
      <PageTopbar />
      <div className="page-body">
        <span className="page-kicker">帮助</span>
        <h1 className="page-title">帮助</h1>
        <div className="form-card">
          <h3>快速入门</h3>
          <ol>
            <li>在「患者队列」中选择患者，点击「开始问诊」进入问诊工作台</li>
            <li>问诊过程中 AI 会实时辅助病历结构化整理</li>
            <li>在「个人技能」中管理已启用的 AI 能力</li>
            <li>在「技能广场」中获取其他医生分享的技能，也可浏览平台开放技能</li>
            <li>在「随访计划」中创建和管理计划性任务</li>
          </ol>
          <h3>技能类型</h3>
          <ul>
            <li><strong>实时性任务</strong>：门诊看诊时病历结构化、检查结果标红等</li>
            <li><strong>计划性任务</strong>：创建随访计划、执行随访任务等</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
