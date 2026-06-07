import Modal from './Modal'

interface ConfirmDialogProps {
  title: string
  message: string
  detail?: string
  confirmLabel?: string
  cancelLabel?: string
  danger?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export default function ConfirmDialog({
  title,
  message,
  detail,
  confirmLabel = '确认',
  cancelLabel = '取消',
  danger,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <Modal
      title={title}
      onClose={onCancel}
      footer={
        <>
          <button type="button" className="secondary-button" onClick={onCancel}>{cancelLabel}</button>
          <button
            type="button"
            className={danger ? 'danger-button' : 'primary-button'}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </>
      }
    >
      <p className="confirm-message">{message}</p>
      {detail && <p className="confirm-detail">{detail}</p>}
    </Modal>
  )
}
