import { useNavigate, useLocation } from 'react-router-dom'
import { Activity, Map, User, Sliders, ChevronRight, Timer, Radio } from 'lucide-react'

const NAV = [
  { label: 'RACE CONTROL', icon: Activity, path: 'race' },
  { label: 'TELEMETRY',    icon: Map,      path: 'telemetry' },
  { label: 'DRIVER INTEL', icon: User,     path: 'intel' },
  { label: 'SCENARIO',     icon: Sliders,  path: 'scenario' },
  { label: 'TIMING',       icon: Timer,    path: 'timing' },
  { label: 'RC FEED',      icon: Radio,    path: 'radio' },
]

export default function StatusBanner({ year, gp, round }) {
  const navigate = useNavigate()
  const location = useLocation()

  const go = (path) => {
    if (year && gp) {
      navigate(`/${path}/${year}/${encodeURIComponent(gp)}`)
    } else {
      navigate('/')
    }
  }

  const activePath = location.pathname.split('/')[1] || 'race'

  return (
    <header style={{ background: '#0a0a0f', borderBottom: '1px solid #1e2535' }}>
      {/* Top info bar */}
      <div style={{ background: '#0d0d1a', borderBottom: '1px solid #1e2535' }}
        className="flex items-center justify-between px-4 py-1">
        <div className="flex items-center gap-3">
          <div style={{ width: 3, height: 18, background: '#E8002D', borderRadius: 1 }} />
          <span className="font-mono font-bold text-white tracking-widest text-xs uppercase">
            F1 WINNER PREDICTOR
          </span>
        </div>
        <div className="flex items-center gap-2 font-mono text-xs">
          {year && gp ? (
            <>
              <span style={{ color: '#E8002D' }} className="font-bold">{year}</span>
              <ChevronRight size={10} style={{ color: '#3d4f66' }} />
              <span className="text-white font-bold uppercase tracking-wide">
                {gp.replace(' Grand Prix', ' GP')}
              </span>
              {round && (
                <>
                  <ChevronRight size={10} style={{ color: '#3d4f66' }} />
                  <span style={{ color: '#3d4f66' }}>RD {round}</span>
                </>
              )}
            </>
          ) : (
            <span style={{ color: '#3d4f66' }} className="tracking-widest">SELECT RACE</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#00ff88',
            boxShadow: '0 0 6px #00ff88' }} />
          <span className="font-mono text-xs" style={{ color: '#3d4f66' }}>SYSTEM LIVE</span>
        </div>
      </div>

      {/* Nav tabs */}
      <div className="flex items-center px-4" style={{ gap: 2 }}>
        {NAV.map(({ label, icon: Icon, path }) => {
          const active = activePath === path
          return (
            <button
              key={path}
              onClick={() => go(path)}
              className="flex items-center gap-2 px-4 py-2 font-mono text-xs tracking-widest transition-all duration-150"
              style={{
                borderBottom: active ? '2px solid #E8002D' : '2px solid transparent',
                color: active ? '#fff' : '#3d4f66',
                background: active ? 'rgba(232,0,45,0.06)' : 'transparent',
                cursor: 'pointer',
              }}
            >
              <Icon size={11} />
              {label}
            </button>
          )
        })}
      </div>
    </header>
  )
}
