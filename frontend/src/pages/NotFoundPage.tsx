import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <div className="med-page">
      <div className="page-body">
        <div className="empty-card">
          <span className="page-kicker">未找到</span>
          <h1 className="page-title">未找到页面</h1>
          <p className="page-subtitle">当前页面不存在。</p>
          <Link to="/queue" className="primary-button">返回首页</Link>
        </div>
      </div>
    </div>
  )
}
