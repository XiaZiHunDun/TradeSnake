import { Component } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo)
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null })
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center py-20">
          <div className="bg-cp-low/10 border border-cp-low/30 rounded-xl p-8 text-center max-w-md">
            <AlertTriangle className="w-16 h-16 text-cp-low mx-auto mb-4" />
            <h2 className="text-xl font-bold text-white mb-2">页面出错了</h2>
            <p className="text-gray-400 mb-4">
              抱歉，页面遇到了一些问题。请尝试刷新页面。
            </p>
            <button
              onClick={this.handleReload}
              className="flex items-center gap-2 px-4 py-2 bg-accent-blue text-white rounded-lg hover:bg-accent-blue/80 mx-auto transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              刷新页面
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
