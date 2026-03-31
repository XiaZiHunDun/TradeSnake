// 数据导出工具函数

/**
 * 导出股票数据为CSV
 */
export function exportToCSV(data, filename = 'stocks_export') {
  if (!data || data.length === 0) {
    alert('没有数据可导出')
    return
  }

  // CSV表头
  const headers = [
    '排名',
    '股票代码',
    '股票名称',
    '现价',
    '涨跌幅',
    '战力值',
    '成长分',
    '价值分',
    '趋势分',
    '市盈率(PE)',
    'ROE',
    '净利润增速',
    '营收增速'
  ]

  // 构建CSV内容
  const csvRows = [headers.join(',')]

  data.forEach((stock, index) => {
    const row = [
      index + 1,
      stock.code,
      stock.name,
      stock.price.toFixed(2),
      stock.change_pct.toFixed(2) + '%',
      stock.total_cp.toFixed(2),
      stock.growth_score.toFixed(2),
      stock.value_score.toFixed(2),
      stock.momentum_score.toFixed(2),
      stock.pe > 0 ? stock.pe.toFixed(2) : 'N/A',
      stock.roe.toFixed(2) + '%',
      stock.net_profit_growth.toFixed(2) + '%',
      stock.revenue_growth.toFixed(2) + '%'
    ]
    csvRows.push(row.map(v => `"${v}"`).join(','))
  })

  const csvContent = '\ufeff' + csvRows.join('\n') // \ufeff for UTF-8 BOM
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)

  const link = document.createElement('a')
  link.setAttribute('href', url)
  link.setAttribute('download', `${filename}_${new Date().toISOString().slice(0, 10)}.csv`)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

/**
 * 导出股票数据为JSON
 */
