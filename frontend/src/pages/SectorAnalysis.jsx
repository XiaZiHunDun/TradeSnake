import { useState, useEffect } from 'react'
import { BarChart3, TrendingUp, PieChart, Crown } from 'lucide-react'
import ReactECharts from 'echarts-for-react'

function SectorAnalysis() {
  const [sectorData, setSectorData] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedSector, setSelectedSector] = useState(null)
  const [sectorStocks, setSectorStocks] = useState([])

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    setLoading(true)
    try {
      // 获取所有股票数据
      const res = await fetch('/api/cp/top?limit=200')
      if (res.ok) {
        const json = await res.json()
        processSectorData(json.data || [])
      }
    } catch (e) {
      console.error('Failed to fetch data:', e)
    }
    setLoading(false)
  }

  // 模拟行业分类（实际项目中应该从API获取真实行业数据）
  const classifySector = (code) => {
    // 简单模拟分类
    const prefix = code.substring(0, 3)
    if (['600', '601', '603'].includes(prefix)) {
      // 上交所主板
      const num = parseInt(code.substring(3))
      if (num < 100) return '金融地产'
      if (num < 200) return '消费'
      if (num < 300) return '医药'
      if (num < 400) return '科技'
      if (num < 500) return '工业'
      return '周期'
    } else if (['000', '001', '002', '003'].includes(prefix)) {
      // 深交所
      const num = parseInt(code.substring(3))
      if (num < 100) return '新能源'
      if (num < 200) return '医药'
      if (num < 300) return '消费'
      if (num < 400) return '科技'
      if (num < 500) return '金融地产'
      return '工业'
    } else if (['300'].includes(prefix)) {
      return '科技'
    }
    return '其他'
  }

  const processSectorData = (stocks) => {
    // 按行业分组
    const sectors = {}
    stocks.forEach(stock => {
      const sector = classifySector(stock.code)
      if (!sectors[sector]) {
        sectors[sector] = {
          name: sector,
          stocks: [],
          totalCP: 0,
          avgCP: 0,
          count: 0,
          highCPCount: 0,
          avgChange: 0
        }
      }
      sectors[sector].stocks.push(stock)
      sectors[sector].totalCP += stock.total_cp
      sectors[sector].count++
      if (stock.total_cp >= 70) sectors[sector].highCPCount++
      sectors[sector].avgChange += stock.change_pct
    })

    // 计算平均值
    Object.values(sectors).forEach(sector => {
      sector.avgCP = sector.totalCP / sector.count
      sector.avgChange = sector.avgChange / sector.count
    })

    // 转换为数组并排序
    const sortedSectors = Object.values(sectors).sort((a, b) => b.avgCP - a.avgCP)
    setSectorData(sortedSectors)
  }

  // 行业战力分布图
  const getSectorCPChart = () => {
    if (sectorData.length === 0) return {}
    return {
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: {
        type: 'category',
        data: sectorData.map(s => s.name),
        axisLine: { lineStyle: { color: '#374151' } },
        axisLabel: { color: '#9ca3af', rotate: 30 }
      },
      yAxis: {
        type: 'value',
        name: '平均战力',
        axisLine: { show: false },
        splitLine: { lineStyle: { color: '#374151' } },
        axisLabel: { color: '#9ca3af' }
      },
      series: [{
        type: 'bar',
        data: sectorData.map(s => ({
          value: s.avgCP.toFixed(1),
          itemStyle: {
            color: s.avgCP >= 70 ? '#22c55e' : s.avgCP >= 50 ? '#eab308' : '#ef4444',
            borderRadius: [4, 4, 0, 0]
          }
        })),
        barWidth: '50%',
        label: { show: true, position: 'top', color: '#fff', fontSize: 10 }
      }]
    }
  }

  // 行业股票数量分布
  const getSectorCountChart = () => {
    if (sectorData.length === 0) return {}
    return {
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        data: sectorData.map((s, i) => ({
          value: s.count,
          name: `${s.name}(${s.count})`,
          itemStyle: {
            color: ['#3b82f6', '#22c55e', '#eab308', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316'][i % 8]
          }
        })),
        emphasis: {
          label: { show: true, fontSize: 14, fontWeight: 'bold', color: '#fff' }
        },
        label: { show: false }
      }]
    }
  }

  // 高战力股票比例
  const getHighCPRatioChart = () => {
    if (sectorData.length === 0) return {}
    return {
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: {
        type: 'category',
        data: sectorData.map(s => s.name),
        axisLine: { lineStyle: { color: '#374151' } },
        axisLabel: { color: '#9ca3af', rotate: 30 }
      },
      yAxis: {
        type: 'value',
        name: '高战力比例(%)',
        axisLine: { show: false },
        splitLine: { lineStyle: { color: '#374151' } },
        axisLabel: { color: '#9ca3af', formatter: '{value}%' }
      },
      series: [{
        type: 'bar',
        data: sectorData.map(s => ((s.highCPCount / s.count) * 100).toFixed(1)),
        itemStyle: {
          color: '#22c55e',
          borderRadius: [4, 4, 0, 0]
        },
        barWidth: '50%'
      }]
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-accent-blue/30 border-t-accent-blue rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-400">加载行业数据...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-accent-blue" />
          行业战力分析
        </h2>
      </div>

      {/* 行业总览图表 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* 平均战力排名 */}
        <div className="bg-card-bg rounded-xl border border-border-dark p-4">
          <h3 className="font-bold text-white mb-4 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-green-500" />
            行业平均战力排名
          </h3>
          <ReactECharts option={getSectorCPChart()} style={{ height: '300px' }} />
        </div>

        {/* 股票数量分布 */}
        <div className="bg-card-bg rounded-xl border border-border-dark p-4">
          <h3 className="font-bold text-white mb-4 flex items-center gap-2">
            <PieChart className="w-4 h-4 text-blue-500" />
            行业股票数量分布
          </h3>
          <ReactECharts option={getSectorCountChart()} style={{ height: '300px' }} />
        </div>
      </div>

      {/* 高战力比例 */}
      <div className="bg-card-bg rounded-xl border border-border-dark p-4">
        <h3 className="font-bold text-white mb-4 flex items-center gap-2">
          <Crown className="w-4 h-4 text-yellow-500" />
          行业高战力股票比例
        </h3>
        <ReactECharts option={getHighCPRatioChart()} style={{ height: '250px' }} />
      </div>

      {/* 行业详情表格 */}
      <div className="bg-card-bg rounded-xl border border-border-dark overflow-hidden">
        <div className="px-4 py-3 border-b border-border-dark">
          <h3 className="font-bold text-white">行业详情</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border-dark text-left text-sm text-gray-400">
                <th className="px-4 py-3">行业</th>
                <th className="px-4 py-3 text-right">股票数</th>
                <th className="px-4 py-3 text-right">平均战力</th>
                <th className="px-4 py-3 text-right">高战力股票</th>
                <th className="px-4 py-3 text-right">高战力比例</th>
                <th className="px-4 py-3 text-right">平均涨跌幅</th>
              </tr>
            </thead>
            <tbody>
              {sectorData.map(sector => (
                <tr
                  key={sector.name}
                  className="border-b border-border-dark/50 hover:bg-white/5 transition-colors cursor-pointer"
                  onClick={() => { setSelectedSector(sector.name); setSectorStocks(sector.stocks) }}
                >
                  <td className="px-4 py-3">
                    <span className="font-bold text-white">{sector.name}</span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-gray-300">
                    {sector.count}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className={`cp-tag ${
                      sector.avgCP >= 70 ? 'cp-high' : sector.avgCP >= 50 ? 'cp-mid' : 'cp-low'
                    }`}>
                      {sector.avgCP.toFixed(1)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-green-500">
                    {sector.highCPCount}只
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-gray-300">
                    {((sector.highCPCount / sector.count) * 100).toFixed(1)}%
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className={`font-mono text-sm ${
                      sector.avgChange > 0 ? 'text-red-500' : sector.avgChange < 0 ? 'text-green-500' : 'text-gray-500'
                    }`}>
                      {sector.avgChange >= 0 ? '+' : ''}{sector.avgChange.toFixed(2)}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 选中行业的股票列表 */}
      {selectedSector && sectorStocks.length > 0 && (
        <div className="bg-card-bg rounded-xl border border-border-dark overflow-hidden">
          <div className="px-4 py-3 border-b border-border-dark flex items-center justify-between">
            <h3 className="font-bold text-white">{selectedSector} 股票列表</h3>
            <button
              onClick={() => { setSelectedSector(null); setSectorStocks([]) }}
              className="text-gray-400 hover:text-white"
            >
              关闭
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border-dark text-left text-sm text-gray-400">
                  <th className="px-4 py-3">股票</th>
                  <th className="px-4 py-3 text-right">战力值</th>
                  <th className="px-4 py-3 text-right">成长分</th>
                  <th className="px-4 py-3 text-right">价值分</th>
                  <th className="px-4 py-3 text-right">趋势分</th>
                  <th className="px-4 py-3 text-right">涨跌幅</th>
                </tr>
              </thead>
              <tbody>
                {sectorStocks.sort((a, b) => b.total_cp - a.total_cp).map(stock => (
                  <tr
                    key={stock.code}
                    className="border-b border-border-dark/50 hover:bg-white/5 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div>
                          <p className="font-bold text-white">{stock.name}</p>
                          <p className="text-xs text-gray-500">{stock.code}</p>
                        </div>
                        {stock.data_quality && (
                          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                            stock.data_quality === 'high' ? 'bg-green-400' :
                            stock.data_quality === 'medium' ? 'bg-yellow-400' : 'bg-gray-500'
                          }`} title={`数据质量: ${stock.data_quality === 'high' ? '高' : stock.data_quality === 'medium' ? '中' : '低'}`} />
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className={`cp-tag ${
                        stock.total_cp >= 70 ? 'cp-high' : stock.total_cp >= 50 ? 'cp-mid' : 'cp-low'
                      }`}>
                        {stock.total_cp.toFixed(1)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-gray-300">
                      {stock.growth_score.toFixed(1)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-gray-300">
                      {stock.value_score.toFixed(1)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-gray-300">
                      {stock.momentum_score.toFixed(1)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className={`font-mono text-sm ${
                        stock.change_pct > 0 ? 'text-red-500' : stock.change_pct < 0 ? 'text-green-500' : 'text-gray-500'
                      }`}>
                        {stock.change_pct >= 0 ? '+' : ''}{stock.change_pct.toFixed(2)}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

export default SectorAnalysis
