import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  message: string
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: '' }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center min-h-[300px] text-center p-6">
          <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mb-3">
            <AlertTriangle className="w-6 h-6 text-red-600" />
          </div>
          <h2 className="text-base font-semibold text-gray-900">Something went wrong</h2>
          <p className="mt-1 text-sm text-gray-500 max-w-md">{this.state.message}</p>
          <button
            onClick={() => this.setState({ hasError: false, message: '' })}
            className="mt-4 px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700"
          >
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
