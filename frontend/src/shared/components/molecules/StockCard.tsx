import type { StockCP } from '../../types'

interface StockCardProps {
  stock: StockCP
  onClick?: (code: string) => void
  onAddWatchlist?: (code: string) => void
  size?: 'sm' | 'md' | 'lg'
  showCP?: boolean
  className?: string
}

export function StockCard({
  stock,
  onClick,
  onAddWatchlist,
  size = 'md',
  showCP = true,
  className = '',
}: StockCardProps) {
  const isUp = stock.change >= 0

  const sizeStyles = {
    sm: 'text-sm p-2',
    md: 'text-base p-3',
    lg: 'text-lg p-4',
  }

  const colorClass = isUp ? 'text-red-500' : 'text-green-500'
  const bgClass = isUp ? 'bg-red-500/10' : 'bg-green-500/10'

  return (
    <div
      className={`
        rounded-lg border border-gray-200 dark:border-gray-700
        bg-white dark:bg-gray-800
        hover:shadow-md transition-shadow cursor-pointer
        ${sizeStyles[size]} ${className}
      `}
      onClick={() => onClick?.(stock.code)}
    >
      <div className="flex justify-between items-start mb-2">
        <div>
          <div className="font-semibold text-gray-900 dark:text-gray-100">{stock.name}</div>
          <div className="text-xs text-gray-500">{stock.code}</div>
        </div>
        {showCP && (
          <div className="text-right">
            <div className="text-lg font-bold text-blue-600 dark:text-blue-400">
              {stock.total_cp.toFixed(1)}
            </div>
            <div className="text-xs text-gray-500">战力</div>
          </div>
        )}
      </div>

      <div className="flex justify-between items-end">
        <div className={`font-mono font-semibold ${colorClass}`}>
          {stock.price.toFixed(2)}
        </div>
        <div className={`text-right px-2 py-1 rounded ${bgClass} ${colorClass}`}>
          <div className="font-mono text-sm">
            {isUp ? '+' : ''}{stock.change.toFixed(2)}
          </div>
          <div className="font-mono text-xs">
            {isUp ? '+' : ''}{stock.changePercent.toFixed(2)}%
          </div>
        </div>
      </div>

      {onAddWatchlist && (
        <button
          onClick={(e) => {
            e.stopPropagation()
            onAddWatchlist(stock.code)
          }}
          className="mt-2 w-full py-1 text-sm text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded"
        >
          + 加自选
        </button>
      )}
    </div>
  )
}
