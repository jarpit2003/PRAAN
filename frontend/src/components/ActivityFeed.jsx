const TYPE_META = {
  alert:        { bg: "#3d0000", color: "#f85149", icon: "🚨", label: "ALERT" },
  warn:         { bg: "#3d2c00", color: "#e3b341", icon: "⚠️", label: "WARN"  },
  info:         { bg: "#1a3a2a", color: "#3fb950", icon: "✅", label: "INFO"  },
  match:        { bg: "#1a3a5c", color: "#58a6ff", icon: "🔗", label: "MATCH" },
  escalation:   { bg: "#3d0000", color: "#f85149", icon: "⬆",  label: "ESC"  },
  confirmation: { bg: "#1a3a2a", color: "#3fb950", icon: "✅", label: "CONF" },
  reminder:     { bg: "#3d2c00", color: "#e3b341", icon: "🔔", label: "REM"  },
};

function getMeta(type) {
  const t = (type || "").toLowerCase();
  if (TYPE_META[t])           return TYPE_META[t];
  if (t.includes("escalat"))  return TYPE_META.escalation;
  if (t.includes("confirm"))  return TYPE_META.confirmation;
  if (t.includes("match"))    return TYPE_META.match;
  if (t.includes("remind"))   return TYPE_META.reminder;
  if (t.includes("alert"))    return TYPE_META.alert;
  if (t.includes("warn"))     return TYPE_META.warn;
  return TYPE_META.info;
}

function formatTime(ts) {
  try {
    return new Date(ts).toLocaleTimeString("en-IN", {
      hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
    });
  } catch { return ts; }
}

export default function ActivityFeed({ items = [] }) {
  const sorted = [...items].sort((a, b) => new Date(b.ts) - new Date(a.ts));

  return (
    <div style={styles.wrapper}>
      <div style={styles.header}>
        <span style={styles.heading}>📋 Activity Feed</span>
        <span style={styles.liveRow}>
          <span style={styles.pulse} />
          <span style={styles.liveLabel}>LIVE</span>
        </span>
      </div>

      <div style={styles.scroll}>
        {sorted.length === 0 ? (
          <p style={styles.empty}>No activity yet</p>
        ) : (
          sorted.map((item, i) => {
            const meta = getMeta(item.type);
            const isAlert = item.type === "alert" || (item.type || "").includes("escalat");
            return (
              <div key={i} style={{ ...styles.row, ...(isAlert ? styles.rowAlert : {}) }}>
                <span style={styles.ts}>{formatTime(item.ts)}</span>
                <span style={{ ...styles.badge, background: meta.bg, color: meta.color }}>
                  {meta.icon} {meta.label}
                </span>
                <span style={{ ...styles.msg, ...(isAlert ? styles.msgAlert : {}) }}>
                  {item.msg}
                </span>
              </div>
            );
          })
        )}
      </div>

      <style>{`
        @keyframes livePulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50%       { opacity: 0.4; transform: scale(0.7); }
        }
      `}</style>
    </div>
  );
}

const styles = {
  wrapper: {
    background: "#161b22",
    border: "1px solid #30363d",
    borderRadius: "10px",
    padding: "20px 24px",
    display: "flex",
    flexDirection: "column",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: "14px",
  },
  heading: {
    color: "#f0f6fc",
    fontSize: "15px",
    fontWeight: 700,
  },
  liveRow: {
    display: "flex",
    alignItems: "center",
    gap: "5px",
  },
  pulse: {
    width: "7px",
    height: "7px",
    borderRadius: "50%",
    background: "#3fb950",
    display: "inline-block",
    animation: "livePulse 1.4s infinite",
  },
  liveLabel: {
    fontSize: "10px",
    color: "#3fb950",
    fontWeight: 700,
    letterSpacing: "0.8px",
  },
  scroll: {
    maxHeight: "420px",
    overflowY: "auto",
    display: "flex",
    flexDirection: "column",
    gap: "5px",
  },
  row: {
    display: "flex",
    alignItems: "flex-start",
    gap: "10px",
    padding: "8px 10px",
    borderRadius: "6px",
    background: "#0d1117",
    borderLeft: "2px solid transparent",
  },
  rowAlert: {
    borderLeft: "2px solid #f85149",
    background: "#1a0a0a",
  },
  ts: {
    fontSize: "11px",
    color: "#8b949e",
    whiteSpace: "nowrap",
    minWidth: "75px",
    paddingTop: "2px",
  },
  badge: {
    fontSize: "10px",
    fontWeight: 700,
    padding: "2px 7px",
    borderRadius: "4px",
    whiteSpace: "nowrap",
    flexShrink: 0,
  },
  msg: {
    fontSize: "12px",
    color: "#c9d1d9",
    lineHeight: 1.5,
  },
  msgAlert: {
    color: "#f85149",
    fontWeight: 600,
  },
  empty: {
    color: "#8b949e",
    fontSize: "13px",
    margin: 0,
    padding: "20px 0",
    textAlign: "center",
  },
};
