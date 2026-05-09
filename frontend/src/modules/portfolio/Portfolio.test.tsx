import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { Portfolio } from './Portfolio'
import { renderWithProviders } from '../../test-utils'

const mockUseAccount = vi.fn()
const mockUsePortfolio = vi.fn()
const mockUseBuyTrade = vi.fn()
const mockUseSellTrade = vi.fn()

vi.mock('../../shared/hooks/useApi', () => ({
  useAccount: (...args: unknown[]) => mockUseAccount(...args),
  usePortfolio: (...args: unknown[]) => mockUsePortfolio(...args),
  useBuyTrade: (...args: unknown[]) => mockUseBuyTrade(...args),
  useSellTrade: (...args: unknown[]) => mockUseSellTrade(...args),
}))

const mockAccount = {
  cash: 15000,
  total_assets: 25000,
  total_market_value: 10000,
  total_profit: 500,
  profit_rate: 2.5,
}

const mockPortfolio = {
  holdings: [
    {
      code: '000001',
      name: '平安银行',
      quantity: 500,
      cost_price: 12.5,
      current_price: 13.0,
      market_value: 6500,
      profit: 250,
      profit_rate: 4.0,
    },
  ],
}

describe('Portfolio', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders account overview', () => {
    mockUseAccount.mockReturnValue({ data: mockAccount, isLoading: false })
    mockUsePortfolio.mockReturnValue({ data: undefined })
    mockUseBuyTrade.mockReturnValue({ mutate: vi.fn(), isPending: false })
    mockUseSellTrade.mockReturnValue({ mutate: vi.fn(), isPending: false })
    renderWithProviders(<Portfolio />)
    expect(screen.getByText('账户概览')).toBeInTheDocument()
    expect(screen.getAllByText(/25000/).length).toBeGreaterThan(0)
  })

  it('renders holdings table', () => {
    mockUseAccount.mockReturnValue({ data: mockAccount, isLoading: false })
    mockUsePortfolio.mockReturnValue({ data: mockPortfolio })
    mockUseBuyTrade.mockReturnValue({ mutate: vi.fn(), isPending: false })
    mockUseSellTrade.mockReturnValue({ mutate: vi.fn(), isPending: false })
    renderWithProviders(<Portfolio />)
    expect(screen.getByText('平安银行')).toBeInTheDocument()
    expect(screen.getAllByText('500').length).toBeGreaterThan(0)
  })

  it('buy button calls buy with correct quantity (handles)', () => {
    const buyMutate = vi.fn()
    mockUseAccount.mockReturnValue({ data: mockAccount, isLoading: false })
    mockUsePortfolio.mockReturnValue({ data: mockPortfolio })
    mockUseBuyTrade.mockReturnValue({ mutate: buyMutate, isPending: false })
    mockUseSellTrade.mockReturnValue({ mutate: vi.fn(), isPending: false })
    renderWithProviders(<Portfolio />)
    const codeInput = screen.getByPlaceholderText('如: 000001')
    const qtyInput = screen.getByPlaceholderText('1')
    fireEvent.change(codeInput, { target: { value: '600519' } })
    fireEvent.change(qtyInput, { target: { value: '5' } })
    fireEvent.click(screen.getByRole('button', { name: '买入' }))
    expect(buyMutate).toHaveBeenCalledWith({ code: '600519', quantity: 500 })
  })

  it('shows empty holdings message', () => {
    mockUseAccount.mockReturnValue({ data: mockAccount, isLoading: false })
    mockUsePortfolio.mockReturnValue({ data: { holdings: [] } })
    mockUseBuyTrade.mockReturnValue({ mutate: vi.fn(), isPending: false })
    mockUseSellTrade.mockReturnValue({ mutate: vi.fn(), isPending: false })
    renderWithProviders(<Portfolio />)
    expect(screen.getByText('暂无持仓')).toBeInTheDocument()
  })
})
