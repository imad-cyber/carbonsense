import { Link } from 'react-router-dom'
import { Compass } from 'lucide-react'

export function NotFoundPage() {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-4 text-center">
      <Compass className="w-10 h-10 text-gray-300 mb-4" />
      <h1 className="text-3xl font-bold text-gray-900">404</h1>
      <p className="text-sm text-gray-500 mt-2 mb-6">This page doesn't exist.</p>
      <Link
        to="/dashboard"
        className="px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700 transition-colors"
      >
        Back to dashboard
      </Link>
    </div>
  )
}
