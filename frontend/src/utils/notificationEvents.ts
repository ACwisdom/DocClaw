export const NOTIFICATIONS_CHANGED = 'docclaw:notifications-changed'

export function emitNotificationsChanged() {
  window.dispatchEvent(new Event(NOTIFICATIONS_CHANGED))
}
