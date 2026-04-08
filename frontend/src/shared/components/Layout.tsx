import { Outlet } from 'react-router-dom'
import { Header, Sidebar } from './organisms'
import { useUIStore } from '../stores'

interface LayoutProps {
  onSearch?: (query: string) => void
  version?: string
}

export function Layout({ onSearch, version }: LayoutProps) {
  const { sidebarCollapsed } = useUIStore()

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <Header onSearch={onSearch} version={version} />
      <div className="flex">
        <Sidebar />
        <main
          className={`
            flex-1 p-4 transition-all duration-300
            ${sidebarCollapsed ? 'lg:ml-0' : 'lg:ml-0'}
          `}
        >
          <div className="container mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
