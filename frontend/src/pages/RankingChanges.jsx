import { useState, useEffect } from 'react'
import { TrendingUp, TrendingDown, Trophy, AlertTriangle, Star } from 'lucide-react'
import { useWatchlist } from '../hooks/useWatchlist'

function RankingChanges() {
  const [changes, setChanges] = useState([])
  const [rankings, setRankings] = useState([])
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(30)
  const { toggle, isInWatchlist } = useWatchlist()

  useEffect(() => {
    fetchData()
  }, [days])

  const fetchData = async () => {
    setLoading(true)
    try {
      const [changesRes, rankingsRes] = await Promise.all([
        fetch(`/api/history/rankings/changes?days=${days}`),
        fetch(`/api/history/rankings/top?days=${days}`)
      ])

      if (changesRes.ok) {
        const data = await changesRes.json()
        setChanges(data.data || [])
      }

      if (rankingsRes.ok) {
        const data = await rankingsRes.json()
        setRankings(data.data || [])
      }
    } catch (e) {
      console.error('Failed to fetch:', e)
    }
    setLoading(false)
  }

  const getCPColor = (cp) => {
    if (cp >= 70) return 'cp-high'
    if (cp >= 50) return 'cp-mid'
    return 'cp-low'
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-accent-blue/30 border-t-accent-blue rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-400">加载榜单数据...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 筛选器 */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">榜单排名变化</h2>
        <div className="flex gap-2">
          <button
            onClick={() => setDays(7)}
            className={`px-3 py-1 rounded text-sm ${days === 7 ? 'bg-accent-blue/20 text-accent-blue' : 'text-gray-400 hover:text-white'}`}
          >
            近7天
          </button>
          <button
            onClick={() => setDays(30)}
            className={`px-3 py-1 rounded text-sm ${days === 30 ? 'bg-accent-blue/20 text-accent-blue' : 'text-gray-400 hover:text-white'}`}
          >
            近30天
          </button>
          <button
            onClick={() => setDays(90)}
            className={`px-3 py-1 rounded text-sm ${days === 90 ? 'bg-accent-blue/20 text-accent-blue' : 'text-gray-400 hover:text-white'}`}
          >
            近90天
          </button>
        </div>
      </div>

      {/* 新晋/跌出榜单 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* 新晋TOP10 */}
        <div className="bg-card-bg rounded-xl border border-border-dark p-4">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-5 h-5 text-green-500" />
            <h3 className="font-bold text-white">新晋TOP10</h3>
            <span className="text-xs text-gray-400">({changes.filter(c => c.type === 'new').length}只)</span>
          </div>
          {changes.filter(c => c.type === 'new').length === 0 ? (
            <p className="text-gray-400 text-sm text-center py-4">暂无数据</p>
          ) : (
            <div className="space-y-2">
              {changes.filter(c => c.type === 'new').map(stock => (
                <div key={stock.code} className="flex items-center justify-between p-2 bg-deep-night rounded-lg">
                  <div className="flex items-center gap-3">
                    <Star className="w-4 h-4 text-green-500" />
                    <div>
                      <p className="text-white text-sm font-medium">{stock.name}</p>
                      <p className="text-gray-500 text-xs">{stock.code}</p>
                    </div>
                  </div>
                  <span className={`cp-tag ${getCPColor(stock.total_cp)}`}>
                    {stock.total_cp.toFixed(1)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 跌出TOP10 */}
        <div className="bg-card-bg rounded-xl border border-border-dark p-4">
          <div className="flex items-center gap-2 mb-4">
            <TrendingDown className="w-5 h-5 text-red-500" />
            <h3 className="font-bold text-white">跌出TOP10</h3>
            <span className="text-xs text-gray-400">({changes.filter(c => c.type === 'drop').length}只)</span>
          </div>
          {changes.filter(c => c.type === 'drop').length === 0 ? (
            <p className="text-gray-400 text-sm text-center py-4">暂无数据</p>
          ) : (
            <div className="space-y-2">
              {changes.filter(c => c.type === 'drop').map(stock => (
                <div key={stock.code} className="flex items-center justify-between p-2 bg-deep-night rounded-lg">
                  <div className="flex items-center gap-3">
                    <AlertTriangle className="w-4 h-4 text-red-500" />
                    <div>
                      <p className="text-white text-sm font-medium">{stock.name}</p>
                      <p className="text-gray-500 text-xs">{stock.code}</p>
                    </div>
                  </div>
                  <span className={`cp-tag ${getCPColor(stock.total_cp)}`}>
                    {stock.total_cp.toFixed(1)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 历史TOP10榜单 */}
      <div className="bg-card-bg rounded-xl border border-border-dark overflow-hidden">
        <div className="px-4 py-3 border-b border-border-dark flex items-center gap-2">
          <Trophy className="w-5 h-5 text-yellow-500" />
          <h3 className="font-bold text-white">历史冠军榜</h3>
        </div>

        {rankings.length === 0 ? (
          <div className="p-8 text-center text-gray-400">
            <Trophy className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>暂无历史数据</p>
            <p className="text-sm">战力榜每日更新后会记录历史</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border-dark text-left text-sm text-gray-400">
                  <th className="px-4 py-3">日期</th>
                  <th className="px-4 py-3">TOP1</th>
                  <th className="px-4 py-3">TOP2</th>
                  <th className="px-4 py-3">TOP3</th>
                  <th className="px-4 py-3">TOP4</th>
                  <th className="px-4 py-3">TOP5</th>
                </tr>
              </thead>
              <tbody>
                {rankings.slice(0, 10).map((day, idx) => (
                  <tr key={idx} className="border-b border-border-dark/50">
                    <td className="px-4 py-3 text-gray-400 text-sm">{day.date}</td>
                    {[0, 1, 2, 3, 4].map(i => (
                      <td key={i} className="px-4 py-3">
                        {day.top10[i] ? (
                          <div className="flex items-center gap-2">
                            <span className={`cp-tag ${getCPColor(day.top10[i].total_cp)}`}>
                              {day.top10[i].total_cp.toFixed(1)}
                            </span>
                            <span className="text-white text-sm">{day.top10[i].name}</span>
                          </div>
                        ) : (
                          <span className="text-gray-600">-</span>
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

export default RankingChanges
