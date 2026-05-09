import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { Watchlist } from './Watchlist'
import { renderWithProviders } from '../../test-utils'

const mockUseWatchlistGroups = vi.fn()
const mockUseSaveWatchlistGroups = vi.fn()

vi.mock('../../shared/hooks/useApi', () => ({
  useWatchlistGroups: (...args: unknown[]) => mockUseWatchlistGroups(...args),
  useSaveWatchlistGroups: (...args: unknown[]) => mockUseSaveWatchlistGroups(...args),
}))

describe('Watchlist', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Mock localStorage
    vi.stubGlobal('localStorage', {
      getItem: vi.fn().mockReturnValue(null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    })
  })

  it('shows empty message when no groups', () => {
    mockUseWatchlistGroups.mockReturnValue({ data: [], isLoading: false })
    mockUseSaveWatchlistGroups.mockReturnValue({ mutate: vi.fn() })
    renderWithProviders(<Watchlist />)
    expect(screen.getByText('暂无自选股分组，点击上方创建')).toBeInTheDocument()
  })

  it('renders group list when groups exist', () => {
    const mockGroups = [
      { id: '1', name: '我的重仓', codes: ['600519', '000001'], color: '#3B82F6' },
    ]
    mockUseWatchlistGroups.mockReturnValue({ data: mockGroups, isLoading: false })
    mockUseSaveWatchlistGroups.mockReturnValue({ mutate: vi.fn() })
    renderWithProviders(<Watchlist />)
    expect(screen.getByText('我的重仓')).toBeInTheDocument()
    expect(screen.getByText('600519')).toBeInTheDocument()
    expect(screen.getByText('000001')).toBeInTheDocument()
  })

  it('can create a new group', () => {
    const saveMutate = vi.fn()
    mockUseWatchlistGroups.mockReturnValue({ data: [], isLoading: false })
    mockUseSaveWatchlistGroups.mockReturnValue({ mutate: saveMutate })
    renderWithProviders(<Watchlist />)

    fireEvent.change(screen.getByPlaceholderText('如: 我的重仓'), {
      target: { value: '新分组' },
    })
    fireEvent.change(screen.getByPlaceholderText('000001, 000002, 600519'), {
      target: { value: '600036, 000002' },
    })
    fireEvent.click(screen.getByRole('button', { name: '创建' }))

    expect(saveMutate).toHaveBeenCalled()
    const callArg = saveMutate.mock.calls[0][0]
    expect(callArg[0].name).toBe('新分组')
    expect(callArg[0].codes).toEqual(['600036', '000002'])
  })

  it('can delete a group', () => {
    const saveMutate = vi.fn()
    const mockGroups = [
      { id: '1', name: '测试分组', codes: ['600519'], color: '#3B82F6' },
    ]
    mockUseWatchlistGroups.mockReturnValue({ data: mockGroups, isLoading: false })
    mockUseSaveWatchlistGroups.mockReturnValue({ mutate: saveMutate })
    renderWithProviders(<Watchlist />)

    fireEvent.click(screen.getByRole('button', { name: '删除' }))
    expect(saveMutate).toHaveBeenCalledWith([])
  })

  it('shows loading state', () => {
    mockUseWatchlistGroups.mockReturnValue({ data: undefined, isLoading: true })
    mockUseSaveWatchlistGroups.mockReturnValue({ mutate: vi.fn() })
    renderWithProviders(<Watchlist />)
    expect(screen.getByText('加载中...')).toBeInTheDocument()
  })
})
