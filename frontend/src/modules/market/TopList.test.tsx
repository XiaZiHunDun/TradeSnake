import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { TopList } from './TopList'
import { renderWithProviders } from '../../test-utils'

const mockUseCPTop = vi.fn()
const mockUseGainPredictionTop = vi.fn()
const mockUseProbabilityPredictionTop = vi.fn()

vi.mock('../../shared/hooks/useApi', () => ({
  useCPTop: (...args: unknown[]) => mockUseCPTop(...args),
  useGainPredictionTop: (...args: unknown[]) => mockUseGainPredictionTop(...args),
  useProbabilityPredictionTop: (...args: unknown[]) => mockUseProbabilityPredictionTop(...args),
}))

const mockStocks = {
  data: {
    data: [
      {
        code: '600519',
        name: '贵州茅台',
        price: 1800,
        change_pct: 1.5,
        total_cp: 85.3,
        growth_score: 70,
        value_score: 80,
        quality_score: 90,
        momentum_score: 60,
      },
      {
        code: '000001',
        name: '平安银行',
        price: 12.5,
        change_pct: -0.8,
        total_cp: 72.1,
        growth_score: 65,
        value_score: 75,
        quality_score: 80,
        momentum_score: 55,
      },
    ],
    updated_at: '2026-04-27 10:30:00',
  },
  isLoading: false,
  error: null,
  refetch: vi.fn(),
}

describe('TopList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders loading state', () => {
    mockUseCPTop.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
    })
    mockUseGainPredictionTop.mockReturnValue({ data: undefined })
    mockUseProbabilityPredictionTop.mockReturnValue({ data: undefined })
    renderWithProviders(<TopList />)
    // Both table empty message and loading indicator show "加载中..."
    expect(screen.getAllByText(/加载中/).length).toBeGreaterThan(0)
  })

  it('renders error state with retry button', () => {
    const refetch = vi.fn()
    mockUseCPTop.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: { message: 'Network error' },
      refetch,
    })
    mockUseGainPredictionTop.mockReturnValue({ data: undefined })
    mockUseProbabilityPredictionTop.mockReturnValue({ data: undefined })
    renderWithProviders(<TopList />)
    expect(screen.getByText(/加载失败/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重试' })).toBeInTheDocument()
  })

  it('renders stock table when data loaded', () => {
    mockUseCPTop.mockReturnValue({ ...mockStocks })
    mockUseGainPredictionTop.mockReturnValue({ data: undefined })
    mockUseProbabilityPredictionTop.mockReturnValue({ data: undefined })
    renderWithProviders(<TopList />)
    expect(screen.getByText('贵州茅台')).toBeInTheDocument()
    expect(screen.getByText('平安银行')).toBeInTheDocument()
  })

  it('filters stocks by up/down', async () => {
    const { act } = await import('react')
    mockUseCPTop.mockReturnValue({ ...mockStocks })
    mockUseGainPredictionTop.mockReturnValue({ data: undefined })
    mockUseProbabilityPredictionTop.mockReturnValue({ data: undefined })
    renderWithProviders(<TopList />)

    expect(screen.getByText('贵州茅台')).toBeInTheDocument()
    expect(screen.getByText('平安银行')).toBeInTheDocument()

    // Click "上涨" filter
    await act(async () => {
      screen.getByRole('button', { name: '上涨' }).click()
    })
    expect(screen.queryByText('平安银行')).not.toBeInTheDocument()

    // Click "下跌" filter
    await act(async () => {
      screen.getByRole('button', { name: '下跌' }).click()
    })
    expect(screen.queryByText('贵州茅台')).not.toBeInTheDocument()

    // Click "全部" filter
    await act(async () => {
      screen.getByRole('button', { name: '全部' }).click()
    })
    expect(screen.getByText('贵州茅台')).toBeInTheDocument()
    expect(screen.getByText('平安银行')).toBeInTheDocument()
  })
})
