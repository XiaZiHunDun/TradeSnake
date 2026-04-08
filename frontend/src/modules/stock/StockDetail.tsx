import { useParams, useNavigate } from 'react-router-dom'
import { useStockDetail } from '../../shared/hooks/useApi'
import { Button } from '../../shared/components/atoms'
import { PriceDisplay } from '../../shared/components/molecules'

export function StockDetail() {
  const { code } = useParams<{ code: string }>()
  const navigate = useNavigate()
  const { data, isLoading, error } = useStockDetail(code || '')

  if (!code) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">未指定股票代码</p>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">加载中...</p>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="text-center py-12">
        <p className="text-red-500 mb-4">加载失败</p>
        <Button onClick={() => navigate('/')}>返回战力榜</Button>
      </div>
    )
  }

  const isUp = data.change_pct >= 0

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* 头部 */}
      <div className="flex items-start justify-between">
        <div>
          <button
            onClick={() => navigate(-1)}
            className="text-sm text-blue-500 hover:text-blue-600 mb-2"
          >
            ← 返回
          </button>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            {data.name}
          </h1>
          <p className="text-gray-500">{data.code}</p>
        </div>
        <Button variant="primary">+ 加自选</Button>
      </div>

      {/* 价格 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
        <PriceDisplay
          price={data.price}
          changePercent={data.change_pct}
          size="lg"
          showAbsolute={false}
        />
      </div>

      {/* 战力数据 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">战力分析</h2>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <ScoreCard label="综合战力" value={data.total_cp} color="text-blue-600" />
          <ScoreCard label="成长分" value={data.growth_score} color="text-purple-600" />
          <ScoreCard label="价值分" value={data.value_score} color="text-orange-600" />
          <ScoreCard label="质量分" value={data.quality_score} color="text-cyan-600" />
          <ScoreCard label="动量分" value={data.momentum_score} color="text-green-600" />
        </div>
      </div>

      {/* 基本面 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">基本面</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <InfoCard label="市盈率(PE)" value={data.pe?.toFixed(2) || '-'} />
          <InfoCard label="市净率(PB)" value={data.pb?.toFixed(2) || '-'} />
          <InfoCard
            label="总市值"
            value={data.market_cap ? `${(data.market_cap / 100000000).toFixed(2)}亿` : '-'}
          />
          <InfoCard
            label="流通市值"
            value={data.float_market_cap ? `${(data.float_market_cap / 100000000).toFixed(2)}亿` : '-'}
          />
          <InfoCard label="换手率" value={data.turnover_rate ? `${data.turnover_rate.toFixed(2)}%` : '-'} />
          <InfoCard
            label="成交额"
            value={data.amount ? `${(data.amount / 100000000).toFixed(2)}亿` : '-'}
          />
          <InfoCard
            label="最高"
            value={data.high ? data.high.toFixed(2) : '-'}
          />
          <InfoCard
            label="最低"
            value={data.low ? data.low.toFixed(2) : '-'}
          />
        </div>
      </div>

      {/* 财务数据 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">财务指标</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <InfoCard
            label="净利润增长"
            value={data.net_profit_growth ? `${data.net_profit_growth.toFixed(2)}%` : '-'}
            color={data.net_profit_growth && data.net_profit_growth > 0 ? 'text-red-500' : 'text-green-500'}
          />
          <InfoCard
            label="营收增长"
            value={data.revenue_growth ? `${data.revenue_growth.toFixed(2)}%` : '-'}
            color={data.revenue_growth && data.revenue_growth > 0 ? 'text-red-500' : 'text-green-500'}
          />
          <InfoCard label="ROE" value={data.roe ? `${data.roe.toFixed(2)}%` : '-'} />
          <InfoCard
            label="毛利率"
            value={data.gross_margin ? `${data.gross_margin.toFixed(2)}%` : '-'}
          />
        </div>
      </div>
    </div>
  )
}

function ScoreCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="text-center">
      <div className={`text-3xl font-bold font-mono ${color}`}>{value.toFixed(1)}</div>
      <div className="text-sm text-gray-500 mt-1">{label}</div>
    </div>
  )
}

function InfoCard({
  label,
  value,
  color,
}: {
  label: string
  value: string
  color?: string
}) {
  return (
    <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className={`text-lg font-semibold font-mono ${color || 'text-gray-900 dark:text-white'}`}>
        {value}
      </div>
    </div>
  )
}
