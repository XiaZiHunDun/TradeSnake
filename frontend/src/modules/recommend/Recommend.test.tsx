import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { Recommend } from './Recommend'
import { renderWithProviders } from '../../test-utils'

const mockUseRecommendations = vi.fn()
const mockUseSwapSuggestions = vi.fn()
const mockUseGainPredictionTop = vi.fn()
const mockUseProbabilityPredictionTop = vi.fn()

vi.mock('../../shared/hooks/useApi', () => ({
  useRecommendations: (...args: unknown[]) => mockUseRecommendations(...args),
  useSwapSuggestions: (...args: unknown[]) => mockUseSwapSuggestions(...args),
  useGainPredictionTop: (...args: unknown[]) => mockUseGainPredictionTop(...args),
  useProbabilityPredictionTop: (...args: unknown[]) => mockUseProbabilityPredictionTop(...args),
}))

const mockRecommendations = {
  data: {
    data: [
      { code: '600519', name: '贵州茅台', total_cp: 85.3, price: 1800, change_pct: 1.5 },
      { code: '600036', name: '招商银行', total_cp: 78.5, price: 35.2, change_pct: 0.8 },
    ],
  },
  isLoading: false,
}

describe('Recommend', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders category selection buttons', () => {
    mockUseRecommendations.mockReturnValue({ data: undefined, isLoading: false })
    mockUseSwapSuggestions.mockReturnValue({ data: undefined, isLoading: false })
    mockUseGainPredictionTop.mockReturnValue({ data: undefined })
    mockUseProbabilityPredictionTop.mockReturnValue({ data: undefined })
    renderWithProviders(<Recommend />)
    expect(screen.getByText('价值型')).toBeInTheDocument()
    expect(screen.getByText('成长型')).toBeInTheDocument()
    expect(screen.getByText('趋势型')).toBeInTheDocument()
    expect(screen.getByText('质量型')).toBeInTheDocument()
  })

  it('switches category on click', () => {
    mockUseRecommendations.mockReturnValue({ ...mockRecommendations })
    mockUseSwapSuggestions.mockReturnValue({ data: undefined, isLoading: false })
    mockUseGainPredictionTop.mockReturnValue({ data: undefined })
    mockUseProbabilityPredictionTop.mockReturnValue({ data: undefined })
    renderWithProviders(<Recommend />)
    expect(screen.getByText('贵州茅台')).toBeInTheDocument()
    fireEvent.click(screen.getByText('成长型'))
    expect(mockUseRecommendations).toHaveBeenCalledWith('growth')
  })

  it('renders recommendation list', () => {
    mockUseRecommendations.mockReturnValue({ ...mockRecommendations })
    mockUseSwapSuggestions.mockReturnValue({ data: undefined, isLoading: false })
    mockUseGainPredictionTop.mockReturnValue({ data: undefined })
    mockUseProbabilityPredictionTop.mockReturnValue({ data: undefined })
    renderWithProviders(<Recommend />)
    expect(screen.getByText('贵州茅台')).toBeInTheDocument()
    expect(screen.getByText('招商银行')).toBeInTheDocument()
  })

  it('renders swap suggestions', () => {
    mockUseRecommendations.mockReturnValue({ ...mockRecommendations })
    const mockSwaps = [{
      from_code: '000001', from_name: '平安银行', from_cp: 70,
      to_code: '600519', to_name: '贵州茅台', to_cp: 85,
      cp_improvement: 15, net_benefit: 1000, trade_cost: 50,
      holding_days_equivalent: 5, action_level: 'buy', action_label: '建议买入',
    }]
    mockUseSwapSuggestions.mockReturnValue({ data: mockSwaps, isLoading: false })
    mockUseGainPredictionTop.mockReturnValue({ data: undefined })
    mockUseProbabilityPredictionTop.mockReturnValue({ data: undefined })
    renderWithProviders(<Recommend />)
    expect(screen.getByText('换出')).toBeInTheDocument()
    expect(screen.getByText('换入')).toBeInTheDocument()
    expect(screen.getByText('平安银行')).toBeInTheDocument()
  })
})
