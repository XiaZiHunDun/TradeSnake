interface PriceDisplayProps {
  price: number
  change?: number
  changePercent?: number
  previousPrice?: number
  size?: 'sm' | 'md' | 'lg'
  showAbsolute?: boolean
  animated?: boolean
  className?: string
}

export function PriceDisplay({
  price,
  change,
  changePercent,
  previousPrice,
  size = 'md',
  showAbsolute = true,
  animated = false,
  className = '',
}: PriceDisplayProps) {
  const displayChange = change ?? (previousPrice ? price - previousPrice : 0)
  const displayPercent = changePercent ?? (previousPrice ? ((price - previousPrice) / previousPrice) * 100 : 0)
  const isUp = displayChange >= 0

  const sizeStyles = {
    sm: 'text-sm',
    md: 'text-base',
    lg: 'text-xl',
  }

  const colorClass = isUp ? 'text-red-500' : 'text-green-500'
  const bgClass = isUp ? 'bg-red-500/10' : 'bg-green-500/10'
  const arrow = isUp ? '▲' : '▼'

  return (
    <div className={`inline-flex items-center gap-2 ${className}`}>
      <span className={`font-mono font-bold ${sizeStyles[size]} ${colorClass}`}>
        {price.toFixed(2)}
      </span>
      {showAbsolute && (
        <span className={`font-mono ${colorClass}`}>
          {isUp ? '+' : ''}{displayChange.toFixed(2)}
        </span>
      )}
      <span className={`px-2 py-0.5 rounded font-mono ${bgClass} ${colorClass} ${sizeStyles[size]}`}>
        {arrow} {Math.abs(displayPercent).toFixed(2)}%
      </span>
      {animated && (
        <span className="animate-pulse">↻</span>
      )}
    </div>
  )
}
