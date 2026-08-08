import { useLocation } from 'react-router-dom'
import { Wifi, WifiOff } from 'lucide-react'
import { clsx } from 'clsx'
import { useWebSocket } from '@/hooks/useWebSocket'

const PAGE_TITLES: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/companies': 'Companies',
  '/emissions': 'Emission Records',
  '/predictions': 'ML Predictions',
  '/chat': 'ESG Assistant',
  '/reports': 'CSRD Reports',
  '/admin': 'User Management',
}

export function TopBar() {
  const { pathname } = useLocation()
  const title = pathname.startsWith('/companies/')
    ? 'Company Detail'
    : PAGE_TITLES[pathname] ?? 'CarbonSense'

  // Global WS status indicator — connects to company 1 as the demo feed
  const { isConnected } = useWebSocket({ companyId: 1 })

  return (
    <header className="h-14 bg-white border-b border-gray-200 px-4 md:px-6 flex items-center justify-between shrink-0">
      <h1 className="text-base font-semibold text-gray-900">{title}</h1>
      <div className={clsx(
        'flex items-center gap-1.5 text-xs font-medium px-2 py-1 rounded-full',
        isConnected
          ? 'bg-green-50 text-green-700'
          : 'bg-gray-100 text-gray-500'
      )}>
        {isConnected
          ? <><Wifi className="w-3 h-3" /> Live</>
          : <><WifiOff className="w-3 h-3" /> Offline</>
        }
      </div>
    </header>
  )
}
