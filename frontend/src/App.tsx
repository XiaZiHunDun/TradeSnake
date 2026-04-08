import { Routes, Route, useNavigate } from 'react-router-dom'
import { Layout } from './shared/components/Layout'
import { TopList } from './modules/market/TopList'
import { StockDetail } from './modules/stock/StockDetail'
import { Portfolio } from './modules/portfolio/Portfolio'
import { Watchlist } from './modules/watchlist/Watchlist'
import { Recommend } from './modules/recommend/Recommend'
import { Backtest } from './modules/backtest/Backtest'
import { useCPTop } from './shared/hooks/useApi'
import type { StockCP } from './shared/types'

const FRONTEND_VERSION = 'v2.2'

function App() {
  const navigate = useNavigate()
  const { data } = useCPTop(200)

  const handleSearch = (query: string) => {
    if (!query.trim()) return
    const stocks = data?.data || []
    const matched = stocks.find(
      (s: StockCP) =>
        s.code.toLowerCase().includes(query.toLowerCase()) ||
        s.name.toLowerCase().includes(query.toLowerCase())
    )
    if (matched) {
      navigate(`/stock/${matched.code}`)
    }
  }

  return (
    <Routes>
      <Route element={<Layout onSearch={handleSearch} version={FRONTEND_VERSION} />}>
        <Route path="/" element={<TopList />} />
        <Route path="/market" element={<TopList />} />
        <Route path="/stock/:code" element={<StockDetail />} />
        <Route path="/watchlist" element={<Watchlist />} />
        <Route path="/portfolio" element={<Portfolio />} />
        <Route path="/recommend" element={<Recommend />} />
        <Route path="/backtest" element={<Backtest />} />
      </Route>
    </Routes>
  )
}

export default App
