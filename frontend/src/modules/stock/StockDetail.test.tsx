import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { StockDetail } from './StockDetail'
import { Routes, Route } from 'react-router-dom'
import { renderWithProviders } from '../../test-utils'

const mockUseStockDetail = vi.fn()
const mockUseGainPredictionStock = vi.fn()
const mockUseProbabilityPredictionStock = vi.fn()

vi.mock('../../shared/hooks/useApi', () => ({
  useStockDetail: (...args: unknown[]) => mockUseStockDetail(...args),
  useGainPredictionStock: (...args: unknown[]) => mockUseGainPredictionStock(...args),
  useProbabilityPredictionStock: (...args: unknown[]) => mockUseProbabilityPredictionStock(...args),
}))

const mockStockDetail = {
  code: '600519',
  name: '贵州茅台',
  price: 1800,
  change_pct: 1.5,
  total_cp: 85.3,
  growth_score: 70,
  value_score: 80,
  quality_score: 90,
  momentum_score: 60,
  pe: 30,
  pb: 10,
  market_cap: 2000000000000,
  float_market_cap: 1500000000000,
  turnover_rate: 0.5,
  amount: 50000000000,
  high: 1850,
  low: 1750,
  net_profit_growth: 15.5,
  revenue_growth: 12.3,
  roe: 25.6,
  gross_margin: 90,
}

describe('StockDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUseGainPredictionStock.mockReturnValue({ data: undefined })
    mockUseProbabilityPredictionStock.mockReturnValue({ data: undefined })
  })

  it('renders loading state', () => {
    mockUseStockDetail.mockReturnValue({ data: undefined, isLoading: true, error: null })
    renderWithProviders(
      <Routes>
        <Route path="/stock/:code" element={<StockDetail />} />
      </Routes>,
      { route: '/stock/600519' }
    )
    expect(screen.getByText('加载中...')).toBeInTheDocument()
  })

  it('renders error state with back button', () => {
    mockUseStockDetail.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: { message: 'Network error' },
    })
    renderWithProviders(
      <Routes>
        <Route path="/stock/:code" element={<StockDetail />} />
      </Routes>,
      { route: '/stock/600519' }
    )
    expect(screen.getByText('加载失败')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '返回战力榜' })).toBeInTheDocument()
  })

  it('renders stock name and code when data loaded', () => {
    mockUseStockDetail.mockReturnValue({ data: mockStockDetail, isLoading: false, error: null })
    renderWithProviders(
      <Routes>
        <Route path="/stock/:code" element={<StockDetail />} />
      </Routes>,
      { route: '/stock/600519' }
    )
    expect(screen.getByText('贵州茅台')).toBeInTheDocument()
    expect(screen.getByText('600519')).toBeInTheDocument()
  })

  it('renders score cards with correct values', () => {
    mockUseStockDetail.mockReturnValue({ data: mockStockDetail, isLoading: false, error: null })
    renderWithProviders(
      <Routes>
        <Route path="/stock/:code" element={<StockDetail />} />
      </Routes>,
      { route: '/stock/600519' }
    )
    expect(screen.getByText('85.3')).toBeInTheDocument()
    expect(screen.getByText('70.0')).toBeInTheDocument()
    expect(screen.getByText('80.0')).toBeInTheDocument()
  })
})
