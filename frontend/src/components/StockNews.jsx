import { useState, useEffect } from 'react'
import { ExternalLink, Clock, AlertCircle } from 'lucide-react'

function StockNews({ code }) {
  const [news, setNews] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!code) return
    fetchNews()
  }, [code])

  const fetchNews = async () => {
    setLoading(true)
    try {
      // 模拟新闻数据（实际项目中可接入东方财富等新闻API）
      const mockNews = [
        {
          title: `${code} 发布2024年年度报告`,
          date: new Date().toISOString().slice(0, 10),
          type: '公告',
          url: '#'
        },
        {
          title: `${code} 净利润同比增长15%，业绩超预期`,
          date: new Date(Date.now() - 86400000).toISOString().slice(0, 10),
          type: '财报',
          url: '#'
        },
        {
          title: `机构上调${code}目标价至新高`,
          date: new Date(Date.now() - 172800000).toISOString().slice(0, 10),
          type: '研报',
          url: '#'
        }
      ]
      setNews(mockNews)
    } catch (e) {
      console.error('Failed to fetch news:', e)
    }
    setLoading(false)
  }

  if (loading) {
    return (
      <div className="animate-pulse space-y-2">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-16 bg-deep-night rounded-lg" />
        ))}
      </div>
    )
  }

  if (news.length === 0) {
    return (
      <div className="text-center py-8 text-gray-400">
        <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
        <p className="text-sm">暂无相关新闻</p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {news.map((item, idx) => (
        <a
          key={idx}
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-start gap-3 p-3 bg-deep-night rounded-lg hover:bg-white/5 transition-colors group"
        >
          <div className={`px-2 py-0.5 rounded text-xs font-medium ${
            item.type === '公告' ? 'bg-blue-500/20 text-blue-400' :
            item.type === '财报' ? 'bg-green-500/20 text-green-400' :
            'bg-yellow-500/20 text-yellow-400'
          }`}>
            {item.type}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-white text-sm group-hover:text-accent-blue transition-colors line-clamp-2">
              {item.title}
            </p>
            <div className="flex items-center gap-2 mt-1 text-gray-500 text-xs">
              <Clock className="w-3 h-3" />
              {item.date}
            </div>
          </div>
          <ExternalLink className="w-4 h-4 text-gray-500 group-hover:text-accent-blue flex-shrink-0" />
        </a>
      ))}
    </div>
  )
}

export default StockNews
