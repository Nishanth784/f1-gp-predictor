import { getTeamColour } from './TeamColours'

// Simplified SVG circuit paths keyed by GP name fragments
const CIRCUIT_PATHS = {
  monaco: "M80,15 L140,18 C165,20 185,35 188,60 L190,100 L180,125 C172,145 158,155 140,158 L115,160 L90,185 C78,198 60,204 42,200 L18,192 L8,165 C2,148 8,128 22,118 L38,108 L28,80 C20,60 26,38 42,28 Z",
  silverstone: "M50,60 C45,35 65,15 92,18 L155,25 C178,30 195,50 193,75 L187,118 C182,145 162,162 135,165 L85,170 C58,172 38,158 32,132 L28,105 Z",
  monza: "M45,40 L185,40 C205,40 218,55 218,75 L218,145 C218,165 205,178 185,178 L45,178 C25,178 12,165 12,145 L12,120 L118,120 L118,100 L12,100 L12,75 C12,55 25,40 45,40 Z",
  bahrain: "M48,65 L118,22 C140,10 168,14 185,32 L215,68 C228,86 226,110 212,128 L182,160 C162,178 136,180 114,168 L48,128 C30,116 24,96 32,78 Z",
  "abu dhabi": "M42,80 L82,30 C98,12 122,8 145,20 L188,48 C208,62 215,88 205,112 L185,148 C168,168 142,172 118,162 L75,140 C52,128 40,104 48,82 Z",
  suzuka: "M72,28 L158,28 C180,28 196,44 196,66 L196,98 L128,98 L128,120 L196,120 L196,152 C196,174 180,190 158,190 L72,190 C50,190 34,174 34,152 L34,66 C34,44 50,28 72,28 Z",
  spa: "M35,75 L88,22 C106,5 132,2 155,14 L202,40 C224,54 232,80 225,106 L212,152 C202,175 178,188 152,185 L92,175 C66,168 48,150 42,124 Z",
  singapore: "M60,90 L90,40 C105,20 128,14 152,24 L192,48 C212,62 218,88 208,112 L185,148 C170,168 146,175 122,168 L78,148 C55,138 48,112 58,92 Z",
  austria: "M55,50 L155,50 C178,50 195,67 195,90 L195,135 C195,158 178,175 155,175 L55,175 C32,175 15,158 15,135 L15,90 C15,67 32,50 55,50 Z",
  default: "M60,50 L180,50 C202,50 215,63 215,85 L215,145 C215,167 202,180 180,180 L60,180 C38,180 25,167 25,145 L25,85 C25,63 38,50 60,50 Z",
}

function getCircuitPath(gpName = '') {
  const lower = gpName.toLowerCase()
  for (const [key, path] of Object.entries(CIRCUIT_PATHS)) {
    if (lower.includes(key)) return path
  }
  return CIRCUIT_PATHS.default
}

// Place driver dots evenly around the circuit path (simplified: distribute by index)
const DOT_POSITIONS = [
  { cx: 115, cy: 35 },
  { cx: 175, cy: 65 },
  { cx: 190, cy: 115 },
  { cx: 155, cy: 168 },
  { cx: 80,  cy: 178 },
  { cx: 30,  cy: 148 },
  { cx: 18,  cy: 90 },
  { cx: 45,  cy: 42 },
]

export default function CircuitMap({ gpName = '', drivers = [], width = 240, height = 220 }) {
  const path = getCircuitPath(gpName)
  const top5 = drivers.slice(0, 5)

  return (
    <div style={{ position: 'relative', width, height }}>
      <svg
        viewBox="0 0 240 220"
        width={width}
        height={height}
        style={{ display: 'block' }}
      >
        {/* Glow filter */}
        <defs>
          <filter id="dot-glow">
            <feGaussianBlur stdDeviation="2.5" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <filter id="p1-glow">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        {/* Circuit outline */}
        <path
          d={path}
          fill="none"
          stroke="#1e2a3a"
          strokeWidth="10"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d={path}
          fill="none"
          stroke="#2a3a50"
          strokeWidth="7"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d={path}
          fill="none"
          stroke="#334466"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeDasharray="4 8"
          opacity="0.4"
        />

        {/* Driver dots */}
        {top5.map((driver, i) => {
          const pos = DOT_POSITIONS[i] || DOT_POSITIONS[i % DOT_POSITIONS.length]
          const colour = getTeamColour(driver.team || driver.Team || '')
          const isP1 = i === 0
          return (
            <g key={driver.driver || driver.Driver || i}>
              {/* P1 gets extra glow ring */}
              {isP1 && (
                <circle
                  cx={pos.cx} cy={pos.cy} r={9}
                  fill="none" stroke={colour} strokeWidth="1.5"
                  opacity="0.5"
                  style={{ animation: 'pulse-ring 2s ease-in-out infinite' }}
                />
              )}
              <circle
                cx={pos.cx} cy={pos.cy} r={isP1 ? 6 : 4.5}
                fill={colour}
                filter={isP1 ? 'url(#p1-glow)' : 'url(#dot-glow)'}
              />
              {/* Driver code label */}
              <text
                x={pos.cx} y={pos.cy - (isP1 ? 10 : 8)}
                textAnchor="middle"
                fontSize={isP1 ? 7 : 6}
                fontFamily="monospace"
                fontWeight="bold"
                fill={colour}
                opacity="0.9"
              >
                {(driver.driver || driver.Driver || '').slice(0, 3).toUpperCase()}
              </text>
            </g>
          )
        })}

        {/* No data state */}
        {drivers.length === 0 && (
          <text x="120" y="115" textAnchor="middle" fontSize="9"
            fontFamily="monospace" fill="#3d4f66">
            SELECT RACE TO LOAD
          </text>
        )}
      </svg>
    </div>
  )
}
