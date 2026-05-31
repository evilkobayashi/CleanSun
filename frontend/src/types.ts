export interface SolarData {
  pv1_w: number
  pv2_w: number
  total_w: number
  pv1_v: number
  pv1_a: number
  pv2_v: number
  pv2_a: number
}

export interface BatteryData {
  soc_pct: number
  power_kw: number
  mode: 'charging' | 'discharging' | 'idle'
  voltage_v: number
  available_kwh: number
}

export interface GridData {
  power_kw: number
  voltage_v: number
  frequency_hz: number
  status: string
}

export interface LoadData {
  power_w: number
}

export interface InverterData {
  temp_c: number
  status: string
}

export interface EnergyData {
  today_kwh: number
  total_kwh: number
}

export interface Alert {
  code: string
  msg: string
  severity: string
}

export interface Snapshot {
  timestamp: number
  source: 'lan' | 'cloud' | 'stale'
  solar: SolarData
  battery: BatteryData
  grid: GridData
  load: LoadData
  inverter: InverterData
  energy: EnergyData
  alerts: Alert[]
  stale: boolean
}

export interface HistoryRow {
  ts: number
  solar_w: number
  battery_soc: number
  battery_kw: number
  grid_kw: number
  load_w: number
  temp_c: number
  today_kwh: number
  total_kwh: number
  samples: number
}
