import React from 'react'
import { Snapshot } from '../types'

interface NodeProps {
  icon: string
  label: string
  value: string
  subtext?: string
  color: string
}

function Node({ icon, label, value, subtext, color }: NodeProps) {
  return (
    <div className="flex flex-col items-center gap-1 group cursor-default">
      <div className={`text-4xl transition-transform group-hover:scale-110 ${color}`}>
        {icon}
      </div>
      <div className="text-white font-bold text-lg leading-tight">{value}</div>
      <div className="text-gray-400 text-xs font-medium">{label}</div>
      {subtext && <div className={`text-xs ${color}`}>{subtext}</div>}
    </div>
  )
}

interface FlowLineProps {
  active: boolean
  watts: number
  direction: 'horizontal' | 'vertical'
  reverse?: boolean
  color: string
}

function FlowLine({ active, watts, color }: FlowLineProps) {
  const duration = active ? Math.max(0.4, 2.5 - watts / 4000) : 99
  return (
    <div className="relative flex items-center justify-center w-full h-1">
      <div className="w-full h-px bg-gray-700" />
      {active && (
        <div
          className="absolute h-0.5 w-8 rounded-full opacity-90"
          style={{
            background: `linear-gradient(90deg, transparent, ${color}, transparent)`,
            animation: `flow ${duration}s linear infinite`,
          }}
        />
      )}
    </div>
  )
}

interface Props {
  snapshot: Snapshot
}

export function PowerFlow({ snapshot }: Props) {
  const { solar, battery, grid, load, inverter } = snapshot
  const solarKw = solar.total_w / 1000
  const loadKw = load.power_w / 1000
  const battKw = Math.abs(battery.power_kw)
  const gridKw = Math.abs(grid.power_kw)

  const battSubtext =
    battery.mode === 'charging'
      ? `↓ ${battKw.toFixed(2)} kW`
      : battery.mode === 'discharging'
      ? `↑ ${battKw.toFixed(2)} kW`
      : 'Idle'

  const gridSubtext =
    grid.power_kw > 0.05
      ? `↑ Importando`
      : grid.power_kw < -0.05
      ? `↓ Exportando`
      : 'Standby'

  return (
    <div className="bg-gray-900 rounded-2xl p-6 w-full select-none">
      <style>{`
        @keyframes flow {
          0% { transform: translateX(-200%); }
          100% { transform: translateX(500%); }
        }
      `}</style>

      {/* Top row: Solar → Inverter → Load */}
      <div className="grid grid-cols-5 items-center gap-2">
        <Node
          icon="☀️"
          label="Solar"
          value={`${solarKw.toFixed(2)} kW`}
          color="text-yellow-400"
        />
        <FlowLine active={solarKw > 0.05} watts={solar.total_w} direction="horizontal" color="#facc15" />
        <Node
          icon="⚡"
          label="Inversor"
          value={inverter.status}
          subtext={`${inverter.temp_c}°C`}
          color="text-blue-400"
        />
        <FlowLine active={loadKw > 0.05} watts={load.power_w} direction="horizontal" color="#4ade80" />
        <Node
          icon="🏠"
          label="Consumo"
          value={`${loadKw.toFixed(2)} kW`}
          color="text-green-400"
        />
      </div>

      {/* Vertical connectors */}
      <div className="grid grid-cols-5 my-2">
        <div />
        <div />
        <div className="flex justify-center">
          <div className="w-px h-8 bg-gray-700 relative overflow-hidden">
            {(battery.mode !== 'idle' || grid.power_kw !== 0) && (
              <div
                className="absolute w-px h-3 rounded-full"
                style={{
                  background: battery.mode === 'charging' ? '#22d3ee' : '#f97316',
                  animation: `flowV 1.5s linear infinite`,
                  top: battery.mode === 'discharging' ? '-12px' : '0',
                }}
              />
            )}
          </div>
        </div>
        <div />
        <div />
      </div>

      {/* Bottom row: Battery ←→ Inverter ←→ Grid */}
      <div className="grid grid-cols-5 items-center gap-2">
        <Node
          icon="🔋"
          label="Bateria"
          value={`${battery.soc_pct}%`}
          subtext={battSubtext}
          color={
            battery.soc_pct > 50
              ? 'text-cyan-400'
              : battery.soc_pct > 20
              ? 'text-yellow-400'
              : 'text-red-400'
          }
        />
        <FlowLine
          active={battery.mode !== 'idle'}
          watts={Math.abs(battery.power_kw) * 1000}
          direction="horizontal"
          color="#22d3ee"
        />
        <div />
        <FlowLine
          active={Math.abs(grid.power_kw) > 0.05}
          watts={Math.abs(grid.power_kw) * 1000}
          direction="horizontal"
          color="#c084fc"
        />
        <Node
          icon="🔌"
          label="Grid"
          value={`${gridKw.toFixed(2)} kW`}
          subtext={gridSubtext}
          color={
            grid.status === 'Normal'
              ? 'text-purple-400'
              : grid.status === 'Alarme'
              ? 'text-red-400'
              : 'text-gray-500'
          }
        />
      </div>
    </div>
  )
}
