import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { Backtest } from './Backtest'
import { renderWithProviders } from '../../test-utils'

const mockUseBacktest = vi.fn()

vi.mock('../../shared/hooks/useApi', () => ({
  useBacktest: (...args: unknown[]) => mockUseBacktest(...args),
}))

const mockBacktestResult = {
  total_return: 15.5,
  annualized_return: 18.2,
  sharpe_ratio: 1.8,
  max_drawdown: -8.5,
  win_rate: 62.5,
  total_trades: 45,
  monthly_returns: [
    { month: '2024-01', return: 2.5 },
    { month: '2024-02', return: -1.2 },
  ],
}

describe('Backtest', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders form with date and number inputs', () => {
    mockUseBacktest.mockReturnValue({ mutate: vi.fn(), isPending: false, data: undefined, error: null })
    renderWithProviders(<Backtest />)
    expect(screen.getByText('回测参数')).toBeInTheDocument()
    expect(screen.getByText('回测结果')).toBeInTheDocument()
  })

  it('calls backtest mutation when run button clicked', () => {
    const mutate = vi.fn()
    mockUseBacktest.mockReturnValue({ mutate, isPending: false, data: undefined, error: null })
    renderWithProviders(<Backtest />)
    fireEvent.click(screen.getByRole('button', { name: '运行回测' }))
    expect(mutate).toHaveBeenCalledWith({
      start_date: '2024-01-01',
      end_date: '2024-12-31',
      holding_days: 30,
      top_n: 10,
    })
  })

  it('displays backtest results when available', () => {
    mockUseBacktest.mockReturnValue({ mutate: vi.fn(), isPending: false, data: mockBacktestResult, error: null })
    renderWithProviders(<Backtest />)
    expect(screen.getByText('15.50%')).toBeInTheDocument()
    expect(screen.getByText('18.20%')).toBeInTheDocument()
  })

  it('shows pending state while running', () => {
    mockUseBacktest.mockReturnValue({ mutate: vi.fn(), isPending: true, data: undefined, error: null })
    renderWithProviders(<Backtest />)
    expect(screen.getByText('回测运行中...')).toBeInTheDocument()
  })

  it('shows error state on failure', () => {
    mockUseBacktest.mockReturnValue({ mutate: vi.fn(), isPending: false, data: undefined, error: { message: 'Network error' } })
    renderWithProviders(<Backtest />)
    expect(screen.getByText(/回测失败:/)).toBeInTheDocument()
  })
})