export function exportToJSON(data, filename = 'stocks_export') {
  if (!data || data.length === 0) {
    alert('没有数据可导出')
    return
  }

  const exportData = {
    exportTime: new Date().toISOString(),
    totalCount: data.length,
    data: data.map((stock, index) => ({
      rank: index + 1,
      code: stock.code,
      name: stock.name,
      price: stock.price,
      changePct: stock.change_pct,
      totalCP: stock.total_cp,
      growthScore: stock.growth_score,
      valueScore: stock.value_score,
      momentumScore: stock.momentum_score,
      pe: stock.pe,
      roe: stock.roe,
      netProfitGrowth: stock.net_profit_growth,
      revenueGrowth: stock.revenue_growth
    }))
  }

  const jsonContent = JSON.stringify(exportData, null, 2)
  const blob = new Blob([jsonContent], { type: 'application/json;charset=utf-8;' })
  const url = URL.createObjectURL(blob)

  const link = document.createElement('a')
  link.setAttribute('href', url)
  link.setAttribute('download', `${filename}_${new Date().toISOString().slice(0, 10)}.json`)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

/**
 * 导出股票数据为Excel (使用SheetJS)
 */
export function exportToExcel(data, filename = 'stocks_export') {
  if (!data || data.length === 0) {
    alert('没有数据可导出')
    return
  }

  // 动态导入xlsx库
  import('xlsx').then(XLSX => {
    // 准备数据
    const worksheetData = [
      ['排名', '股票代码', '股票名称', '现价', '涨跌幅', '战力值', '成长分', '价值分', '趋势分', '市盈率(PE)', 'ROE', '净利润增速', '营收增速']
    ]

    data.forEach((stock, index) => {
      worksheetData.push([
        index + 1,
        stock.code,
        stock.name,
        stock.price,
        stock.change_pct,
        stock.total_cp,
        stock.growth_score,
        stock.value_score,
        stock.momentum_score,
        stock.pe > 0 ? stock.pe : 'N/A',
        stock.roe,
        stock.net_profit_growth,
        stock.revenue_growth
      ])
    })

    // 创建工作簿和工作表
    const worksheet = XLSX.utils.aoa_to_sheet(worksheetData)
    const workbook = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(workbook, worksheet, '战力榜')

    // 设置列宽
    worksheet['!cols'] = [
      { wch: 6 },  // 排名
      { wch: 10 }, // 股票代码
      { wch: 10 }, // 股票名称
      { wch: 8 },  // 现价
      { wch: 8 },  // 涨跌幅
      { wch: 8 },  // 战力值
      { wch: 8 },  // 成长分
      { wch: 8 },  // 价值分
      { wch: 8 },  // 趋势分
      { wch: 10 }, // PE
      { wch: 8 },  // ROE
      { wch: 10 }, // 净利润增速
      { wch: 10 }  // 营收增速
    ]

    // 导出文件
    XLSX.writeFile(workbook, `${filename}_${new Date().toISOString().slice(0, 10)}.xlsx`)
  }).catch(err => {
    console.error('Failed to load xlsx library:', err)
    alert('导出Excel失败，请稍后重试')
  })
}

/**
 * 导出持仓数据为CSV
 */
export function exportHoldingsToCSV(holdings, stockDataMap, filename = 'holdings_export') {
  if (!holdings || holdings.length === 0) {
    alert('没有持仓数据可导出')
    return
  }

  const headers = [
    '股票代码',
    '股票名称',
    '持股数量',
    '成本价',
    '现价',
    '战力值',
    '战力贡献',
    '涨跌幅',
    'ROE',
    '市盈率(PE)'
  ]

  const csvRows = [headers.join(',')]

  holdings.forEach(holding => {
    const data = stockDataMap[holding.code]
    const row = [
      holding.code,
      holding.name || '',
      holding.quantity,
      holding.costPrice > 0 ? holding.costPrice.toFixed(2) : 'N/A',
      data ? data.price.toFixed(2) : 'N/A',
      data ? data.total_cp.toFixed(2) : 'N/A',
      data ? (data.total_cp * holding.quantity).toFixed(2) : 'N/A',
      data ? (data.change_pct >= 0 ? '+' : '') + data.change_pct.toFixed(2) + '%' : 'N/A',
      data && data.roe > 0 ? data.roe.toFixed(2) + '%' : 'N/A',
      data && data.pe > 0 ? data.pe.toFixed(2) : 'N/A'
    ]
    csvRows.push(row.map(v => `"${v}"`).join(','))
  })

  const csvContent = '\ufeff' + csvRows.join('\n')
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)

  const link = document.createElement('a')
  link.setAttribute('href', url)
  link.setAttribute('download', `${filename}_${new Date().toISOString().slice(0, 10)}.csv`)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

/**
 * 导出自选股列表
 */
export function exportWatchlistToFile(codes, filename = 'watchlist_export') {
  if (!codes || codes.length === 0) {
    alert('没有自选股可导出')
    return
  }

  const content = codes.join('\n')
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8;' })
  const url = URL.createObjectURL(blob)

  const link = document.createElement('a')
  link.setAttribute('href', url)
  link.setAttribute('download', `${filename}_${new Date().toISOString().slice(0, 10)}.txt`)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

/**
 * 导入自选股列表
 */
export function importWatchlistFromFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const content = e.target.result
        // 支持两种格式：1. 每行一个代码 2. CSV格式
        const lines = content.split(/[\r\n,]+/).map(l => l.trim()).filter(l => l)
        // 验证并清理代码格式
        const codes = lines.map(code => {
          code = code.toUpperCase().trim()
          // 移除引号
          code = code.replace(/"/g, '').replace(/'/g, '')
          // 验证是否为有效股票代码
          if (/^[SHZ]?\d{6}$/.test(code)) {
            // 标准化格式
            if (code.startsWith('6')) return 'SH' + code
            if (code.startsWith('0') || code.startsWith('3')) return 'SZ' + code
            return code
          }
          return null
        }).filter(c => c)

        resolve(codes)
      } catch (error) {
        reject(new Error('文件格式错误'))
      }
    }
    reader.onerror = () => reject(new Error('读取文件失败'))
    reader.readAsText(file)
  })
}
