import React, { useState, useEffect } from 'react'

interface Props {
  source: 'lan' | 'cloud' | 'stale'
  connected: boolean
  lastUpdate: number | null
  tempC: number
}

function useRelativeTime(lastUpdate: number | null): string {
  const [, setTick] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 5000)
    return () => clearInterval(id)
  }, [])
  if (!lastUpdate) return '–'
  const secs = Math.round((Date.now() - lastUpdate) / 1000)
  if (secs < 60) return `${secs}s atrás`
  if (secs < 3600) return `${Math.floor(secs / 60)}min atrás`
  return `${Math.floor(secs / 3600)}h atrás`
}

export function Header({ source, connected, lastUpdate, tempC }: Props) {
  const relTime = useRelativeTime(lastUpdate)

  const sourceBadge =
    source === 'lan'   ? { label: 'LAN',   color: 'bg-green-500'  } :
    source === 'cloud' ? { label: 'Cloud', color: 'bg-blue-500'   } :
                         { label: 'Stale', color: 'bg-red-500'    }

  return (
    <header className="flex items-center justify-between px-6 py-4 bg-gray-900 border-b border-gray-800 sticky top-0 z-10">
      <div className="flex items-center gap-3">
        <span className="text-2xl">☀️</span>
        <span className="text-white font-bold text-xl tracking-tight">CleanSun</span>
      </div>

      <div className="flex items-center gap-4 text-sm">
        <div className="flex items-center gap-1.5">
          <span
            className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400 animate-pulse' : 'bg-red-500'}`}
          />
          <span className={`font-medium px-2 py-0.5 rounded-full text-white text-xs ${sourceBadge.color}`}>
            {sourceBadge.label}
          </span>
        </div>
        <div className="text-blue-400 font-medium">{tempC.toFixed(1)}°C</div>
        <div className="text-gray-500 text-xs hidden sm:block">última: {relTime}</div>
      </div>
    </header>
  )
}
