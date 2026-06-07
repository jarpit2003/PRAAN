const CARDS = [
  { label: "Active Requests",   key: "active_requests",  icon: "🩸", accent: "#f85149" },
  { label: "Donors Notified",   key: "donors_notified",  icon: "📣", accent: "#e3b341" },
  { label: "Confirmed Today",   key: "confirmed_today",  icon: "✅", accent: "#3fb950" },
  { label: "Avg Match Time",    key: "avg_match_time",   icon: "⏱", accent: "#58a6ff" },
  { label: "Critical Cases",    key: "critical_cases",   icon: "🚨", accent: "#f85149" },
  { label: "Due in 7 Days",     key: "patients_due_7days", icon: "📅", accent: "#e3b341" },
];

export default function StatsRow({ stats }) {
  return (
    <>
      <style>{`
        @keyframes shimmer {
          0%   { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
      `}</style>
      <div style={styles.grid}>
        {CARDS.map(({ label, key, icon, accent }) => {
          const val = stats?.[key];
          const isHigh = typeof val === "number" && key === "active_requests" && val > 0;
          const isCritical = typeof val === "number" && key === "critical_cases" && val > 0;
          return (
            <div key={key} style={{ ...styles.card, borderColor: (isHigh || isCritical) ? accent + "55" : "#30363d" }}>
              <div style={styles.topRow}>
                <span style={styles.icon}>{icon}</span>
                <span style={styles.label}>{label}</span>
              </div>
              {stats
                ? <span style={{ ...styles.value, color: (isHigh || isCritical) ? accent : "#f0f6fc" }}>
                    {val ?? "—"}
                  </span>
                : <div style={styles.skeleton} />
              }
            </div>
          );
        })}
      </div>
    </>
  );
}

const styles = {
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(6, 1fr)",
    gap: "12px",
    width: "100%",
  },
  card: {
    background: "#161b22",
    border: "1px solid #30363d",
    borderRadius: "10px",
    padding: "16px 18px",
    display: "flex",
    flexDirection: "column",
    gap: "8px",
    transition: "border-color 0.3s",
  },
  topRow: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
  },
  icon: { fontSize: "14px" },
  label: {
    fontSize: "10px",
    color: "#8b949e",
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.5px",
  },
  value: {
    fontSize: "28px",
    fontWeight: 700,
    color: "#f0f6fc",
    lineHeight: 1,
  },
  skeleton: {
    height: "32px",
    width: "55%",
    background: "linear-gradient(90deg, #21262d 25%, #30363d 50%, #21262d 75%)",
    backgroundSize: "200% 100%",
    borderRadius: "6px",
    animation: "shimmer 1.4s infinite",
  },
};
