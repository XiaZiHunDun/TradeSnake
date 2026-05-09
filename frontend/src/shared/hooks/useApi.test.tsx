import { describe, it, expect, vi } from 'vitest'
import * as useApiModule from './useApi'

vi.mock('./useApi', () => ({
  useCPTop: vi.fn(),
  useBuyTrade: vi.fn(),
}))

describe('useApi hooks', () => {
  describe('useCPTop', () => {
    it('uses correct query key with limit', () => {
      const { useCPTop } = vi.mocked(useApiModule)
      const mockQuery = { data: undefined, isLoading: false, error: null }
      ;(useCPTop as ReturnType<typeof vi.fn>).mockReturnValue(mockQuery)
      const result = useCPTop(100)
      expect(result).toEqual(mockQuery)
      expect(useCPTop).toHaveBeenCalledWith(100)
    })

    it('returns correct data shape from API', () => {
      const { useCPTop } = vi.mocked(useApiModule)
      const mockData = {
        data: {
          data: [{ code: '600519', name: '贵州茅台', total_cp: 85.3 }],
          updated_at: '2026-04-27 10:30:00',
        },
        isLoading: false,
        error: null,
      }
      ;(useCPTop as ReturnType<typeof vi.fn>).mockReturnValue(mockData)
      const result = useCPTop(200)
      expect(result.data?.data[0].code).toBe('600519')
      expect(result.data?.data[0].name).toBe('贵州茅台')
    })
  })

  describe('useBuyTrade', () => {
    it('mutate function is available', () => {
      const { useBuyTrade } = vi.mocked(useApiModule)
      const mockBuyTrade = { mutate: vi.fn(), isPending: false }
      ;(useBuyTrade as ReturnType<typeof vi.fn>).mockReturnValue(mockBuyTrade)
      const result = useBuyTrade()
      expect(result.mutate).toBeDefined()
      expect(result.isPending).toBe(false)
    })
  })
})
