import { useSSE } from './hooks/useSSE'
import { Header } from './components/Header'
import { PowerFlow } from './components/PowerFlow'
import { BatteryCard } from './components/BatteryCard'
import { StatsBar } from './components/StatsBar'
import { PVDetail } from './components/PVDetail'
import { HistoryChart } from './components/HistoryChart'
import { AlertsList } from './components/AlertsList'

export default function App() {
  const { snapshot, connected, lastUpdate } = useSSE('/api/events')

  if (!snapshot) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-center">
          <div className="text-5xl mb-4 animate-spin">☀️</div>
          <div className="text-gray-400 text-lg">Conectando ao inversor...</div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-950">
      <Header
        source={snapshot.source}
        connected={connected}
        lastUpdate={lastUpdate}
        tempC={snapshot.inverter.temp_c}
      />

      <main className="max-w-7xl mx-auto px-4 py-6 flex flex-col gap-6">
        {/* Power flow diagram */}
        <PowerFlow snapshot={snapshot} />

        {/* Stats row */}
        <StatsBar
          energy={snapshot.energy}
          inverter={snapshot.inverter}
          source={snapshot.source}
        />

        {/* Cards grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <BatteryCard battery={snapshot.battery} />
          <PVDetail solar={snapshot.solar} />
          <AlertsList alerts={snapshot.alerts} />
        </div>

        {/* History chart */}
        <HistoryChart />
      </main>
    </div>
  )
}
