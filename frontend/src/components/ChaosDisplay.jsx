import { AlertTriangle, CloudRain, Flag, Wind } from 'lucide-react'

function chaosLevel(index) {
  if (index >= 0.7) return { label: 'HIGH',   colour: '#E8002D', bg: 'rgba(232,0,45,0.12)' }
  if (index >= 0.4) return { label: 'MEDIUM', colour: '#FFD700', bg: 'rgba(255,215,0,0.10)' }
  return              { label: 'LOW',    colour: '#00ff88', bg: 'rgba(0,255,136,0.08)' }
}

export default function ChaosDisplay({ chaosIndex = 0, scRate = 0, hasPracticeData = false }) {
  const level = chaosLevel(chaosIndex)
  const pct   = Math.round(chaosIndex * 100)
  const bars  = 10
  const filled = Math.round(chaosIndex * bars)

  return (
    <div style={{ padding: '12px 14px' }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <span className="font-mono text-xs tracking-widest uppercase" style={{ color: '#3d4f66' }}>
          Chaos Index
        </span>
        <div style={{
          padding: '2px 8px', borderRadius: 3, background: level.bg,
          display: 'flex', alignItems: 'center', gap: 4,
        }}>
          {level.label === 'HIGH' && <AlertTriangle size={9} style={{ color: level.colour }} />}
          <span style={{ fontFamily: 'monospace', fontSize: 9, fontWeight: 700, color: level.colour }}>
            {level.label}
          </span>
        </div>
      </div>

      {/* Bar + value */}
      <div className="flex items-center gap-3 mb-3">
        <div style={{ flex: 1, display: 'flex', gap: 2 }}>
          {Array.from({ length: bars }).map((_, i) => (
            <div key={i} style={{
              flex: 1, height: 12, borderRadius: 2,
              background: i < filled ? level.colour : 'rgba(255,255,255,0.06)',
              transition: 'background 0.3s ease',
              boxShadow: i < filled ? `0 0 4px ${level.colour}66` : 'none',
            }} />
          ))}
        </div>
        <span style={{ fontFamily: 'monospace', fontSize: 16, fontWeight: 700,
          color: level.colour, minWidth: 40, textAlign: 'right' }}>
          {(chaosIndex).toFixed(2)}
        </span>
      </div>

      {/* Breakdown tiles */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6 }}>
        <Tile icon={Flag} label="Safety Car" value={`${Math.round(scRate * 100)}%`} colour="#FF8000" />
        <Tile icon={Wind} label="Wind" value={chaosIndex > 0.5 ? 'HIGH' : 'LOW'} colour="#64C4FF" />
        <Tile icon={CloudRain} label="Practice" value={hasPracticeData ? 'LOADED' : 'N/A'}
          colour={hasPracticeData ? '#00ff88' : '#3d4f66'} />
      </div>
    </div>
  )
}

function Tile({ icon: Icon, label, value, colour }) {
  return (
    <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 4, padding: '6px 8px',
      border: '1px solid rgba(255,255,255,0.06)' }}>
      <div className="flex items-center gap-1 mb-1">
        <Icon size={8} style={{ color: colour }} />
        <span style={{ fontFamily: 'monospace', fontSize: 7, color: '#3d4f66', textTransform: 'uppercase',
          letterSpacing: '0.05em' }}>{label}</span>
      </div>
      <span style={{ fontFamily: 'monospace', fontSize: 10, fontWeight: 700, color: colour }}>
        {value}
      </span>
    </div>
  )
}
