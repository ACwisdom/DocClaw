import { useCallback, useEffect, useState } from 'react'

import { api } from '../api'
import { NOTIFICATIONS_CHANGED } from '../utils/notificationEvents'

interface PageTopbarProps {
  searchPlaceholder?: string
  searchValue?: string
  onSearchChange?: (v: string) => void
}

export default function PageTopbar({
  searchPlaceholder = '搜索...',
  searchValue = '',
  onSearchChange,
}: PageTopbarProps) {
  const [unreadCount, setUnreadCount] = useState(0)

  const refreshUnreadCount = useCallback(() => {
    api
      .getNotifications()
      .then((items) => setUnreadCount(items.filter((n) => !n.is_read).length))
      .catch(console.error)
  }, [])

  useEffect(() => {
    refreshUnreadCount()
    window.addEventListener(NOTIFICATIONS_CHANGED, refreshUnreadCount)
    window.addEventListener('focus', refreshUnreadCount)
    return () => {
      window.removeEventListener(NOTIFICATIONS_CHANGED, refreshUnreadCount)
      window.removeEventListener('focus', refreshUnreadCount)
    }
  }, [refreshUnreadCount])

  const badgeLabel = unreadCount > 99 ? '99+' : String(unreadCount)

  return (
    <header className="page-topbar">
      <div className="page-topbar-brand">医疗 AI 工作台</div>
      <div className="page-topbar-actions">
        {onSearchChange && (
          <label className="top-search">
            <span className="material-symbols-outlined">search</span>
            <input
              placeholder={searchPlaceholder}
              value={searchValue}
              onChange={(e) => onSearchChange(e.target.value)}
            />
          </label>
        )}
        <a
          className="icon-link icon-link-with-badge"
          href="/notifications"
          aria-label={unreadCount > 0 ? `${unreadCount} 条未读通知` : '通知中心'}
        >
          <span className="material-symbols-outlined">notifications</span>
          {unreadCount > 0 && (
            <span className="topbar-notification-badge" aria-hidden="true">
              {badgeLabel}
            </span>
          )}
        </a>
        <a className="icon-link" href="/settings">
          <span className="material-symbols-outlined">settings</span>
        </a>
        <a className="avatar-badge" href="/settings">李</a>
      </div>
    </header>
  )
}
