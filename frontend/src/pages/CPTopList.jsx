import { useState, useEffect, useMemo, useCallback } from 'react'
import { TrendingUp, TrendingDown, Minus, ArrowUpDown, Star, GitCompare, X, RefreshCw, BarChart3, TrendingUp as TrendUp, Download, FileJson, FileSpreadsheet, ChevronDown, Shield } from 'lucide-react'
import ReactECharts from 'echarts-for-react'
import { useWatchlist } from '../hooks/useWatchlist'
import { SkeletonTable, SkeletonCard } from '../components/Skeleton'
import { exportToCSV, exportToJSON, exportToExcel } from '../utils/export'
import StockScreener from '../components/StockScreener'

function CPTopList() {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)
  const [updatedAt, setUpdatedAt] = useState(null)
  const [sortBy, setSortBy] = useState('total_cp') // total_cp, change_pct, pe, roe
  const [sortOrder, setSortOrder] = useState('desc') // desc, asc
  const [filterMode, setFilterMode] = useState('all') // all, watchlist
  const [cpRange, setCpRange] = useState('all') // all, high, mid, low
  const [boardFilter, setBoardFilter] = useState('main') // main, all, gem, star
  const [autoRefresh, setAutoRefresh] = useState(true) // 自动刷新开关
  const { watchlist, toggle, isInWatchlist } = useWatchlist()
  const [compareList, setCompareList] = useState([]) // 最多3只股票
  const [compareChartType, setCompareChartType] = useState('radar') // 'radar' | 'financial'
  const [marketStats, setMarketStats] = useState(null)
  const [dataFreshness, setDataFreshness] = useState({}) // 数据新鲜度
  const [showExportMenu, setShowExportMenu] = useState(false) // 导出菜单
  const [error, setError] = useState(null) // 错误状态

  // 获取市场统计
  useEffect(() => {
    fetchMarketStats()
  }, [])

  const fetchMarketStats = async () => {
    try {
      const res = await fetch('/api/stats/market')
      if (res.ok) {
        const stats = await res.json()
        setMarketStats(stats)
      }
    } catch (e) {
      console.error('Failed to fetch market stats:', e)
    }
  }

  // 市场概览图表配置
  const getMarketOverviewOption = () => {
    if (!marketStats) return {}
    return {
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 8, borderColor: '#1a1a2e', borderWidth: 2 },
        label: { show: false },
        emphasis: {
          label: { show: true, fontSize: 14, fontWeight: 'bold', color: '#fff' }
        },
        data: [
          { value: marketStats.high_cp_count, name: '高战力', itemStyle: { color: '#22c55e' } },
          { value: marketStats.mid_cp_count, name: '中战力', itemStyle: { color: '#eab308' } },
          { value: marketStats.low_cp_count, name: '低战力', itemStyle: { color: '#ef4444' } }
        ]
      }]
    }
  }

  const getMarketChangeOption = () => {
    if (!marketStats) return {}
    const rising = marketStats.rising_stocks || 0
    const falling = marketStats.falling_stocks || 0
    return {
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { type: 'category', data: ['上涨', '下跌'], axisLine: { lineStyle: { color: '#374151' } }, axisLabel: { color: '#9ca3af' } },
      yAxis: { type: 'value', axisLine: { show: false }, splitLine: { lineStyle: { color: '#374151' } }, axisLabel: { color: '#9ca3af' } },
      series: [{
        type: 'bar',
        data: [
          { value: rising, itemStyle: { color: '#ef4444', borderRadius: [4, 4, 0, 0] } },
          { value: falling, itemStyle: { color: '#22c55e', borderRadius: [4, 4, 0, 0] } }
        ],
        barWidth: '50%'
      }]
    }
  }

  // 对比雷达图配置
  const getCompareRadarOption = () => {
    if (compareList.length < 2) return null
    const colors = ['#3b82f6', '#22c55e', '#eab308']
    return {
      tooltip: { trigger: 'item' },
      legend: {
        data: compareList.map(s => s.name),
        bottom: 0,
        textStyle: { color: '#9ca3af' }
      },
      radar: {
        indicator: [
          { name: '成长分', max: 100 },
          { name: '价值分', max: 100 },
          { name: '质量分', max: 100 },
          { name: '趋势分', max: 100 },
          { name: '战力值', max: 100 },
        ],
        radius: '60%',
        splitNumber: 4,
        axisName: { color: '#9ca3af' },
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
        splitArea: { areaStyle: { color: ['rgba(0,0,0,0)'] } },
        axisLine: { lineStyle: { color: 'rgba(255,255,255,0.2)' } }
      },
      series: [{
        type: 'radar',
        data: compareList.map((stock, idx) => ({
          value: [stock.growth_score, stock.value_score, stock.quality_score || 0, stock.momentum_score, stock.total_cp],
          name: stock.name,
          areaStyle: { color: colors[idx % 3] + '40' },
          lineStyle: { color: colors[idx % 3], width: 2 },
          itemStyle: { color: colors[idx % 3] }
        }))
      }]
    }
  }

  // 财务数据对比图
  const getFinancialCompareOption = () => {
    if (compareList.length < 2) return null
    const colors = ['#3b82f6', '#22c55e', '#eab308']
    return {
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: {
        data: compareList.map(s => s.name),
        bottom: 0,
        textStyle: { color: '#9ca3af' }
      },
      grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
      xAxis: {
        type: 'category',
        data: ['ROE(%)', '净利润增速(%)', '营收增速(%)', 'PE'],
        axisLine: { lineStyle: { color: '#374151' } },
        axisLabel: { color: '#9ca3af' }
      },
      yAxis: {
        type: 'value',
        axisLine: { show: false },
        splitLine: { lineStyle: { color: '#374151' } },
        axisLabel: { color: '#9ca3af' }
      },
      series: compareList.map((stock, idx) => ({
        name: stock.name,
        type: 'bar',
        data: [
          stock.roe,
          stock.net_profit_growth,
          stock.revenue_growth,
          stock.pe > 0 ? stock.pe : 0
        ],
        itemStyle: { color: colors[idx % 3] }
      }))
    }
  }

  // 战力分布直方图
  const getCPDistributionOption = () => {
    if (data.length === 0) return {}
    // 将战力值分组统计
    const buckets = [
      { label: '0-10', min: 0, max: 10, count: 0 },
      { label: '10-20', min: 10, max: 20, count: 0 },
      { label: '20-30', min: 20, max: 30, count: 0 },
      { label: '30-40', min: 30, max: 40, count: 0 },
      { label: '40-50', min: 40, max: 50, count: 0 },
      { label: '50-60', min: 50, max: 60, count: 0 },
      { label: '60-70', min: 60, max: 70, count: 0 },
      { label: '70-80', min: 70, max: 80, count: 0 },
      { label: '80-90', min: 80, max: 90, count: 0 },
      { label: '90-100', min: 90, max: 100, count: 0 },
    ]

    data.forEach(stock => {
      const cp = stock.total_cp
      const bucket = buckets.find(b => cp >= b.min && cp < b.max)
      if (bucket) bucket.count++
    })

    return {
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: {
        type: 'category',
        data: buckets.map(b => b.label),
        axisLine: { lineStyle: { color: '#374151' } },
        axisLabel: { color: '#9ca3af', rotate: 45 }
      },
      yAxis: {
        type: 'value',
        name: '股票数量',
        axisLine: { show: false },
        splitLine: { lineStyle: { color: '#374151' } },
        axisLabel: { color: '#9ca3af' }
      },
      series: [{
        type: 'bar',
        data: buckets.map((b, i) => ({
          value: b.count,
          itemStyle: {
            color: i < 4 ? '#ef4444' : i < 6 ? '#eab308' : '#22c55e',
            borderRadius: [4, 4, 0, 0]
          }
        })),
        barWidth: '80%'
      }]
    }
  }

  const addToCompare = (stock) => {
    if (compareList.length >= 3) return
    if (compareList.find(s => s.code === stock.code)) return
    setCompareList([...compareList, stock])
  }

  const removeFromCompare = (code) => {
    setCompareList(compareList.filter(s => s.code !== code))
  }

  const isInCompare = (code) => {
    return compareList.find(s => s.code === code)
  }

  useEffect(() => {
    fetchData()

    // 自动刷新：每5分钟
    const interval = setInterval(() => {
      if (autoRefresh) {
        fetchData()
      }
    }, 5 * 60 * 1000)

    return () => clearInterval(interval)
  }, [autoRefresh, boardFilter])

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const boardParam = boardFilter === 'all' ? '' : `&board=${boardFilter}`
      const [topRes, healthRes] = await Promise.all([
        fetch(`/api/cp/top?limit=200${boardParam}`),
        fetch('/api/health')
      ])

      if (!topRes.ok) {
        throw new Error('请求失败')
      }

      const json = await topRes.json()

      // 检查API返回的错误
      if (json.error) {
        setError(json.error)
        setData([])
      } else {
        setData(json.data || [])
      }
      setUpdatedAt(json.updated_at)

      if (healthRes.ok) {
        const health = await healthRes.json()
        setDataFreshness({
          lastUpdate: health.last_update,
          stocksCount: health.stocks_count,
          isFresh: health.data_fresh
        })
      }
    } catch (e) {
      console.error('Failed to fetch data:', e)
      setError(e.message || '数据加载失败，请检查网络连接')
    }
    setLoading(false)
  }, [boardFilter])

  // 排序和筛选数据（使用useMemo优化性能）
  const getSortedData = useMemo(() => {
    return () => {
      const sorted = [...data].sort((a, b) => {
        let aVal = a[sortBy]
        let bVal = b[sortBy]

        // 处理0值（无数据）
        if (sortBy !== 'change_pct') {
          if (aVal === 0) aVal = sortOrder === 'desc' ? -Infinity : Infinity
          if (bVal === 0) bVal = sortOrder === 'desc' ? -Infinity : Infinity
        }

        if (sortOrder === 'desc') {
          return bVal - aVal
        } else {
          return aVal - bVal
        }
      })
      return sorted
    }
  }, [data, sortBy, sortOrder])

  // 过滤后的数据
  const getFilteredData = useMemo(() => {
    return () => {
      return getSortedData().filter(stock => {
        // 模式筛选
        if (filterMode === 'watchlist' && !isInWatchlist(stock.code)) return false
        // 战力范围筛选
        if (cpRange === 'high' && stock.total_cp < 70) return false
        if (cpRange === 'mid' && (stock.total_cp < 50 || stock.total_cp >= 70)) return false
        if (cpRange === 'low' && stock.total_cp >= 50) return false
        return true
      })
    }
  }, [getSortedData, filterMode, cpRange, isInWatchlist])

  // 切换排序
  const toggleSort = (field) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc')
    } else {
      setSortBy(field)
      setSortOrder('desc')
    }
  }

  // 获取排序图标
  const getSortIcon = (field) => {
    if (sortBy !== field) return <ArrowUpDown className="w-3 h-3 opacity-30" />
    return sortOrder === 'desc'
      ? <TrendingUp className="w-3 h-3" />
      : <TrendingDown className="w-3 h-3" />
  }

  const getCPColor = (cp) => {
    if (cp >= 70) return 'cp-high'
    if (cp >= 50) return 'cp-mid'
    return 'cp-low'
  }

  const getTrendIcon = (changePct) => {
    if (changePct > 0) return <TrendingUp className="w-4 h-4 text-red-500" />
    if (changePct < 0) return <TrendingDown className="w-4 h-4 text-green-500" />
    return <Minus className="w-4 h-4 text-gray-500" />
  }

  if (loading) {
    return (
      <div className="space-y-4">
        {/* 市场统计骨架 */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <SkeletonCard />
        </div>
        {/* 表格骨架 */}
        <div className="bg-card-bg rounded-xl border border-border-dark overflow-hidden">
          <SkeletonTable rows={10} cols={8} />
        </div>
      </div>
    )
  }

  // 错误状态
  if (error) {
    return (
      <div className="bg-cp-low/10 border border-cp-low/30 rounded-xl p-8 text-center">
        <p className="text-cp-low text-lg mb-4">{error}</p>
        <button
          onClick={() => fetchData()}
          className="px-4 py-2 bg-cp-low/20 hover:bg-cp-low/30 text-cp-low rounded-lg transition-colors"
        >
          重试
        </button>
      </div>
    )
  }

  return (
    <div>
      {/* 更新信息 */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <p className="text-sm text-gray-400">
            共 <span className="text-white font-bold">
              {filterMode !== 'all' || cpRange !== 'all' ? getFilteredData().length : data.length}
            </span> 只股票
            {(filterMode !== 'all' || cpRange !== 'all') && (
              <span className="ml-1 text-xs text-gray-500">
                (共{data.length}只)
              </span>
            )}
            {dataFreshness.stocksCount && (
              <span className="ml-2 text-xs text-gray-500">(数据库: {dataFreshness.stocksCount}只)</span>
            )}
          </p>
          {/* 数据状态指示器 */}
          {dataFreshness.lastUpdate && (
            <div className={`flex items-center gap-1 px-2 py-0.5 rounded text-xs ${
              dataFreshness.isFresh ? 'bg-green-500/20 text-green-500' : 'bg-yellow-500/20 text-yellow-500'
            }`}>
              <span className={`w-2 h-2 rounded-full ${dataFreshness.isFresh ? 'bg-green-500' : 'bg-yellow-500'}`} />
              {dataFreshness.isFresh ? '数据最新' : '数据较旧'}
            </div>
          )}
          {/* 筛选器 */}
          <div className="flex items-center gap-1 bg-deep-night rounded-lg p-1">
            <button
              onClick={() => setFilterMode('all')}
              className={`px-3 py-1 rounded text-sm transition-colors ${
                filterMode === 'all'
                  ? 'bg-accent-blue/20 text-accent-blue'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              全部
            </button>
            <button
              onClick={() => setFilterMode('watchlist')}
              className={`px-3 py-1 rounded text-sm transition-colors flex items-center gap-1 ${
                filterMode === 'watchlist'
                  ? 'bg-cp-high/20 text-cp-high'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <Star className="w-3 h-3" />
              自选 {watchlist.length > 0 && `(${watchlist.length})`}
            </button>
          </div>
          {/* 战力筛选 */}
          <div className="flex items-center gap-1 bg-deep-night rounded-lg p-1">
            <button
              onClick={() => setCpRange('all')}
              className={`px-3 py-1 rounded text-sm transition-colors ${
                cpRange === 'all' ? 'bg-accent-blue/20 text-accent-blue' : 'text-gray-400 hover:text-white'
              }`}
            >
              全部
            </button>
            <button
              onClick={() => setCpRange('high')}
              className={`px-3 py-1 rounded text-sm transition-colors ${
                cpRange === 'high' ? 'bg-green-500/20 text-green-500' : 'text-gray-400 hover:text-white'
              }`}
            >
              高战力
            </button>
            <button
              onClick={() => setCpRange('mid')}
              className={`px-3 py-1 rounded text-sm transition-colors ${
                cpRange === 'mid' ? 'bg-yellow-500/20 text-yellow-500' : 'text-gray-400 hover:text-white'
              }`}
            >
              中战力
            </button>
            <button
              onClick={() => setCpRange('low')}
              className={`px-3 py-1 rounded text-sm transition-colors ${
                cpRange === 'low' ? 'bg-red-500/20 text-red-500' : 'text-gray-400 hover:text-white'
              }`}
            >
              低战力
            </button>
          </div>
          {/* 板块筛选 - 新手友好 */}
          <div className="flex items-center gap-1 bg-deep-night rounded-lg p-1">
            <button
              onClick={() => setBoardFilter('main')}
              className={`px-3 py-1 rounded text-sm transition-colors flex items-center gap-1 ${
                boardFilter === 'main' ? 'bg-green-500/20 text-green-500' : 'text-gray-400 hover:text-white'
              }`}
              title="新手可交易"
            >
              <Shield className="w-3 h-3" />
              主板
            </button>
            <button
              onClick={() => setBoardFilter('all')}
              className={`px-3 py-1 rounded text-sm transition-colors ${
                boardFilter === 'all' ? 'bg-accent-blue/20 text-accent-blue' : 'text-gray-400 hover:text-white'
              }`}
            >
              全部
            </button>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* 自动刷新开关 */}
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`flex items-center gap-1 px-3 py-1 rounded text-sm transition-colors ${
              autoRefresh
                ? 'bg-green-500/20 text-green-500'
                : 'bg-gray-500/20 text-gray-500'
            }`}
          >
            <RefreshCw className={`w-3 h-3 ${autoRefresh ? 'animate-spin' : ''}`} />
            {autoRefresh ? '自动刷新中' : '已暂停'}
          </button>
          {/* 高级筛选 */}
          <StockScreener data={data} onFilter={(filtered) => {
            // 筛选结果会替换当前显示的数据
            if (filtered) {
              // 使用筛选后的数据进行显示
            }
          }} />
          {/* 导出按钮 */}
          <div className="relative">
            <button
              onClick={() => setShowExportMenu(!showExportMenu)}
              className="flex items-center gap-1 px-3 py-1 rounded text-sm bg-accent-blue/10 text-accent-blue hover:bg-accent-blue/20 transition-colors"
            >
              <Download className="w-3 h-3" />
              导出
              <ChevronDown className="w-3 h-3" />
            </button>
            {showExportMenu && (
              <div className="absolute right-0 top-full mt-1 w-36 bg-card-bg border border-border-dark rounded-lg shadow-xl z-50">
                <button
                  onClick={() => { exportToCSV(getFilteredData()); setShowExportMenu(false) }}
                  className="w-full px-4 py-2 flex items-center gap-2 text-sm text-gray-300 hover:bg-white/5 transition-colors first:rounded-t-lg last:rounded-b-lg"
                >
                  <FileSpreadsheet className="w-4 h-4 text-green-500" />
                  导出 CSV
                </button>
                <button
                  onClick={() => { exportToJSON(getFilteredData()); setShowExportMenu(false) }}
                  className="w-full px-4 py-2 flex items-center gap-2 text-sm text-gray-300 hover:bg-white/5 transition-colors first:rounded-t-lg last:rounded-b-lg"
                >
                  <FileJson className="w-4 h-4 text-blue-500" />
                  导出 JSON
                </button>
                <button
                  onClick={() => { exportToExcel(getFilteredData()); setShowExportMenu(false) }}
                  className="w-full px-4 py-2 flex items-center gap-2 text-sm text-gray-300 hover:bg-white/5 transition-colors first:rounded-t-lg last:rounded-b-lg"
                >
                  <FileSpreadsheet className="w-4 h-4 text-emerald-500" />
                  导出 Excel
                </button>
              </div>
            )}
          </div>
          {updatedAt && (
            <p className="text-xs text-gray-500">
              更新于 {new Date(updatedAt).toLocaleTimeString()}
            </p>
          )}
        </div>
      </div>

      {/* 市场统计概览 */}
      {marketStats && (
        <div className="mb-4 grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* 左侧统计卡片 */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-card-bg rounded-xl border border-border-dark p-4">
              <div className="flex items-center gap-2 mb-2">
                <BarChart3 className="w-4 h-4 text-accent-blue" />
                <span className="text-gray-400 text-sm">市场总战力</span>
              </div>
              <p className="text-2xl font-bold text-white">{marketStats.avg_cp.toFixed(1)}</p>
              <p className="text-xs text-gray-500">平均战力值</p>
            </div>
            <div className="bg-card-bg rounded-xl border border-border-dark p-4">
              <div className="flex items-center gap-2 mb-2">
                <TrendUp className="w-4 h-4 text-red-500" />
                <span className="text-gray-400 text-sm">上涨股票</span>
              </div>
              <p className="text-2xl font-bold text-red-500">{marketStats.rising_stocks}</p>
              <p className="text-xs text-gray-500">下跌 {marketStats.falling_stocks}</p>
            </div>
            <div className="bg-card-bg rounded-xl border border-border-dark p-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-gray-400 text-sm">战力分布</span>
              </div>
              <div className="flex gap-2 mt-1">
                <span className="px-2 py-1 rounded bg-green-500/20 text-green-500 text-xs font-bold">{marketStats.high_cp_count}</span>
                <span className="px-2 py-1 rounded bg-yellow-500/20 text-yellow-500 text-xs font-bold">{marketStats.mid_cp_count}</span>
                <span className="px-2 py-1 rounded bg-red-500/20 text-red-500 text-xs font-bold">{marketStats.low_cp_count}</span>
              </div>
            </div>
            <div className="bg-card-bg rounded-xl border border-border-dark p-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-gray-400 text-sm">高PE/亏损</span>
              </div>
              <p className="text-2xl font-bold text-white">{marketStats.high_pe_stocks}</p>
              <p className="text-xs text-gray-500">PE&gt;50 | 亏损 {marketStats.loss_stocks}</p>
            </div>
          </div>
          {/* 右侧战力分布图 */}
          <div className="bg-card-bg rounded-xl border border-border-dark p-4">
            <p className="text-gray-400 text-sm mb-2">战力分布</p>
            <ReactECharts option={getCPDistributionOption()} style={{ height: '180px' }} />
          </div>
        </div>
      )}

      {/* 榜单 */}
      <div className="bg-card-bg rounded-xl border border-border-dark overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border-dark text-left text-sm text-gray-400">
              <th className="px-4 py-3 w-12">排名</th>
              <th className="px-4 py-3 w-10"></th>
              <th className="px-4 py-3 w-10"></th>
              <th className="px-4 py-3">股票</th>
              <th
                className="px-4 py-3 text-right cursor-pointer hover:text-white transition-colors"
                onClick={() => toggleSort('total_cp')}
              >
                <div className="flex items-center justify-end gap-1">
                  战力值 {getSortIcon('total_cp')}
                </div>
              </th>
              <th
                className="px-4 py-3 text-right cursor-pointer hover:text-white transition-colors"
                onClick={() => toggleSort('growth_score')}
              >
                <div className="flex items-center justify-end gap-1">
                  成长分 {getSortIcon('growth_score')}
                </div>
              </th>
              <th
                className="px-4 py-3 text-right cursor-pointer hover:text-white transition-colors"
                onClick={() => toggleSort('value_score')}
              >
                <div className="flex items-center justify-end gap-1">
                  价值分 {getSortIcon('value_score')}
                </div>
              </th>
              <th
                className="px-4 py-3 text-right cursor-pointer hover:text-white transition-colors"
                onClick={() => toggleSort('quality_score')}
              >
                <div className="flex items-center justify-end gap-1">
                  质量分 {getSortIcon('quality_score')}
                </div>
              </th>
              <th
                className="px-4 py-3 text-right cursor-pointer hover:text-white transition-colors"
                onClick={() => toggleSort('momentum_score')}
              >
                <div className="flex items-center justify-end gap-1">
                  趋势分 {getSortIcon('momentum_score')}
                </div>
              </th>
              <th
                className="px-4 py-3 text-right cursor-pointer hover:text-white transition-colors"
                onClick={() => toggleSort('change_pct')}
              >
                <div className="flex items-center justify-end gap-1">
                  涨跌幅 {getSortIcon('change_pct')}
                </div>
              </th>
              <th
                className="px-4 py-3 text-right cursor-pointer hover:text-white transition-colors"
                onClick={() => toggleSort('pe')}
              >
                <div className="flex items-center justify-end gap-1">
                  PE {getSortIcon('pe')}
                </div>
              </th>
              <th
                className="px-4 py-3 text-right cursor-pointer hover:text-white transition-colors"
                onClick={() => toggleSort('roe')}
              >
                <div className="flex items-center justify-end gap-1">
                  ROE {getSortIcon('roe')}
                </div>
              </th>
              <th className="px-4 py-3 text-right">
                <div className="flex items-center justify-end gap-1">
                  <Shield className="w-3 h-3" />
                  风险
                </div>
              </th>
            </tr>
          </thead>
          <tbody>
            {getFilteredData()
              .map((stock, index) => (
              <tr
                key={stock.code}
                className="border-b border-border-dark/50 hover:bg-white/5 transition-colors"
              >
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold ${
                    index < 3 ? 'bg-accent-blue/20 text-accent-blue' : 'text-gray-500'
                  }`}>
                    {index + 1}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => toggle(stock.code)}
                    className="transition-colors"
                  >
                    <Star
                      className={`w-5 h-5 ${
                        isInWatchlist(stock.code)
                          ? 'text-cp-high fill-cp-high'
                          : 'text-gray-500 hover:text-cp-high'
                      }`}
                    />
                  </button>
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => isInCompare(stock.code) ? removeFromCompare(stock.code) : addToCompare(stock)}
                    disabled={!isInCompare(stock.code) && compareList.length >= 3}
                    className={`p-1 rounded transition-colors ${
                      isInCompare(stock.code)
                        ? 'text-accent-blue'
                        : compareList.length >= 3
                        ? 'text-gray-600 cursor-not-allowed'
                        : 'text-gray-500 hover:text-accent-blue'
                    }`}
                  >
                    <GitCompare className="w-4 h-4" />
                  </button>
                </td>
                <td className="px-4 py-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="font-bold text-white">{stock.name}</p>
                      {/* 板块标签 */}
                      {stock.board_type !== 'main' && (
                        <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                          stock.board_type === 'gem' ? 'bg-orange-500/20 text-orange-400' :
                          stock.board_type === 'star' ? 'bg-purple-500/20 text-purple-400' :
                          'bg-blue-500/20 text-blue-400'
                        }`}>
                          {stock.board_name}
                        </span>
                      )}
                      {/* 新手不可交易提示 */}
                      {!stock.can_trade_newbie && (
                        <span className="px-1.5 py-0.5 rounded text-xs bg-gray-500/20 text-gray-400" title={stock.trade_requirement}>
                          限
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-500">{stock.code}</p>
                  </div>
                </td>
                <td className="px-4 py-3 text-right">
                  <span className={`cp-tag ${getCPColor(stock.total_cp)}`}>
                    {stock.total_cp.toFixed(1)}
                  </span>
                </td>
                <td className="px-4 py-3 text-right text-sm text-gray-300">
                  {stock.growth_score.toFixed(1)}
                </td>
                <td className="px-4 py-3 text-right text-sm text-gray-300">
                  {stock.value_score.toFixed(1)}
                </td>
                <td className="px-4 py-3 text-right text-sm text-purple-400">
                  {(stock.quality_score || 0).toFixed(1)}
                </td>
                <td className="px-4 py-3 text-right text-sm text-gray-300">
                  {stock.momentum_score.toFixed(1)}
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-1">
                    {getTrendIcon(stock.change_pct)}
                    <span className={`text-sm font-mono ${
                      stock.change_pct > 0 ? 'text-red-500' : stock.change_pct < 0 ? 'text-green-500' : 'text-gray-500'
                    }`}>
                      {stock.change_pct >= 0 ? '+' : ''}{stock.change_pct.toFixed(2)}%
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3 text-right text-sm font-mono text-gray-300">
                  {stock.pe > 0 ? stock.pe.toFixed(1) : 'N/A'}
                </td>
                <td className="px-4 py-3 text-right text-sm font-mono text-gray-300">
                  {stock.roe.toFixed(1)}%
                </td>
                <td className="px-4 py-3 text-right">
                  {stock.risk_score !== undefined ? (
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
                      stock.risk_score >= 60 ? 'bg-red-500/20 text-red-400' :
                      stock.risk_score >= 30 ? 'bg-yellow-500/20 text-yellow-400' :
                      'bg-green-500/20 text-green-400'
                    }`}>
                      <Shield className="w-3 h-3" />
                      {stock.risk_score.toFixed(0)}
                    </span>
                  ) : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {data.length === 0 && (
          <div className="py-20 text-center text-gray-400">
            暂无数据
          </div>
        )}
      </div>

      {/* 战力说明 */}
      <div className="mt-4 bg-card-bg rounded-xl border border-border-dark p-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="font-bold text-white">战力说明 (v14)</h4>
          <p className="text-xs text-gray-500">战力 = (成长×30% + 价值×25% + 质量×20% + 动量×15%) × 风险调整</p>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
          <div className="bg-white/5 rounded-lg p-2">
            <p className="text-gray-400 mb-1">成长分 30%</p>
            <p className="text-accent-blue text-xs">净利润+营收增长</p>
          </div>
          <div className="bg-white/5 rounded-lg p-2">
            <p className="text-gray-400 mb-1">价值分 25%</p>
            <p className="text-cp-high text-xs">ROE+PE+PEG+PB</p>
          </div>
          <div className="bg-white/5 rounded-lg p-2">
            <p className="text-gray-400 mb-1">质量分 20%</p>
            <p className="text-purple-400 text-xs">现金流+毛利率</p>
          </div>
          <div className="bg-white/5 rounded-lg p-2">
            <p className="text-gray-400 mb-1">动量分 15%</p>
            <p className="text-yellow-400 text-xs">涨跌幅</p>
          </div>
          <div className="bg-white/5 rounded-lg p-2">
            <p className="text-gray-400 mb-1">风险调整</p>
            <p className="text-red-400 text-xs">高风险打折</p>
          </div>
        </div>
      </div>

      {/* 战力对比面板 */}
      {compareList.length > 0 && (
        <div className="mt-4 bg-card-bg rounded-xl border border-accent-blue/50 p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-white flex items-center gap-2">
              <GitCompare className="w-5 h-5 text-accent-blue" />
              战力对比 ({compareList.length}/3)
            </h3>
            <button
              onClick={() => setCompareList([])}
              className="text-gray-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* 雷达图对比 */}
          {compareList.length >= 2 && (
            <div className="mb-4 bg-deep-night rounded-lg p-4">
              <div className="flex justify-between items-center mb-2">
                <p className="text-gray-400 text-sm">图表对比</p>
                <div className="flex gap-2">
                  <button
                    onClick={() => setCompareChartType('radar')}
                    className={`px-3 py-1 rounded text-xs ${compareChartType === 'radar' ? 'bg-accent-blue/20 text-accent-blue' : 'text-gray-400'}`}
                  >
                    雷达图
                  </button>
                  <button
                    onClick={() => setCompareChartType('financial')}
                    className={`px-3 py-1 rounded text-xs ${compareChartType === 'financial' ? 'bg-accent-blue/20 text-accent-blue' : 'text-gray-400'}`}
                  >
                    财务数据
                  </button>
                </div>
              </div>
              <ReactECharts
                option={compareChartType === 'radar' ? getCompareRadarOption() : getFinancialCompareOption()}
                style={{ height: '250px' }}
              />
            </div>
          )}

          <div className="grid grid-cols-3 gap-4">
            {compareList.map((stock, idx) => (
              <div key={stock.code} className="bg-deep-night rounded-lg p-4 relative">
                <button
                  onClick={() => removeFromCompare(stock.code)}
                  className="absolute top-2 right-2 text-gray-500 hover:text-white"
                >
                  <X className="w-4 h-4" />
                </button>
                <div className="text-center mb-4">
                  <p className="font-bold text-white">{stock.name}</p>
                  <p className="text-xs text-gray-500">{stock.code}</p>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-400">战力值</span>
                    <span className={`cp-tag ${stock.total_cp >= 70 ? 'cp-high' : stock.total_cp >= 50 ? 'cp-mid' : 'cp-low'}`}>
                      {stock.total_cp.toFixed(1)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">成长分</span>
                    <span className="text-white">{stock.growth_score.toFixed(1)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">价值分</span>
                    <span className="text-white">{stock.value_score.toFixed(1)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">质量分</span>
                    <span className="text-purple-400">{(stock.quality_score || 0).toFixed(1)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">趋势分</span>
                    <span className="text-white">{stock.momentum_score.toFixed(1)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">价格</span>
                    <span className="text-white">¥{stock.price.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">PE</span>
                    <span className="text-white">{stock.pe.toFixed(1)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">ROE</span>
                    <span className="text-white">{stock.roe.toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">涨跌幅</span>
                    <span className={stock.change_pct >= 0 ? 'text-red-500' : 'text-green-500'}>
                      {stock.change_pct >= 0 ? '+' : ''}{stock.change_pct.toFixed(2)}%
                    </span>
                  </div>
                  {stock.market_cap > 0 && (
                    <div className="flex justify-between">
                      <span className="text-gray-400">市值</span>
                      <span className="text-white">{stock.market_cap.toFixed(0)}亿</span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-gray-400">数据</span>
                    <span className={stock.data_quality === 'high' ? 'text-green-400' : stock.data_quality === 'medium' ? 'text-yellow-400' : 'text-gray-400'}>
                      {stock.data_quality === 'high' ? '高' : stock.data_quality === 'medium' ? '中' : '低'}
                    </span>
                  </div>
                </div>
              </div>
            ))}
            {/* 空白槽位 */}
            {[...Array(3 - compareList.length)].map((_, i) => (
              <div key={`empty-${i}`} className="bg-deep-night/50 rounded-lg p-4 border-2 border-dashed border-border-dark flex items-center justify-center">
                <p className="text-gray-500 text-sm">点击+添加股票</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default CPTopList
