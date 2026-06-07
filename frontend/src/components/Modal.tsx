import { useEffect, type ReactNode } from 'react'

interface ModalProps {
  title: string
  subtitle?: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  wide?: boolean
}

export default function Modal({ title, subtitle, onClose, children, footer, wide }: ModalProps) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="modal-overlay" onClick={onClose} role="presentation">
      <div
        className={`modal-panel${wide ? ' modal-wide' : ''}`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
      >
        <header className="modal-header">
          <div>
            <h3 id="modal-title">{title}</h3>
            {subtitle && <p className="modal-subtitle">{subtitle}</p>}
          </div>
          <button type="button" className="modal-close" onClick={onClose} aria-label="关闭">
            <span className="material-symbols-outlined">close</span>
          </button>
        </header>
        <div className="modal-body">{children}</div>
        {footer && <footer className="modal-footer">{footer}</footer>}
      </div>
    </div>
  )
}
