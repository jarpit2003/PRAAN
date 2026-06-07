import { useState } from "react";

const SECTIONS = [
  {
    title: "Patient & Donor Data",
    prompts: [
      "List all active patients and their blood types",
      "Show me donors available in Delhi right now",
      "Which patients are due for transfusion this week?",
    ],
  },
  {
    title: "Matching Pipeline",
    prompts: [
      "Explain how the TOPSIS donor matching score is calculated",
      "Why was this donor ranked #1 for the latest request?",
      "Show the proximity score breakdown for the last match",
    ],
  },
  {
    title: "Predictions",
    prompts: [
      "Which patients are predicted to need blood in the next 3 days?",
      "What is the confidence score for the next transfusion prediction?",
      "Explain the hemoglobin drop rate used in prediction",
    ],
  },
  {
    title: "Escalations & Alerts",
    prompts: [
      "List all requests that have been escalated in the last hour",
      "Why was this request escalated?",
      "How does the 30-60-90 minute escalation ladder work?",
    ],
  },
  {
    title: "System Status",
    prompts: [
      "Is the Neo4j graph database connected?",
      "Show a summary of today's activity feed",
      "How many donors were notified vs confirmed today?",
    ],
  },
];

const MAX_HISTORY = 5;

export default function QCommandCenter() {
  const [input, setInput]     = useState("");
  const [history, setHistory] = useState([]);
  const [response, setResponse] = useState("");
  const [loading, setLoading]   = useState(false);

  function handleSend() {
    const text = input.trim();
    if (!text) return;
    setHistory((prev) => [text, ...prev].slice(0, MAX_HISTORY));
    setLoading(true);
    setResponse("");
    // Simulate response — replace with real Amazon Q call if available
    setTimeout(() => {
      setResponse(`[Amazon Q] Received: "${text}"\n\nThis panel is connected to Amazon Q Developer. Integrate the Q API here to get real-time answers about PRAAN data.`);
      setLoading(false);
    }, 1200);
    setInput("");
  }

  return (
    <div style={s.wrapper}>
      {/* Header */}
      <div style={s.header}>
        <span style={s.headerIcon}>⚡</span>
        <span style={s.headerTitle}>Amazon Q Command Center</span>
        <span style={s.headerSub}>Ask anything about PRAAN</span>
      </div>

      {/* Preset sections */}
      <div style={s.sections}>
        {SECTIONS.map((sec) => (
          <div key={sec.title} style={s.section}>
            <div style={s.sectionTitle}>{sec.title}</div>
            <div style={s.btnRow}>
              {sec.prompts.map((p) => (
                <button key={p} style={s.presetBtn} onClick={() => setInput(p)}>
                  {p}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* History chips */}
      {history.length > 0 && (
        <div style={s.historyRow}>
          {history.map((h, i) => (
            <button key={i} style={s.chip} onClick={() => setInput(h)}>
              {h.length > 40 ? h.slice(0, 40) + "…" : h}
            </button>
          ))}
        </div>
      )}

      {/* Textarea */}
      <textarea
        style={s.textarea}
        rows={3}
        placeholder="Ask Amazon Q anything about PRAAN..."
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
      />

      {/* Send button */}
      <button style={s.sendBtn} onClick={handleSend}>
        Send to Q →
      </button>

      {/* Response box */}
      {(response || loading) && (
        <div style={s.responseBox}>
          <pre style={s.responseText}>
            {response}
            {loading && <span style={s.cursor}>▋</span>}
          </pre>
        </div>
      )}

      <style>{`
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
      `}</style>
    </div>
  );
}

const s = {
  wrapper: {
    background: "#0f1117",
    border: "1px solid #00ff8844",
    borderRadius: "12px",
    padding: "24px",
    display: "flex",
    flexDirection: "column",
    gap: "16px",
    fontFamily: "monospace",
    color: "#fff",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    borderBottom: "1px solid #00ff8833",
    paddingBottom: "14px",
  },
  headerIcon: { fontSize: "18px" },
  headerTitle: { color: "#00ff88", fontWeight: 700, fontSize: "15px" },
  headerSub: { color: "#8b949e", fontSize: "12px", marginLeft: "auto" },
  sections: { display: "flex", flexDirection: "column", gap: "12px" },
  section: { display: "flex", flexDirection: "column", gap: "6px" },
  sectionTitle: {
    fontSize: "10px",
    color: "#00ff88",
    textTransform: "uppercase",
    letterSpacing: "1px",
    fontWeight: 700,
  },
  btnRow: { display: "flex", flexWrap: "wrap", gap: "6px" },
  presetBtn: {
    background: "#161b22",
    border: "1px solid #30363d",
    color: "#c9d1d9",
    fontSize: "11px",
    padding: "5px 10px",
    borderRadius: "6px",
    cursor: "pointer",
    textAlign: "left",
    transition: "border-color 0.15s",
  },
  historyRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: "6px",
    borderTop: "1px solid #21262d",
    paddingTop: "12px",
  },
  chip: {
    background: "#21262d",
    border: "1px solid #00ff8844",
    color: "#00ff88",
    fontSize: "11px",
    padding: "3px 10px",
    borderRadius: "20px",
    cursor: "pointer",
  },
  textarea: {
    background: "#161b22",
    border: "1px solid #30363d",
    borderRadius: "8px",
    color: "#fff",
    fontFamily: "monospace",
    fontSize: "13px",
    padding: "12px",
    resize: "vertical",
    outline: "none",
    width: "100%",
    boxSizing: "border-box",
  },
  sendBtn: {
    background: "#00ff88",
    color: "#0f1117",
    border: "none",
    borderRadius: "8px",
    padding: "10px 24px",
    fontWeight: 700,
    fontSize: "13px",
    cursor: "pointer",
    alignSelf: "flex-end",
    fontFamily: "monospace",
  },
  responseBox: {
    background: "#0d1117",
    border: "1px solid #30363d",
    borderRadius: "8px",
    padding: "14px",
    maxHeight: "200px",
    overflowY: "auto",
  },
  responseText: {
    color: "#c9d1d9",
    fontSize: "12px",
    margin: 0,
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
  },
  cursor: {
    color: "#00ff88",
    animation: "blink 1s infinite",
  },
};
