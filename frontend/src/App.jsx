import { useCallback } from "react";
import StatsRow       from "./components/StatsRow";
import CriticalCases  from "./components/CriticalCases";
import ActivityFeed   from "./components/ActivityFeed";
import QCommandCenter from "./components/QCommandCenter";
import usePolling     from "./hooks/usePolling";
import { getStats, getCritical, getActivity, escalateRequest, contactBloodBank } from "./api";

export default function App() {
  const { data: stats }    = usePolling(useCallback(getStats,    []), 30000);
  const { data: cases }    = usePolling(useCallback(getCritical, []), 30000);
  const { data: activity } = usePolling(useCallback(getActivity, []), 10000);

  const criticalCount = cases?.length ?? 0;

  return (
    <div style={s.shell}>
      {/* Top Navbar */}
      <header style={s.navbar}>
        <div style={s.navLeft}>
          <span style={s.navLogo}>🩸</span>
          <span style={s.navTitle}>PRAAN</span>
          <span style={s.navSub}>Thalassemia Donor Coordination</span>
        </div>
        <div style={s.navRight}>
          {criticalCount > 0 && (
            <span style={s.alertChip}>🚨 {criticalCount} Critical</span>
          )}
          <span style={s.liveChip}>
            <span style={s.liveDot} />
            LIVE
          </span>
        </div>
      </header>

      {/* Body */}
      <div style={s.body}>
        {/* Left — Q Command Center */}
        <aside style={s.left}>
          <QCommandCenter />
        </aside>

        {/* Right — Dashboard */}
        <div style={s.right}>
          <StatsRow stats={stats} />
          <div style={s.row}>
            <div style={s.col}>
              <CriticalCases
                cases={cases ?? []}
                onEscalate={escalateRequest}
                onContactBloodBank={contactBloodBank}
              />
            </div>
            <div style={s.col}>
              <ActivityFeed items={activity ?? []} />
            </div>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes liveDot {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.3; }
        }
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: #0d1117; }
        ::-webkit-scrollbar-thumb { background: #30363d; border-radius: 4px; }
      `}</style>
    </div>
  );
}

const s = {
  shell: {
    display:        "flex",
    flexDirection:  "column",
    height:         "100vh",
    overflow:       "hidden",
    background:     "#0d1117",
    color:          "#c9d1d9",
    fontFamily:     "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  },
  navbar: {
    display:        "flex",
    alignItems:     "center",
    justifyContent: "space-between",
    padding:        "0 20px",
    height:         "52px",
    flexShrink:     0,
    background:     "#161b22",
    borderBottom:   "1px solid #30363d",
  },
  navLeft: {
    display:    "flex",
    alignItems: "center",
    gap:        "10px",
  },
  navLogo:  { fontSize: "22px" },
  navTitle: { color: "#f0f6fc", fontWeight: 800, fontSize: "18px", letterSpacing: "1px" },
  navSub:   { color: "#8b949e", fontSize: "12px", marginLeft: "4px" },
  navRight: {
    display:    "flex",
    alignItems: "center",
    gap:        "10px",
  },
  alertChip: {
    background: "#3d0000",
    color:      "#f85149",
    fontSize:   "12px",
    fontWeight: 700,
    padding:    "3px 12px",
    borderRadius: "20px",
  },
  liveChip: {
    display:    "flex",
    alignItems: "center",
    gap:        "5px",
    background: "#1a3a2a",
    color:      "#3fb950",
    fontSize:   "11px",
    fontWeight: 700,
    padding:    "3px 12px",
    borderRadius: "20px",
    letterSpacing: "0.5px",
  },
  liveDot: {
    width:        "7px",
    height:       "7px",
    borderRadius: "50%",
    background:   "#3fb950",
    display:      "inline-block",
    animation:    "liveDot 1.4s infinite",
  },
  body: {
    display:  "flex",
    flex:     1,
    overflow: "hidden",
  },
  left: {
    width:     "28%",
    flexShrink: 0,
    overflowY: "auto",
    padding:   "16px",
    borderRight: "1px solid #30363d",
  },
  right: {
    flex:          1,
    display:       "flex",
    flexDirection: "column",
    gap:           "14px",
    padding:       "16px",
    overflowY:     "auto",
    minWidth:      0,
  },
  row: {
    display:             "grid",
    gridTemplateColumns: "1fr 1fr",
    gap:                 "14px",
    flex:                1,
    minHeight:           0,
  },
  col: {
    minWidth:  0,
    overflowY: "auto",
  },
};
