import { useEffect, useRef } from "react";

interface FeederLine {
  line_id: string;
  from_node: number;
  to_node: number;
  capacity_kw: number;
  flow_kw: number;
  loss_kw: number;
  utilisation: number;
  is_congested: boolean;
}
interface FeederNode {
  node_id: number;
  name: string;
  type: string;
}
interface FeederState {
  nodes: FeederNode[];
  lines: FeederLine[];
  total_loss_kw: number;
  congested_lines: string[];
  peak_utilisation: number;
}

// Fixed SVG positions for each node
const NODE_POS: Record<number, [number, number]> = {
  1: [250, 40],   // substation top-centre
  2: [130, 130],
  3: [370, 130],
  4: [60,  230],
  5: [200, 230],
  6: [300, 230],
  7: [440, 230],
  8: [440, 320],
};

function utilColor(util: number, congested: boolean): string {
  if (congested)      return "#ef4444";   // red
  if (util > 0.60)    return "#f59e0b";   // amber
  if (util > 0.0)     return "#22c55e";   // green
  return "#334155";                        // idle (dark)
}

function nodeColor(type: string): string {
  switch (type) {
    case "substation": return "#7c3aed";
    case "prosumer":   return "#22c55e";
    case "consumer":   return "#3b82f6";
    case "mixed":      return "#0891b2";
    default:           return "#64748b";
  }
}

interface Props {
  feeder: FeederState | null;
  highlightPath?: number[];
}

export default function FeederMap({ feeder, highlightPath }: Props) {
  if (!feeder) return (
    <div style={{ color: "#94a3b8", textAlign: "center", padding: 40 }}>
      No feeder data. Run an allocation first.
    </div>
  );

  const W = 500, H = 380;

  return (
    <div>
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ background: "#0f172a", borderRadius: 12 }}>
        {/* Lines */}
        {feeder.lines.map((ln) => {
          const [x1, y1] = NODE_POS[ln.from_node] ?? [0, 0];
          const [x2, y2] = NODE_POS[ln.to_node]   ?? [0, 0];
          const col = utilColor(ln.utilisation, ln.is_congested);
          const onPath = highlightPath &&
            highlightPath.includes(ln.from_node) &&
            highlightPath.includes(ln.to_node);
          const strokeW = onPath ? 5 : ln.flow_kw > 0 ? 3 : 2;
          const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
          return (
            <g key={ln.line_id}>
              <line x1={x1} y1={y1} x2={x2} y2={y2}
                stroke={col} strokeWidth={strokeW} strokeLinecap="round"
                strokeDasharray={ln.is_congested ? "6 3" : undefined} />
              {/* Utilisation label */}
              <rect x={mx - 18} y={my - 9} width={36} height={16} rx={4} fill="#1e293b" opacity={0.85} />
              <text x={mx} y={my + 3} textAnchor="middle" fontSize={9} fill={col} fontWeight={600}>
                {(ln.utilisation * 100).toFixed(0)}%
              </text>
            </g>
          );
        })}

        {/* Nodes */}
        {feeder.nodes.map((nd) => {
          const [cx, cy] = NODE_POS[nd.node_id] ?? [0, 0];
          const col = nodeColor(nd.type);
          return (
            <g key={nd.node_id}>
              <circle cx={cx} cy={cy} r={18} fill={col} opacity={0.9} />
              <text x={cx} y={cy + 4} textAnchor="middle" fontSize={11} fill="#fff" fontWeight={700}>
                {nd.node_id}
              </text>
              <text x={cx} y={cy + 30} textAnchor="middle" fontSize={9} fill="#94a3b8">
                {nd.name}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Legend */}
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginTop: 10, fontSize: 12, color: "#94a3b8" }}>
        {[["#7c3aed","Substation"],["#22c55e","Prosumer/Green"],["#3b82f6","Consumer"],["#0891b2","Mixed"]].map(([c,l]) => (
          <span key={l}><span style={{ display:"inline-block", width:10, height:10, background:c, borderRadius:"50%", marginRight:4 }} />{l}</span>
        ))}
        <span style={{ marginLeft:"auto" }}>
          Line: <span style={{ color:"#22c55e" }}>■</span> active &nbsp;
          <span style={{ color:"#f59e0b" }}>■</span> {">"} 60% &nbsp;
          <span style={{ color:"#ef4444" }}>■</span> congested
        </span>
      </div>

      {/* Stats row */}
      <div style={{ display: "flex", gap: 24, marginTop: 12, fontSize: 13 }}>
        <span>Total losses: <b style={{ color:"#ef4444" }}>{feeder.total_loss_kw} kW</b></span>
        <span>Peak utilisation: <b style={{ color: feeder.peak_utilisation > 0.8 ? "#ef4444" : "#22c55e" }}>
          {(feeder.peak_utilisation * 100).toFixed(1)}%
        </b></span>
        <span>Congested lines: <b style={{ color: feeder.congested_lines.length ? "#ef4444" : "#22c55e" }}>
          {feeder.congested_lines.length ? feeder.congested_lines.join(", ") : "None"}
        </b></span>
      </div>
    </div>
  );
}