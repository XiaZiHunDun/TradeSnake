// 骨架屏组件
export function SkeletonTable({ rows = 5, cols = 8 }) {
  return (
    <div className="animate-pulse">
      {/* 表头 */}
      <div className="flex gap-4 px-4 py-3 border-b border-border-dark">
        {Array.from({ length: cols }).map((_, i) => (
          <div key={i} className={`bg-gray-700 rounded ${i === 0 ? 'w-8 h-4' : i === 3 ? 'w-24 h-4' : 'flex-1 h-4'}`} />
        ))}
      </div>
      {/* 表格行 */}
      {Array.from({ length: rows }).map((_, rowIdx) => (
        <div key={rowIdx} className="flex gap-4 px-4 py-4 border-b border-border-dark/50">
          {Array.from({ length: cols }).map((_, colIdx) => (
            <div
              key={colIdx}
              className={`bg-gray-700/50 rounded ${colIdx === 0 ? 'w-8 h-4' : colIdx === 3 ? 'w-24 h-4' : 'flex-1 h-4'}`}
            />
          ))}
        </div>
      ))}
    </div>
  )
}

export function SkeletonCard() {
  return (
    <div className="bg-card-bg rounded-xl border border-border-dark p-6 animate-pulse">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-gray-700 rounded-lg" />
          <div>
            <div className="w-24 h-5 bg-gray-700 rounded mb-2" />
            <div className="w-16 h-3 bg-gray-700 rounded" />
          </div>
        </div>
        <div className="w-16 h-8 bg-gray-700 rounded" />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-deep-night rounded-lg p-4">
          <div className="w-12 h-4 bg-gray-700 rounded mb-2" />
          <div className="w-20 h-6 bg-gray-700 rounded" />
        </div>
        <div className="bg-deep-night rounded-lg p-4">
          <div className="w-12 h-4 bg-gray-700 rounded mb-2" />
          <div className="w-20 h-6 bg-gray-700 rounded" />
        </div>
      </div>
    </div>
  )
}

export function SkeletonChart({ height = '200px' }) {
  return (
    <div className="bg-deep-night rounded-lg p-4 animate-pulse" style={{ height }}>
      <div className="flex items-end justify-center gap-2 h-full">
        {[40, 60, 45, 80, 65, 70, 55, 75, 50, 85].map((h, i) => (
          <div key={i} className="w-6 bg-gray-700 rounded-t" style={{ height: `${h}%` }} />
        ))}
      </div>
    </div>
  )
}
