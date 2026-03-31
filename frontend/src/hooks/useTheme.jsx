import { createContext, useContext, useState, useEffect } from 'react'

const ThemeContext = createContext()

// 主题配置
const themes = {
  dark: {
    bgPrimary: '#0f0f1a',
    bgCard: '#1a1a2e',
    border: '#2d2d44',
    textPrimary: '#ffffff',
    textSecondary: '#9ca3af',
    cpHigh: '#00ff88',
    cpMid: '#ffd32a',
    cpLow: '#ff4757',
    accentBlue: '#00d9ff',
  },
  light: {
    bgPrimary: '#f5f5f5',
    bgCard: '#ffffff',
    border: '#e5e5e5',
    textPrimary: '#1a1a2e',
    textSecondary: '#6b7280',
    cpHigh: '#00c853',
    cpMid: '#f9a825',
    cpLow: '#d32f2f',
    accentBlue: '#0288d1',
  }
}

export function ThemeProvider({ children }) {
  const [isDark, setIsDark] = useState(() => {
    const saved = localStorage.getItem('tradesnake_theme')
    return saved ? saved === 'dark' : true
  })

  useEffect(() => {
    const root = document.documentElement
    const theme = isDark ? themes.dark : themes.light

    root.style.setProperty('--bg-primary', theme.bgPrimary)
    root.style.setProperty('--bg-card', theme.bgCard)
    root.style.setProperty('--border-color', theme.border)
    root.style.setProperty('--text-primary', theme.textPrimary)
    root.style.setProperty('--text-secondary', theme.textSecondary)
    root.style.setProperty('--cp-high', theme.cpHigh)
    root.style.setProperty('--cp-mid', theme.cpMid)
    root.style.setProperty('--cp-low', theme.cpLow)
    root.style.setProperty('--accent-blue', theme.accentBlue)

    if (isDark) {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }

    try {
      localStorage.setItem('tradesnake_theme', isDark ? 'dark' : 'light')
    } catch (e) {
      console.error('Failed to save theme:', e)
    }
  }, [isDark])

  const toggleTheme = () => setIsDark(!isDark)

  return (
    <ThemeContext.Provider value={{ isDark, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider')
  }
  return context
}
