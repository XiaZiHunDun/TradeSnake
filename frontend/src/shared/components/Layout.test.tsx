import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { Routes, Route } from 'react-router-dom'
import { Layout } from './Layout'
import { renderWithProviders } from '../../test-utils'

vi.mock('./organisms/Header', () => ({
  Header: ({ onSearch, version }: { onSearch?: (q: string) => void; version?: string }) => (
    <div data-testid="header">
      <button onClick={() => onSearch?.('test')}>Search</button>
      <span>Version: {version || 'v2.2'}</span>
    </div>
  ),
  Sidebar: () => <div data-testid="sidebar">Sidebar</div>,
}))

describe('Layout', () => {
  it('renders Header component', () => {
    renderWithProviders(<Layout />)
    expect(screen.getByTestId('header')).toBeInTheDocument()
  })

  it('renders Sidebar component', () => {
    renderWithProviders(<Layout />)
    expect(screen.getByTestId('sidebar')).toBeInTheDocument()
  })

  it('renders Outlet for child routes', () => {
    renderWithProviders(
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<div data-testid="child">Child Route</div>} />
        </Route>
      </Routes>,
      { route: '/' }
    )
    expect(screen.getByTestId('child')).toBeInTheDocument()
  })

  it('passes onSearch callback to Header', () => {
    const handleSearch = vi.fn()
    renderWithProviders(<Layout onSearch={handleSearch} />)
    screen.getByText('Search').click()
    expect(handleSearch).toHaveBeenCalledWith('test')
  })

  it('renders default version', () => {
    renderWithProviders(<Layout />)
    expect(screen.getByText('Version: v2.2')).toBeInTheDocument()
  })
})
