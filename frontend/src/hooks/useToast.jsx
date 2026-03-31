import { useState, useEffect, useCallback } from 'react'

let toastId = 0
let addToastFn = null

export function useToast() {
  const [toasts, setToasts] = useState([])

  const addToast = useCallback((message, type = 'info', duration = 3000) => {
    const id = ++toastId
    setToasts(prev => [...prev, { id, message, type }])

    if (duration > 0) {
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id))
      }, duration)
    }

    return id
  }, [])

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  return { toasts, addToast, removeToast }
}

export function ToastContainer() {
  const [toasts, setToasts] = useState([])

  useEffect(() => {
    addToastFn = (message, type) => {
      const id = ++toastId
      setToasts(prev => [...prev, { id, message, type }])
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id))
      }, 3000)
    }
    return () => {
      addToastFn = null
    }
  }, [])

  if (toasts.length === 0) return null

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map(toast => (
        <div
          key={toast.id}
          className={`px-4 py-3 rounded-lg shadow-lg animate-slide-in ${
            toast.type === 'success' ? 'bg-green-500/90 text-white' :
            toast.type === 'error' ? 'bg-red-500/90 text-white' :
            toast.type === 'warning' ? 'bg-yellow-500/90 text-white' :
            'bg-accent-blue/90 text-white'
          }`}
        >
          <p className="font-medium">{toast.message}</p>
        </div>
      ))}
    </div>
  )
}

// 全局Toast函数
export function showToast(message, type = 'info') {
  if (addToastFn) {
    addToastFn(message, type)
  }
}
