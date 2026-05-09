import { Link, useLocation } from 'react-router-dom'
import { useUIStore } from '../../stores'
import { SearchBar } from '../molecules'

const navItems = [
  { path: '/', label: '战力榜', key: 'toplist' },
  { path: '/market', label: '行情', key: 'market' },
  { path: '/watchlist', label: '自选', key: 'watchlist' },
  { path: '/portfolio', label: '持仓', key: 'portfolio' },
  { path: '/recommend', label: '推荐', key: 'recommend' },
  { path: '/backtest', label: '回测', key: 'backtest' },
]

interface HeaderProps {
  onSearch?: (query: string) => void
  version?: string
}

export function Header({ onSearch, version = 'v2.2' }: HeaderProps) {
  const location = useLocation()
  const { theme, toggleTheme, toggleSidebar } = useUIStore()

  return (
    <header className="sticky top-0 z-50 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Title */}
          <div className="flex items-center gap-4">
            <button
              onClick={toggleSidebar}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg lg:hidden"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <Link to="/" className="flex items-center gap-2">
              <span className="text-2xl">🐍</span>
              <span className="font-bold text-xl text-gray-900 dark:text-white">
                TradeSnake
              </span>
            </Link>
          </div>

          {/* Search */}
          {onSearch && (
            <div className="hidden md:block flex-1 max-w-md mx-8">
              <SearchBar onSearch={onSearch} />
            </div>
          )}

          {/* Nav & Actions */}
          <div className="flex items-center gap-2">
            <nav className="hidden lg:flex items-center gap-1">
              {navItems.map((item) => (
                <Link
                  key={item.key}
                  to={item.path}
                  className={`
                    px-3 py-2 rounded-lg text-sm font-medium transition-colors
                    ${location.pathname === item.path
                      ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
                      : 'text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800'
                    }
                  `}
                >
                  {item.label}
                </Link>
              ))}
            </nav>

            <button
              onClick={toggleTheme}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg"
              title="切换主题"
            >
              {theme === 'dark' ? '☀️' : '🌙'}
            </button>

            <span className="text-xs text-gray-400 ml-2 hidden sm:inline">
              {version}
            </span>
          </div>
        </div>
      </div>
    </header>
  )
}

// 侧边栏组件
interface SidebarProps {
  className?: string
}

export function Sidebar({ className = '' }: SidebarProps) {
  const location = useLocation()
  const { sidebarCollapsed, toggleSidebar } = useUIStore()

  if (sidebarCollapsed) {
    return (
      <aside className={`fixed left-0 top-16 h-[calc(100vh-4rem)] w-16 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700 z-40 lg:hidden ${className}`}>
        <button onClick={toggleSidebar} className="p-4 w-full">
          <svg className="w-6 h-6 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
          </svg>
        </button>
      </aside>
    )
  }

  return (
    <aside className={`fixed left-0 top-16 h-[calc(100vh-4rem)] w-64 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700 z-40 lg:hidden ${className}`}>
      <div className="p-4 flex justify-between items-center">
        <span className="font-semibold">导航</span>
        <button onClick={toggleSidebar}>
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      <nav className="px-2">
        {navItems.map((item) => (
          <Link
            key={item.key}
            to={item.path}
            className={`
              flex items-center gap-3 px-4 py-3 rounded-lg mb-1
              ${location.pathname === item.path
                ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
                : 'text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800'
              }
            `}
          >
            <span>{item.label}</span>
          </Link>
        ))}
      </nav>
    </aside>
  )
}
