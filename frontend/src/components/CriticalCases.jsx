import { useState } from "react";

const URGENCY_STYLE = {
  urgent:  { background: "#3d0000", color: "#f85149" },
  normal:  { background: "#1a3a5c", color: "#58a6ff" },
  planned: { background: "#1a2a1a", color: "#3fb950" },
};

export default function CriticalCases({ cases = [], onEscalate, onContactBloodBank }) {
  const sorted = [...cases].sort((a, b) => b.waiting_minutes - a.waiting_minutes);
  const [sending,   setSending]   = useState({});
  const [sent,      setSent]      = useState({});
  const [escalated, setEscalated] = useState({});

  async function handleContact(id) {
    setSending(s => ({ ...s, [id]: true }));
    const res = await onContactBloodBank(id);
    setSending(s => ({ ...s, [id]: false }));
    if (res?.sent) {
      setSent(s => ({ ...s, [id]: "✓ Sent" }));
    } else {
      const msg = res?.error ? `✗ ${res.error}` : "✗ Failed";
      setSent(s => ({ ...s, [id]: msg }));
      console.error("[Blood Bank Email]", res?.error);
    }
    setTimeout(() => setSent(s => { const n = { ...s }; delete n[id]; return n; }), 6000);
  }

  async function handleEscalate(id) {
    await onEscalate(id);
    setEscalated(s => ({ ...s, [id]: true }));
  }

  return (
    <div style={styles.wrapper}>
      <div style={styles.header}>
        <span style={styles.heading}>🚨 Critical Cases</span>
        {sorted.length > 0 && (
          <span style={styles.countBadge}>{sorted.length}</span>
        )}
      </div>

      {sorted.length === 0 ? (
        <div style={styles.emptyBox}>
          <span style={styles.emptyIcon}>✅</span>
          <p style={styles.empty}>No critical cases right now</p>
        </div>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              {["Patient", "Type", "City", "Urgency", "Waiting", "Actions"].map(h => (
                <th key={h} style={styles.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map(c => {
              const urgStyle = URGENCY_STYLE[c.urgency] || URGENCY_STYLE.normal;
              const isEscalated = escalated[c.id];
              return (
                <tr key={c.id} style={styles.row}>
                  <td style={styles.td}>
                    <span style={styles.patientName}>{c.patient}</span>
                  </td>
                  <td style={styles.td}>
                    <span style={styles.bloodBadge}>{c.blood_type}</span>
                  </td>
                  <td style={{ ...styles.td, color: "#8b949e", fontSize: "12px" }}>
                    {c.city || "—"}
                  </td>
                  <td style={styles.td}>
                    <span style={{ ...styles.pill, ...urgStyle }}>
                      {c.urgency}
                    </span>
                  </td>
                  <td style={styles.td}>
                    <span style={c.waiting_minutes >= 60 ? styles.timeRed : styles.timeYellow}>
                      {c.waiting_minutes}m
                    </span>
                  </td>
                  <td style={styles.td}>
                    <div style={styles.actions}>
                      <button
                        style={{ ...styles.btnEscalate, ...(isEscalated ? styles.btnDone : {}) }}
                        onClick={() => handleEscalate(c.id)}
                        disabled={isEscalated}
                        title="Escalate this request"
                      >
                        {isEscalated ? "✓ Escalated" : "⬆ Escalate"}
                      </button>
                      <button
                        style={{ ...styles.btnEmail, ...(sending[c.id] ? styles.btnDisabled : {}) }}
                        disabled={!!sending[c.id]}
                        onClick={() => handleContact(c.id)}
                        title="Send AI-generated email to blood bank"
                      >
                        {sending[c.id] ? "Sending…" : sent[c.id] ?? "📧 Blood Bank"}
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

const styles = {
  wrapper: {
    background: "#161b22",
    border: "1px solid #30363d",
    borderRadius: "10px",
    padding: "20px 24px",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    marginBottom: "16px",
  },
  heading: {
    color: "#f85149",
    fontSize: "15px",
    fontWeight: 700,
  },
  countBadge: {
    background: "#3d0000",
    color: "#f85149",
    fontSize: "11px",
    fontWeight: 700,
    padding: "1px 8px",
    borderRadius: "10px",
  },
  emptyBox: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    padding: "24px 0",
    gap: "8px",
  },
  emptyIcon: { fontSize: "28px" },
  empty: { color: "#8b949e", fontSize: "13px", margin: 0 },
  table: { width: "100%", borderCollapse: "collapse" },
  th: {
    textAlign: "left",
    fontSize: "10px",
    color: "#8b949e",
    textTransform: "uppercase",
    letterSpacing: "0.6px",
    paddingBottom: "10px",
    borderBottom: "1px solid #30363d",
    fontWeight: 600,
  },
  row: {
    borderBottom: "1px solid #21262d",
    transition: "background 0.15s",
  },
  td: {
    padding: "10px 8px 10px 0",
    fontSize: "13px",
    color: "#c9d1d9",
    verticalAlign: "middle",
  },
  patientName: {
    fontWeight: 600,
    color: "#e6edf3",
  },
  bloodBadge: {
    background: "#3d0000",
    color: "#f85149",
    fontSize: "11px",
    fontWeight: 700,
    padding: "2px 8px",
    borderRadius: "4px",
  },
  pill: {
    fontSize: "10px",
    fontWeight: 700,
    padding: "2px 8px",
    borderRadius: "10px",
    textTransform: "uppercase",
    letterSpacing: "0.4px",
  },
  timeRed:    { color: "#f85149", fontWeight: 700, fontSize: "13px" },
  timeYellow: { color: "#e3b341", fontWeight: 600, fontSize: "13px" },
  actions:    { display: "flex", gap: "6px", flexWrap: "wrap" },
  btnEscalate: {
    background: "#f85149",
    color: "#fff",
    border: "none",
    borderRadius: "6px",
    padding: "5px 12px",
    fontSize: "11px",
    fontWeight: 600,
    cursor: "pointer",
    whiteSpace: "nowrap",
  },
  btnDone: {
    background: "#1a3a2a",
    color: "#3fb950",
    cursor: "default",
    opacity: 0.8,
  },
  btnEmail: {
    background: "#1f6feb",
    color: "#fff",
    border: "none",
    borderRadius: "6px",
    padding: "5px 12px",
    fontSize: "11px",
    fontWeight: 600,
    cursor: "pointer",
    whiteSpace: "nowrap",
  },
  btnDisabled: { opacity: 0.5, cursor: "not-allowed" },
};
