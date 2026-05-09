import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StockCard } from './StockCard'
import type { StockCP } from '../../types'

const mockStock: StockCP = {
  code: '600519',
  name: '贵州茅台',
  price: 1800,
  change_pct: 1.52,
  change: 27,
  changePercent: 1.52,
  total_cp: 85.3,
  growth_score: 70,
  value_score: 80,
  quality_score: 90,
  momentum_score: 60,
  pe: 30,
  risk_score: 20,
}

describe('StockCard', () => {
  it('renders stock name and code', () => {
    render(<StockCard stock={mockStock} />)
    expect(screen.getByText('贵州茅台')).toBeInTheDocument()
    expect(screen.getByText('600519')).toBeInTheDocument()
  })

  it('shows positive change in red', () => {
    render(<StockCard stock={mockStock} />)
    const priceEl = screen.getByText('1800.00').closest('div')
    expect(priceEl?.className).toContain('text-red-500')
  })

  it('shows negative change in green', () => {
    const downStock: StockCP = { ...mockStock, change: -15, changePercent: -0.83 }
    render(<StockCard stock={downStock} />)
    const priceEl = screen.getByText('1800.00').closest('div')
    expect(priceEl?.className).toContain('text-green-500')
  })

  it('calls onClick with code when clicked', () => {
    const handleClick = vi.fn()
    render(<StockCard stock={mockStock} onClick={handleClick} />)
    screen.getByText('贵州茅台').click()
    expect(handleClick).toHaveBeenCalledWith('600519')
  })

  it('calls onAddWatchlist when add button clicked', () => {
    const handleAdd = vi.fn()
    render(<StockCard stock={mockStock} onAddWatchlist={handleAdd} />)
    screen.getByText('+ 加自选').click()
    expect(handleAdd).toHaveBeenCalledWith('600519')
  })
})
