import React from 'react'
import { EnergyData, InverterData } from '../types'

interface StatCardProps {
  label: string
  value: string
  sub?: string
  color?: string
}

function StatCard({ label, value, sub, color = 'text-white' }: StatCardProps) {
  return (
    <div className="bg-gray-900 rounded-2xl p-5 flex flex-col gap-1 hover:bg-gray-800 transition-colors cursor-default group">
      <div className="text-gray-500 text-xs font-semibold uppercase tracking-wide">{label}</div>
      <div className={`text-2xl font-bold ${color} group-hover:scale-105 transition-transform origin-left`}>
        {value}
      </div>
      {sub && <div className="text-gray-500 text-xs">{sub}</div>}
    </div>
  )
}

interface Props {
  energy: EnergyData
  inverter: InverterData
  source: string
}

export function StatsBar({ energy, inverter, source }: Props) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
      <StatCard
        label="Hoje"
        value={`${energy.today_kwh.toFixed(1)} kWh`}
        sub="Geração do dia"
        color="text-yellow-400"
      />
      <StatCard
        label="Total acumulado"
        value={`${(energy.total_kwh / 1000).toFixed(1)} MWh`}
        sub={`${energy.total_kwh.toFixed(0)} kWh`}
        color="text-green-400"
      />
      <StatCard
        label="Temperatura"
        value={`${inverter.temp_c.toFixed(1)}°C`}
        sub="Inversor"
        color={inverter.temp_c > 65 ? 'text-red-400' : inverter.temp_c > 50 ? 'text-yellow-400' : 'text-blue-400'}
      />
      <StatCard
        label="Fonte"
        value={source === 'lan' ? 'LAN' : source === 'cloud' ? 'Cloud' : 'Stale'}
        sub={source === 'lan' ? 'Rede local' : source === 'cloud' ? 'API Deye' : 'Sem dados frescos'}
        color={source === 'lan' ? 'text-green-400' : source === 'cloud' ? 'text-blue-400' : 'text-red-400'}
      />
    </div>
  )
}
