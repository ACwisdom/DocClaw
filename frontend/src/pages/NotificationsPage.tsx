import { useEffect, useState } from 'react'
import { api } from '../api'
import PageTopbar from '../components/PageTopbar'
import type { Notification } from '../types'
import { emitNotificationsChanged } from '../utils/notificationEvents'

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([])

  useEffect(() => {
    api.getNotifications().then(setNotifications).catch(console.error)
  }, [])

  const handleRead = async (id: string) => {
    await api.markRead(id)
    setNotifications((prev) => prev.map((n) => n.id === id ? { ...n, is_read: true } : n))
    emitNotificationsChanged()
  }

  const handleReadAll = async () => {
    await api.markAllRead()
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })))
    emitNotificationsChanged()
  }

  const unreadCount = notifications.filter((n) => !n.is_read).length

  return (
    <div className="med-page">
      <PageTopbar />
      <div className="page-body">
        <div className="page-header-row">
          <div>
            <span className="page-kicker">通知</span>
            <h1 className="page-title">
              通知中心
              {unreadCount > 0 && (
                <span className="notification-page-unread-count">{unreadCount} 条未读</span>
              )}
            </h1>
          </div>
          <button className="secondary-button" onClick={handleReadAll} disabled={unreadCount === 0}>
            全部已读
          </button>
        </div>
        {unreadCount > 0 && (
          <div className="notification-unread-banner" role="status">
            <span className="material-symbols-outlined">mark_email_unread</span>
            <span>您有 {unreadCount} 条未读通知，请及时查看</span>
          </div>
        )}
        <div className="notification-list">
          {notifications.map((n) => (
            <article
              key={n.id}
              className={`notification-card${n.is_read ? '' : ' unread'}`}
              onClick={() => handleRead(n.id)}
            >
              <div className="notification-card-lead" aria-hidden="true">
                {n.is_read ? (
                  <span className="material-symbols-outlined notification-read-icon">drafts</span>
                ) : (
                  <span className="notification-unread-dot" />
                )}
              </div>
              <div className="notification-card-body">
                <div className="notification-card-header">
                  <h4>{n.title}</h4>
                  {!n.is_read && <span className="notification-unread-badge">未读</span>}
                </div>
                <p>{n.content}</p>
                <span className="notification-time">{new Date(n.created_at).toLocaleString('zh-CN')}</span>
              </div>
            </article>
          ))}
        </div>
      </div>
    </div>
  )
}
