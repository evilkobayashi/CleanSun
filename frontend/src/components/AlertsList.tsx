import { Alert } from '../types'

interface Props {
  alerts: Alert[]
}

export function AlertsList({ alerts }: Props) {
  return (
    <div className="bg-gray-900 rounded-2xl p-5 flex flex-col gap-3 hover:bg-gray-800 transition-colors cursor-default">
      <div className="flex items-center justify-between">
        <div className="text-gray-400 text-sm font-semibold uppercase tracking-wide">Alertas</div>
        {alerts.length > 0 && (
          <span className="bg-red-500 text-white text-xs font-bold px-2 py-0.5 rounded-full">
            {alerts.length}
          </span>
        )}
      </div>

      {alerts.length === 0 ? (
        <div className="flex items-center gap-2 text-green-400">
          <span className="text-lg">✓</span>
          <span className="text-sm">Nenhum alerta ativo</span>
        </div>
      ) : (
        <div className="flex flex-col gap-2 max-h-40 overflow-y-auto">
          {alerts.map((alert, i) => (
            <div
              key={i}
              className="flex items-start gap-2 text-sm p-2 bg-gray-800 rounded-lg"
            >
              <span className="text-yellow-400 mt-0.5">⚠</span>
              <div>
                <div className="text-white font-medium">{alert.msg || alert.code}</div>
                <div className="text-gray-500 text-xs">{alert.code}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
