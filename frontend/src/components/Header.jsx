import { RefreshCw, Zap, List, Search, User, Sparkles, Menu, X, Sun, Moon, Calculator, Settings, Trophy, Bell, BarChart3, BookOpen } from 'lucide-react'
import { useState, useEffect } from 'react'
import { useTheme } from '../hooks/useTheme'
import NotificationCenter from './NotificationCenter'
import { useNotification } from '../hooks/useNotification'
import { DataSourceInfo } from './DataSourceInfo'

function Header({ onRefresh, currentPage, onNavigate, onOpenSettings, onOpenEducation }) {
  const { isDark, toggleTheme } = useTheme()
  const [refreshing, setRefreshing] = useState(false)
  const [quickCode, setQuickCode] = useState('')
  const [searchSuggestions, setSearchSuggestions] = useState([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [showNotifications, setShowNotifications] = useState(false)
  const { unreadCount } = useNotification()

  // 全局快捷搜索
  useEffect(() => {
    if (!quickCode.trim()) {
      setSearchSuggestions([])
      return
    }

    const fetchSuggestions = async () => {
      try {
        const res = await fetch('/api/cp/top?limit=50')
        if (res.ok) {
          const json = await res.json()
          const query = quickCode.toLowerCase()
          const filtered = json.data
            .filter(s => s.code.toLowerCase().includes(query) || s.name.toLowerCase().includes(query))
            .slice(0, 5)
          setSearchSuggestions(filtered)
        }
      } catch (e) {}
    }

    const debounce = setTimeout(fetchSuggestions, 150)
    return () => clearTimeout(debounce)
  }, [quickCode])

  // 数据新鲜度检查
  useEffect(() => {
    const checkFreshness = async () => {
      try {
        const res = await fetch('/api/health')
        if (res.ok) {
          const data = await res.json()
          if (!data.data_fresh) {
            // 数据超过1小时，自动刷新
            handleRefresh()
          }
        }
      } catch (e) {}
    }
    checkFreshness()
  }, [])

  const handleQuickSearch = (code) => {
    // 导航到搜索页面并触发搜索
    onNavigate('search')
    setQuickCode('')
    setSearchSuggestions([])
    setShowSuggestions(false)
    // 通过localStorage传递搜索代码
    localStorage.setItem('quickSearchCode', code)
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && searchSuggestions.length > 0) {
      handleQuickSearch(searchSuggestions[0].code)
    } else if (e.key === 'Enter' && quickCode.trim()) {
      onNavigate('search')
      localStorage.setItem('quickSearchCode', quickCode.trim())
      setQuickCode('')
      setShowSuggestions(false)
    }
  }

  return (
    <header className="bg-card-bg border-b border-border-dark px-4 py-3 md:px-6">
      <div className="container mx-auto">
        <div className="flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-2 md:gap-3">
            <div className="w-8 h-8 md:w-10 md:h-10 rounded-lg bg-accent-blue/20 flex items-center justify-center">
              <Zap className="w-5 h-5 md:w-6 md:h-6 text-accent-blue" />
            </div>
            <div className="hidden sm:block">
              <h1 className="text-lg md:text-xl font-bold text-white">TradeSnake</h1>
              <p className="text-xs text-gray-400">股市贪吃蛇</p>
            </div>
          </div>

          {/* 移动端菜单按钮 */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden p-2 text-gray-400 hover:text-white"
          >
            {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>

          {/* 导航 - 桌面端 */}
          <nav className="hidden md:flex items-center gap-2">
            <button
              onClick={() => onNavigate('toplist')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                currentPage === 'toplist'
                  ? 'bg-accent-blue/20 text-accent-blue'
                  : 'text-gray-400 hover:bg-white/5 hover:text-white'
              }`}
            >
              <List className="w-4 h-4" />
              战力榜单
            </button>
            <button
              onClick={() => onNavigate('search')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                currentPage === 'search'
                  ? 'bg-accent-blue/20 text-accent-blue'
                  : 'text-gray-400 hover:bg-white/5 hover:text-white'
              }`}
            >
              <Search className="w-4 h-4" />
              单股查询
            </button>
            <button
              onClick={() => onNavigate('personal')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                currentPage === 'personal'
                  ? 'bg-cp-high/20 text-cp-high'
                  : 'text-gray-400 hover:bg-white/5 hover:text-white'
              }`}
            >
              <User className="w-4 h-4" />
              我的战力
            </button>
            <button
              onClick={() => onNavigate('recommend')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                currentPage === 'recommend'
                  ? 'bg-cp-high/20 text-cp-high'
                  : 'text-gray-400 hover:bg-white/5 hover:text-white'
              }`}
            >
              <Sparkles className="w-4 h-4" />
              智能推荐
            </button>
            <button
              onClick={() => onNavigate('simulator')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                currentPage === 'simulator'
                  ? 'bg-accent-blue/20 text-accent-blue'
                  : 'text-gray-400 hover:bg-white/5 hover:text-white'
              }`}
            >
              <Calculator className="w-4 h-4" />
              模拟器
            </button>
            <button
              onClick={() => onNavigate('rankings')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                currentPage === 'rankings'
                  ? 'bg-accent-blue/20 text-accent-blue'
                  : 'text-gray-400 hover:bg-white/5 hover:text-white'
              }`}
            >
              <Trophy className="w-4 h-4" />
              榜单变化
            </button>
            <button
              onClick={() => onNavigate('sector')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                currentPage === 'sector'
                  ? 'bg-accent-blue/20 text-accent-blue'
                  : 'text-gray-400 hover:bg-white/5 hover:text-white'
              }`}
            >
              <BarChart3 className="w-4 h-4" />
              行业分析
            </button>
          </nav>

          {/* 全局快捷搜索 */}
          <div className="hidden md:block relative">
            <div className="flex items-center gap-2">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  value={quickCode}
                  onChange={(e) => setQuickCode(e.target.value)}
                  onKeyPress={handleKeyPress}
                  onFocus={() => setShowSuggestions(true)}
                  onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
                  placeholder="快捷搜索..."
                  className="w-40 px-3 py-2 pl-9 bg-deep-night border border-border-dark rounded-lg text-white text-sm placeholder-gray-500 focus:outline-none focus:border-accent-blue"
                />
              </div>
              <button
                onClick={onRefresh}
                disabled={refreshing}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent-blue/10 text-accent-blue hover:bg-accent-blue/20 transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
                <span className="hidden lg:inline">{refreshing ? '刷新中...' : '刷新数据'}</span>
              </button>
              <button
                onClick={toggleTheme}
                className="p-2 rounded-lg bg-card-bg text-gray-400 hover:text-white transition-colors"
                title={isDark ? '切换到浅色模式' : '切换到深色模式'}
              >
                {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
              </button>
              <button
                onClick={onOpenSettings}
                className="p-2 rounded-lg bg-card-bg text-gray-400 hover:text-white transition-colors"
                title="设置"
              >
                <Settings className="w-4 h-4" />
              </button>
              {/* 战力学堂 */}
              <button
                onClick={onOpenEducation}
                className="px-3 py-2 rounded-lg bg-cp-high/10 text-cp-high hover:bg-cp-high/20 transition-colors text-sm flex items-center gap-1.5"
                title="了解战力公式"
              >
                <BookOpen className="w-4 h-4" />
                <span className="hidden lg:inline">战力学堂</span>
              </button>
              {/* 数据来源信息 */}
              <DataSourceInfo />
              {/* 通知铃铛 */}
              <div className="relative">
                <button
                  onClick={() => setShowNotifications(!showNotifications)}
                  className="p-2 rounded-lg bg-card-bg text-gray-400 hover:text-white transition-colors relative"
                  title="通知中心"
                >
                  <Bell className="w-4 h-4" />
                  {unreadCount > 0 && (
                    <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
                      {unreadCount > 9 ? '9+' : unreadCount}
                    </span>
                  )}
                </button>
                <NotificationCenter
                  isOpen={showNotifications}
                  onClose={() => setShowNotifications(false)}
                />
              </div>
            </div>
            {/* 搜索建议 */}
            {showSuggestions && searchSuggestions.length > 0 && (
              <div className="absolute right-0 top-full mt-2 w-64 bg-card-bg border border-border-dark rounded-lg shadow-xl z-50">
                {searchSuggestions.map(stock => (
                  <button
                    key={stock.code}
                    onClick={() => handleQuickSearch(stock.code)}
                    className="w-full px-4 py-2 flex items-center justify-between hover:bg-white/5 transition-colors first:rounded-t-lg last:rounded-b-lg"
                  >
                    <div className="flex items-center gap-2">
                      <div className="text-left">
                        <p className="text-white text-sm font-bold">{stock.name}</p>
                        <p className="text-gray-500 text-xs">{stock.code}</p>
                      </div>
                      {stock.data_quality && (
                        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                          stock.data_quality === 'high' ? 'bg-green-400' :
                          stock.data_quality === 'medium' ? 'bg-yellow-400' : 'bg-gray-500'
                        }`} title={`数据质量: ${stock.data_quality === 'high' ? '高' : stock.data_quality === 'medium' ? '中' : '低'}`} />
                      )}
                    </div>
                    <span className={`cp-tag ${
                      stock.total_cp >= 70 ? 'cp-high' : stock.total_cp >= 50 ? 'cp-mid' : 'cp-low'
                    }`}>
                      {stock.total_cp.toFixed(1)}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* 移动端菜单 */}
        {mobileMenuOpen && (
          <div className="md:hidden mt-4 pb-2 border-t border-border-dark pt-4">
            {/* 移动端搜索 */}
            <div className="relative mb-4">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                value={quickCode}
                onChange={(e) => setQuickCode(e.target.value)}
                onKeyPress={handleKeyPress}
                onFocus={() => setShowSuggestions(true)}
                onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
                placeholder="快捷搜索..."
                className="w-full px-3 py-2 pl-9 bg-deep-night border border-border-dark rounded-lg text-white text-sm placeholder-gray-500 focus:outline-none focus:border-accent-blue"
              />
              {showSuggestions && searchSuggestions.length > 0 && (
                <div className="absolute left-0 right-0 top-full mt-2 bg-card-bg border border-border-dark rounded-lg shadow-xl z-50">
                  {searchSuggestions.map(stock => (
                    <button
                      key={stock.code}
                      onClick={() => { handleQuickSearch(stock.code); setMobileMenuOpen(false) }}
                      className="w-full px-4 py-2 flex items-center justify-between hover:bg-white/5 transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <div className="text-left">
                          <p className="text-white text-sm font-bold">{stock.name}</p>
                          <p className="text-gray-500 text-xs">{stock.code}</p>
                        </div>
                        {stock.data_quality && (
                          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                            stock.data_quality === 'high' ? 'bg-green-400' :
                            stock.data_quality === 'medium' ? 'bg-yellow-400' : 'bg-gray-500'
                          }`} title={`数据质量: ${stock.data_quality === 'high' ? '高' : stock.data_quality === 'medium' ? '中' : '低'}`} />
                        )}
                      </div>
                      <span className={`cp-tag ${stock.total_cp >= 70 ? 'cp-high' : stock.total_cp >= 50 ? 'cp-mid' : 'cp-low'}`}>
                        {stock.total_cp.toFixed(1)}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            {/* 移动端导航 */}
            <nav className="flex flex-col gap-2">
              <button
                onClick={() => { onNavigate('toplist'); setMobileMenuOpen(false) }}
                className={`flex items-center gap-2 px-4 py-3 rounded-lg transition-colors ${
                  currentPage === 'toplist' ? 'bg-accent-blue/20 text-accent-blue' : 'text-gray-400'
                }`}
              >
                <List className="w-5 h-5" />
                战力榜单
              </button>
              <button
                onClick={() => { onNavigate('search'); setMobileMenuOpen(false) }}
                className={`flex items-center gap-2 px-4 py-3 rounded-lg transition-colors ${
                  currentPage === 'search' ? 'bg-accent-blue/20 text-accent-blue' : 'text-gray-400'
                }`}
              >
                <Search className="w-5 h-5" />
                单股查询
              </button>
              <button
                onClick={() => { onNavigate('personal'); setMobileMenuOpen(false) }}
                className={`flex items-center gap-2 px-4 py-3 rounded-lg transition-colors ${
                  currentPage === 'personal' ? 'bg-cp-high/20 text-cp-high' : 'text-gray-400'
                }`}
              >
                <User className="w-5 h-5" />
                我的战力
              </button>
              <button
                onClick={() => { onNavigate('recommend'); setMobileMenuOpen(false) }}
                className={`flex items-center gap-2 px-4 py-3 rounded-lg transition-colors ${
                  currentPage === 'recommend' ? 'bg-cp-high/20 text-cp-high' : 'text-gray-400'
                }`}
              >
                <Sparkles className="w-5 h-5" />
                智能推荐
              </button>
              <button
                onClick={() => { onNavigate('simulator'); setMobileMenuOpen(false) }}
                className={`flex items-center gap-2 px-4 py-3 rounded-lg transition-colors ${
                  currentPage === 'simulator' ? 'bg-accent-blue/20 text-accent-blue' : 'text-gray-400'
                }`}
              >
                <Calculator className="w-5 h-5" />
                组合模拟器
              </button>
              <button
                onClick={() => { onNavigate('rankings'); setMobileMenuOpen(false) }}
                className={`flex items-center gap-2 px-4 py-3 rounded-lg transition-colors ${
                  currentPage === 'rankings' ? 'bg-accent-blue/20 text-accent-blue' : 'text-gray-400'
                }`}
              >
                <Trophy className="w-5 h-5" />
                榜单变化
              </button>
              <button
                onClick={() => { onNavigate('sector'); setMobileMenuOpen(false) }}
                className={`flex items-center gap-2 px-4 py-3 rounded-lg transition-colors ${
                  currentPage === 'sector' ? 'bg-accent-blue/20 text-accent-blue' : 'text-gray-400'
                }`}
              >
                <BarChart3 className="w-5 h-5" />
                行业分析
              </button>
            </nav>
          </div>
        )}
      </div>
    </header>
  )
}

export default Header
