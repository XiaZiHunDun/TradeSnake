import { useState, useEffect, lazy, Suspense } from 'react'
import Header from './components/Header'
import { ToastContainer } from './hooks/useToast'
import ErrorBoundary from './components/ErrorBoundary'
import { useTourGuide, TourGuide } from './components/TourGuide'
import { SettingsModal } from './hooks/useSettings.jsx'
import { SkeletonCard, SkeletonTable } from './components/Skeleton'
import { NotificationProvider } from './hooks/useNotification'
import { FormulaEducation } from './components/FormulaEducation'
import { DataSourceModal } from './components/DataSourceInfo'
import './index.css'

// 懒加载页面组件
const CPTopList = lazy(() => import('./pages/CPTopList'))
const SingleStock = lazy(() => import('./pages/SingleStock'))
const PersonalCP = lazy(() => import('./pages/PersonalCP'))
const Recommend = lazy(() => import('./pages/Recommend'))
const PortfolioSimulator = lazy(() => import('./pages/PortfolioSimulator'))
const RankingChanges = lazy(() => import('./pages/RankingChanges'))
const SectorAnalysis = lazy(() => import('./pages/SectorAnalysis'))

// 页面加载骨架
function PageSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <SkeletonCard />
      </div>
      <div className="bg-card-bg rounded-xl border border-border-dark overflow-hidden">
        <SkeletonTable rows={10} cols={8} />
      </div>
    </div>
  )
}

function App() {
  const [refreshKey, setRefreshKey] = useState(0)
  const [currentPage, setCurrentPage] = useState('toplist') // 'toplist' | 'search' | 'personal' | 'recommend' | 'simulator' | 'rankings' | 'sector'
  const [showSettings, setShowSettings] = useState(false)
  const [showEducation, setShowEducation] = useState(false) // 战力学堂
  const [showDataSource, setShowDataSource] = useState(false) // 数据说明
  const tour = useTourGuide()

  // 键盘快捷键
  useEffect(() => {
    const handleKeyPress = (e) => {
      // 忽略输入框中的按键
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return

      switch (e.key) {
        case '1': setCurrentPage('toplist'); break
        case '2': setCurrentPage('search'); break
        case '3': setCurrentPage('personal'); break
        case '4': setCurrentPage('recommend'); break
        case '5': setCurrentPage('simulator'); break
        case '6': setCurrentPage('rankings'); break
        case '7': setCurrentPage('sector'); break
        case 'r':
        case 'R':
          handleRefresh()
          break
        case 't':
        case 'T':
          // 切换主题
          document.querySelector('button[title*="切换"]')?.click()
          break
        case 'e':
        case 'E':
          setShowEducation(true)
          break
        case 'd':
        case 'D':
          setShowDataSource(true)
          break
        case 's':
        case 'S':
          setShowSettings(true)
          break
        case 'Escape':
          // 关闭弹窗
          document.dispatchEvent(new CustomEvent('close-modal'))
          break
      }
    }

    window.addEventListener('keydown', handleKeyPress)
    return () => window.removeEventListener('keydown', handleKeyPress)
  }, [])

  const handleRefresh = () => {
    setRefreshKey(k => k + 1)
  }

  return (
    <NotificationProvider>
      <div className="min-h-screen bg-deep-night">
        <ErrorBoundary>
          <Header
            onRefresh={handleRefresh}
            currentPage={currentPage}
            onNavigate={setCurrentPage}
            onOpenSettings={() => setShowSettings(true)}
            onOpenEducation={() => setShowEducation(true)}
          />
        <main className="container mx-auto px-4 py-6">
          <ErrorBoundary>
            <Suspense fallback={<PageSkeleton />}>
              {currentPage === 'toplist' && (
                <CPTopList key={refreshKey} />
              )}
              {currentPage === 'search' && (
                <SingleStock />
              )}
              {currentPage === 'personal' && (
                <PersonalCP />
              )}
              {currentPage === 'recommend' && (
                <Recommend />
              )}
              {currentPage === 'simulator' && (
                <PortfolioSimulator />
              )}
              {currentPage === 'rankings' && (
                <RankingChanges />
              )}
              {currentPage === 'sector' && (
                <SectorAnalysis />
              )}
            </Suspense>
          </ErrorBoundary>
        </main>
        <ToastContainer />
        <TourGuide {...tour} />
        <FormulaEducation isOpen={showEducation} onClose={() => setShowEducation(false)} />
        <DataSourceModal isOpen={showDataSource} onClose={() => setShowDataSource(false)} />
        <SettingsModal isOpen={showSettings} onClose={() => setShowSettings(false)} />
      </ErrorBoundary>
      </div>
    </NotificationProvider>
  )
}

export default App
