import { SolarData } from '../types'

interface PVRowProps {
  label: string
  voltage: number
  current: number
  power: number
}

function PVRow({ label, voltage, current, power }: PVRowProps) {
  const maxW = 4000
  const barWidth = Math.min(100, (power / maxW) * 100)
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <span className="text-yellow-400 font-semibold text-sm">{label}</span>
        <span className="text-white font-bold">{power} W</span>
      </div>
      <div className="w-full h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div
          className="h-full bg-yellow-400 rounded-full transition-all duration-500"
          style={{ width: `${barWidth}%` }}
        />
      </div>
      <div className="flex gap-4 text-xs text-gray-400">
        <span>{voltage.toFixed(1)} V</span>
        <span>{current.toFixed(2)} A</span>
      </div>
    </div>
  )
}

interface Props {
  solar: SolarData
}

export function PVDetail({ solar }: Props) {
  return (
    <div className="bg-gray-900 rounded-2xl p-5 flex flex-col gap-4 hover:bg-gray-800 transition-colors cursor-default">
      <div className="text-gray-400 text-sm font-semibold uppercase tracking-wide">PV Strings</div>
      <PVRow
        label="PV1"
        voltage={solar.pv1_v}
        current={solar.pv1_a}
        power={solar.pv1_w}
      />
      <PVRow
        label="PV2"
        voltage={solar.pv2_v}
        current={solar.pv2_a}
        power={solar.pv2_w}
      />
      <div className="pt-2 border-t border-gray-800 flex justify-between items-center">
        <span className="text-gray-500 text-xs">Total</span>
        <span className="text-yellow-400 font-bold">{(solar.total_w / 1000).toFixed(2)} kW</span>
      </div>
    </div>
  )
}
