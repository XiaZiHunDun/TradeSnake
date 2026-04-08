import { ReactNode } from 'react'

interface TagProps {
  children: ReactNode
  color?: string
  onRemove?: () => void
  className?: string
}

export function Tag({ children, color, onRemove, className = '' }: TagProps) {
  return (
    <span
      className={`
        inline-flex items-center gap-1 px-2 py-1 rounded-md text-sm
        bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300
        ${className}
      `}
      style={color ? { backgroundColor: `${color}20`, color } : undefined}
    >
      {children}
      {onRemove && (
        <button
          onClick={(e) => {
            e.stopPropagation()
            onRemove()
          }}
          className="ml-1 hover:opacity-70"
        >
          ×
        </button>
      )}
    </span>
  )
}
