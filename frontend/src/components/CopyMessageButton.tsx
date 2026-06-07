import { useCallback, useEffect, useRef, useState } from 'react'

interface CopyMessageButtonProps {
  text: string
  className?: string
}

export default function CopyMessageButton({ text, className = 'copy-btn' }: CopyMessageButtonProps) {
  const [copied, setCopied] = useState(false)
  const timerRef = useRef<number | undefined>(undefined)

  useEffect(
    () => () => {
      if (timerRef.current) window.clearTimeout(timerRef.current)
    },
    [],
  )

  const handleCopy = useCallback(async () => {
    const value = text.trim()
    if (!value) return
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      if (timerRef.current) window.clearTimeout(timerRef.current)
      timerRef.current = window.setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }, [text])

  return (
    <button
      type="button"
      className={`${className}${copied ? ' copy-btn-done' : ''}`}
      onClick={handleCopy}
      aria-label={copied ? '已复制' : '复制消息'}
    >
      {copied ? (
        <>
          <span className="material-symbols-outlined copy-btn-icon">check</span>
          已复制
        </>
      ) : (
        '复制消息'
      )}
    </button>
  )
}
