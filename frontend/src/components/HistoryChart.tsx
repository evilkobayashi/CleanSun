import React, { useState, useEffect } from 'react'
import {
  ComposedChart, Area, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, Brush,
} from 'recharts'
import { HistoryRow } from '../types'

type Bucket = 'hour' | 'day' | 'month'
type Period = { label: string; days: number; bucket: Bucket }

const PERIODS: Period[] = [
  { label: 'Hoje',   days: 1,   bucket: 'hour'  },
  { label: '7 dias', days: 7,   bucket: 'hour'  },
  { label: '30 dias',days: 30,  bucket: 'day'   },
  { label: '1 ano',  days: 365, bucket: 'month' },
]

function formatTs(ts: number, bucket: Bucket): string {
  const d = new Date(ts * 1000)
  if (bucket === 'hour') return d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
  if (bucket === 'day')  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
  return d.toLocaleDateString('pt-BR', { month: 'short', year: '2-digit' })
}

interface CustomTooltipProps {
  active?: boolean
  payload?: Array<{ name: string; value: number; color: string }>
  label?: string
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 text-xs shadow-xl">
      <div className="text-gray-400 mb-2 font-medium">{label}</div>
      {payload.map(p => (
        <div key={p.name} className="flex justify-between gap-4" style={{ color: p.color }}>
          <span>{p.name}</span>
          <span className="font-bold">{typeof p.value === 'number' ? p.value.toFixed(1) : p.value}</span>
        </div>
      ))}
    </div>
  )
}

export function HistoryChart() {
  const [period, setPeriod] = useState<Period>(PERIODS[1])
  const [data, setData] = useState<HistoryRow[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    fetch(`/api/history?days=${period.days}&bucket=${period.bucket}`)
      .then(r => r.json())
      .then(j => setData(j.rows ?? []))
      .catch(() => setData([]))
      .finally(() => setLoading(false))
  }, [period])

  const chartData = data.map(row => ({
    time: formatTs(row.ts, period.bucket),
    'Solar (W)': Math.round(row.solar_w),
    'Consumo (W)': Math.round(row.load_w),
    'SOC (%)': Math.round(row.battery_soc),
    'Grid (kW)': parseFloat(row.grid_kw.toFixed(2)),
  }))

  return (
    <div className="bg-gray-900 rounded-2xl p-5 flex flex-col gap-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="text-gray-400 text-sm font-semibold uppercase tracking-wide">Histórico</div>
        <div className="flex gap-2">
          {PERIODS.map(p => (
            <button
              key={p.label}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                period.label === p.label
                  ? 'bg-yellow-400 text-gray-900'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-white'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64 text-gray-500">Carregando...</div>
      ) : data.length === 0 ? (
        <div className="flex items-center justify-center h-64 text-gray-600">Sem dados para este período</div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis
              dataKey="time"
              tick={{ fill: '#6b7280', fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              yAxisId="power"
              tick={{ fill: '#6b7280', fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={45}
            />
            <YAxis
              yAxisId="soc"
              orientation="right"
              domain={[0, 100]}
              tick={{ fill: '#6b7280', fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={35}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ fontSize: '12px', paddingTop: '12px' }}
              formatter={(value) => <span style={{ color: '#9ca3af' }}>{value}</span>}
            />
            <Area
              yAxisId="power"
              type="monotone"
              dataKey="Solar (W)"
              stroke="#facc15"
              fill="#facc1520"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
            <Area
              yAxisId="power"
              type="monotone"
              dataKey="Consumo (W)"
              stroke="#4ade80"
              fill="#4ade8015"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
            <Bar
              yAxisId="power"
              dataKey="Grid (kW)"
              fill="#c084fc"
              opacity={0.7}
              radius={[2, 2, 0, 0]}
            />
            <Area
              yAxisId="soc"
              type="monotone"
              dataKey="SOC (%)"
              stroke="#22d3ee"
              fill="#22d3ee10"
              strokeWidth={1.5}
              dot={false}
              strokeDasharray="4 2"
            />
            {chartData.length > 20 && (
              <Brush
                dataKey="time"
                height={20}
                stroke="#374151"
                fill="#111827"
                travellerWidth={6}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
