/**
 * @jest-environment jsdom
 */

import { exportToCSV } from '../utils/export'

describe('Export Utils', () => {
  describe('exportToCSV', () => {
    it('should exist as a function', () => {
      expect(typeof exportToCSV).toBe('function')
    })

    it('should handle empty data', () => {
      // 记录alert调用
      const alertSpy = jest.spyOn(window, 'alert').mockImplementation(() => {})

      exportToCSV([])
      expect(alertSpy).toHaveBeenCalledWith('没有数据可导出')

      alertSpy.mockRestore()
    })

    it('should handle valid data', () => {
      const data = [
        {
          code: '600519',
          name: '贵州茅台',
          price: 1800.0,
          change_pct: 2.5,
          total_cp: 85.5,
          growth_score: 80.0,
          value_score: 90.0,
          momentum_score: 70.0,
          pe: 45.0,
          roe: 30.0,
          net_profit_growth: 20.0,
          revenue_growth: 15.0
        }
      ]

      // 创建mock blob和link
      const mockCreateObjectURL = jest.fn(() => 'blob:test')
      const mockRevokeObjectURL = jest.fn()
      global.URL.createObjectURL = mockCreateObjectURL
      global.URL.revokeObjectURL = mockRevokeObjectURL

      const mockAppendChild = jest.fn()
      const mockRemoveChild = jest.fn()
      const mockClick = jest.fn()
      global.document.body.appendChild = mockAppendChild
      global.document.body.removeChild = mockRemoveChild

      // 创建一个mock link元素
      const mockLink = {
        setAttribute: jest.fn(),
        click: mockClick,
        get href() { return '' }
      }
      jest.spyOn(document, 'createElement').mockReturnValue(mockLink)

      exportToCSV(data)

      expect(mockCreateObjectURL).toHaveBeenCalled()
      expect(mockAppendChild).toHaveBeenCalled()
      expect(mockClick).toHaveBeenCalled()
      expect(mockRemoveChild).toHaveBeenCalled()

      // 清理
      mockCreateObjectURL.mockRestore()
      mockRevokeObjectURL.mockRestore()
    })
  })
})
