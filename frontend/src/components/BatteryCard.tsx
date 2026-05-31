import { BatteryData } from '../types'

interface Props {
  battery: BatteryData
}

export function BatteryCard({ battery }: Props) {
  const { soc_pct, mode, available_kwh, voltage_v, power_kw } = battery
  const radius = 54
  const circumference = 2 * Math.PI * radius
  const dashoffset = circumference * (1 - soc_pct / 100)

  const color =
    soc_pct > 50 ? '#22d3ee'
    : soc_pct > 20 ? '#facc15'
    : '#f87171'

  const modeLabel =
    mode === 'charging' ? '↓ Carregando'
    : mode === 'discharging' ? '↑ Descarregando'
    : 'Idle'

  const modeColor =
    mode === 'charging' ? 'text-green-400'
    : mode === 'discharging' ? 'text-orange-400'
    : 'text-gray-500'

  return (
    <div className="bg-gray-900 rounded-2xl p-5 flex flex-col items-center gap-3 group hover:bg-gray-800 transition-colors cursor-default">
      <div className="text-gray-400 text-sm font-semibold uppercase tracking-wide">Bateria</div>

      {/* Circular gauge */}
      <div className="relative w-32 h-32">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 128 128">
          {/* Track */}
          <circle
            cx="64" cy="64" r={radius}
            fill="none"
            stroke="#1f2937"
            strokeWidth="10"
          />
          {/* Fill */}
          <circle
            cx="64" cy="64" r={radius}
            fill="none"
            stroke={color}
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={dashoffset}
            style={{ transition: 'stroke-dashoffset 0.8s ease, stroke 0.5s ease' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold" style={{ color }}>{soc_pct}%</span>
          <span className="text-gray-400 text-xs">{available_kwh.toFixed(1)} kWh</span>
        </div>
      </div>

      {/* Mode + details */}
      <div className={`text-sm font-semibold ${modeColor}`}>{modeLabel}</div>
      <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-center">
        <div>
          <div className="text-gray-500 text-xs">Potência</div>
          <div className="text-white text-sm font-medium">
            {Math.abs(power_kw).toFixed(2)} kW
          </div>
        </div>
        <div>
          <div className="text-gray-500 text-xs">Tensão</div>
          <div className="text-white text-sm font-medium">{voltage_v.toFixed(1)} V</div>
        </div>
      </div>
    </div>
  )
}
