import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Doctor } from '../types'

export default function AppLayout() {
  const [doctor, setDoctor] = useState<Doctor | null>(null)
  const location = useLocation()

  useEffect(() => {
    api.getDoctor().then(setDoctor).catch(console.error)
  }, [])

  const runtimeCopy = location.pathname.startsWith('/consult')
    ? '问诊进行中，门诊病历持续同步整理。'
    : '智能助理已就绪，可开始接诊或管理技能。'

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <NavLink to="/queue" className="sidebar-brand">
          <div className="sidebar-brand-mark">
            <span className="material-symbols-outlined">medical_services</span>
          </div>
          <div className="sidebar-brand-copy">
            <strong>医疗 AI 工作台</strong>
            <span>智能接诊辅助 · 呼吸内科门诊</span>
          </div>
        </NavLink>

        {doctor && (
          <div className="sidebar-doctor">
            <div className="sidebar-avatar">{doctor.avatar}</div>
            <div>
              <strong>{doctor.name}</strong>
              <span>{doctor.title} · {doctor.department}</span>
            </div>
          </div>
        )}

        <nav className="sidebar-nav" aria-label="主导航">
          <NavLink to="/queue" className={({ isActive }) => `sidebar-link${isActive ? ' sidebar-link-active' : ''}`}>
            <span className="sidebar-link-label">患者队列</span>
            <span className="sidebar-link-copy">待诊与问诊</span>
          </NavLink>
          <NavLink to="/skills" className={({ isActive }) => `sidebar-link${isActive ? ' sidebar-link-active' : ''}`}>
            <span className="sidebar-link-label">个人技能</span>
            <span className="sidebar-link-copy">我的技能</span>
          </NavLink>
          <NavLink to="/store" className={({ isActive }) => `sidebar-link${isActive ? ' sidebar-link-active' : ''}`}>
            <span className="sidebar-link-label">技能广场</span>
            <span className="sidebar-link-copy">共享发现</span>
          </NavLink>
          <NavLink to="/followup" className={({ isActive }) => `sidebar-link${isActive ? ' sidebar-link-active' : ''}`}>
            <span className="sidebar-link-label">随访计划</span>
            <span className="sidebar-link-copy">计划性任务</span>
          </NavLink>
        </nav>

        <div className="sidebar-runtime">
          <div className="runtime-chip linked">
            <span className="runtime-chip-dot" />
            <div>
              <strong>智能助理</strong>
              <span>在线</span>
            </div>
          </div>
          <p className="sidebar-runtime-copy">{runtimeCopy}</p>
        </div>

        <div className="sidebar-footer-links">
          <NavLink to="/notifications">通知</NavLink>
          <NavLink to="/settings">设置</NavLink>
          <NavLink to="/help">帮助</NavLink>
        </div>
      </aside>

      <section className="workspace-content">
        <Outlet />
      </section>
    </div>
  )
}
