interface PercentageBarProps {
  value: number // -100 to 100
  maxValue?: number
  showLabel?: boolean
  height?: string
  className?: string
}

export function PercentageBar({
  value,
  maxValue = 10,
  showLabel = false,
  height = 'h-2',
  className = '',
}: PercentageBarProps) {
  const clampedValue = Math.max(-maxValue, Math.min(maxValue, value))
  const percentage = (clampedValue / maxValue) * 50
  const isPositive = clampedValue >= 0

  const colorClass = isPositive ? 'bg-red-500' : 'bg-green-500'

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div className={`flex-1 ${height} bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden`}>
        <div
          className={`${height} ${colorClass} rounded-full transition-all`}
          style={{ width: `${Math.abs(percentage)}%`, marginLeft: isPositive ? '50%' : 'auto' }}
        />
      </div>
      {showLabel && (
        <span className={`text-xs font-mono w-16 text-right ${isPositive ? 'text-red-500' : 'text-green-500'}`}>
          {isPositive ? '+' : ''}{clampedValue.toFixed(2)}%
        </span>
      )}
    </div>
  )
}
