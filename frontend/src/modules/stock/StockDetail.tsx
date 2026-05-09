import { useParams, useNavigate } from 'react-router-dom'
import { useStockDetail, useGainPredictionStock, useProbabilityPredictionStock } from '../../shared/hooks/useApi'
import { Button } from '../../shared/components/atoms'
import { PriceDisplay } from '../../shared/components/molecules'

export function StockDetail() {
  const { code } = useParams<{ code: string }>()
  const navigate = useNavigate()
  const { data, isLoading, error } = useStockDetail(code || '')
  const { data: gainPrediction } = useGainPredictionStock(code || '')
  const { data: probPrediction } = useProbabilityPredictionStock(code || '')

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

      {/* 预测分析 v19.8 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">预测分析</h2>

        {/* 涨幅预测 */}
        <div className="mb-6">
          <h3 className="text-sm font-medium text-gray-500 mb-3">涨幅预测</h3>
          {gainPrediction ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <PredictionCard
                label="3日预测涨幅"
                value={gainPrediction.predicted_gain_3d}
                unit="%"
                confidence={gainPrediction.confidence}
                color={gainPrediction.predicted_gain_3d >= 0 ? 'red' : 'green'}
              />
              <PredictionCard
                label="5日预测涨幅"
                value={gainPrediction.predicted_gain_5d}
                unit="%"
                confidence={gainPrediction.confidence}
                color={gainPrediction.predicted_gain_5d >= 0 ? 'red' : 'green'}
              />
              <PredictionCard
                label="3日置信区间"
                value={gainPrediction.confidence_interval_3d[0]}
                value2={gainPrediction.confidence_interval_3d[1]}
                unit="%"
                color="gray"
              />
              <PredictionCard
                label="5日置信区间"
                value={gainPrediction.confidence_interval_5d[0]}
                value2={gainPrediction.confidence_interval_5d[1]}
                unit="%"
                color="gray"
              />
            </div>
          ) : (
            <div className="text-center py-4 text-gray-500 text-sm">
              暂无预测数据（K线数据不足）
            </div>
          )}
        </div>

        {/* 上涨概率 */}
        <div>
          <h3 className="text-sm font-medium text-gray-500 mb-3">上涨概率</h3>
          {probPrediction ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <PredictionCard
                label="3日上涨概率"
                value={probPrediction.up_probability_3d * 100}
                unit="%"
                color={probPrediction.up_probability_3d >= 0.5 ? 'red' : 'green'}
                isPercent
              />
              <PredictionCard
                label="5日上涨概率"
                value={probPrediction.up_probability_5d * 100}
                unit="%"
                color={probPrediction.up_probability_5d >= 0.5 ? 'red' : 'green'}
                isPercent
              />
              <div className="text-center bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3">
                <div className="text-xs text-gray-500 mb-1">风险等级</div>
                <div className={`text-2xl font-bold ${
                  probPrediction.risk_level === 'high' ? 'text-red-500' :
                  probPrediction.risk_level === 'medium' ? 'text-yellow-500' : 'text-green-500'
                }`}>
                  {probPrediction.risk_level === 'high' ? '高' :
                   probPrediction.risk_level === 'medium' ? '中' : '低'}
                </div>
              </div>
              <PredictionCard
                label="模型版本"
                value={0}
                displayText={probPrediction.model_version || 'rule_v19.8'}
                color="gray"
              />
            </div>
          ) : (
            <div className="text-center py-4 text-gray-500 text-sm">
              暂无概率数据（K线数据不足）
            </div>
          )}
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

interface PredictionCardProps {
  label: string
  value: number
  value2?: number
  unit?: string
  confidence?: number
  color?: 'red' | 'green' | 'gray' | 'blue'
  displayText?: string
  isPercent?: boolean
}

function PredictionCard({ label, value, value2, unit = '', confidence, color = 'gray', displayText, isPercent }: PredictionCardProps) {
  const colorClass = color === 'red' ? 'text-red-500' :
                     color === 'green' ? 'text-green-500' :
                     color === 'blue' ? 'text-blue-500' : 'text-gray-900 dark:text-white'

  const bgClass = color === 'red' ? 'bg-red-50 dark:bg-red-900/20' :
                  color === 'green' ? 'bg-green-50 dark:bg-green-900/20' :
                  color === 'blue' ? 'bg-blue-50 dark:bg-blue-900/20' : 'bg-gray-50 dark:bg-gray-700/50'

  return (
    <div className={`${bgClass} rounded-lg p-3 text-center`}>
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      {displayText ? (
        <div className="text-sm font-medium font-mono text-gray-900 dark:text-white truncate">
          {displayText}
        </div>
      ) : value2 !== undefined ? (
        <div className={`text-lg font-bold font-mono ${colorClass}`}>
          [{value.toFixed(1)}, {value2.toFixed(1)}]{unit}
        </div>
      ) : (
        <div className={`text-lg font-bold font-mono ${colorClass}`}>
          {isPercent ? value.toFixed(0) : value.toFixed(2)}{unit}
        </div>
      )}
      {confidence !== undefined && (
        <div className="text-xs text-gray-400 mt-1">
          置信度: {(confidence * 100).toFixed(0)}%
        </div>
      )}
    </div>
  )
}
