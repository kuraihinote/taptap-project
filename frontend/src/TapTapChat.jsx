/**
 * TapTapChat.jsx — TapTap Analytics Faculty Chatbot
 * Drop-in single React component. No external dependencies beyond React.
 *
 * Props:
 *   apiUrl  — FastAPI endpoint, default "http://localhost:8000/chat"
 *   faculty — Faculty display name, default "Faculty"
 */

import { useState, useRef, useEffect, useCallback } from "react";

const DOMAIN_META = {
  emp:       { label: "Employability", color: "#3b82f6", bg: "rgba(59,130,246,0.1)" },
  pod:       { label: "POD",           color: "#f97316", bg: "rgba(249,115,22,0.1)" },
  assess:    { label: "Assessment",    color: "#10b981", bg: "rgba(16,185,129,0.1)" },
  hackathon: { label: "Hackathon",     color: "#a855f7", bg: "rgba(168,85,247,0.1)" },
  direct:    { label: "General",       color: "#f0a500", bg: "rgba(240,165,0,0.1)"  },
  advice:    { label: "Advice",        color: "#ec4899", bg: "rgba(236,72,153,0.1)" },
};

const SUGGESTIONS = [
  { icon: "🏆", domain: "emp",       title: "Top performers this month",      prompt: "Who are the top 10 students by employability score this month?" },
  { icon: "🔥", domain: "pod",       title: "POD streak leaders",             prompt: "Which students have the longest POD streaks right now?" },
  { icon: "📋", domain: "assess",    title: "Latest assessment pass rates",   prompt: "Show me pass rates for the latest formal assessments." },
  { icon: "💡", domain: "hackathon", title: "Hackathon subject breakdown",    prompt: "Break down hackathon scores by subject — aptitude, verbal, and coding." },
  { icon: "📊", domain: "emp",       title: "DSA practice pass rates",        prompt: "What is the pass rate for DSA practice questions across all students?" },
  { icon: "🎖️", domain: "pod",      title: "Badge and coin leaders",         prompt: "Who has earned the most badges and coins on Problem of the Day?" },
];

const QUICK_QUESTIONS = [
  { icon: "🏆", prompt: "Who are the top 10 students by employability score?" },
  { icon: "🔥", prompt: "Which students have the longest POD streaks right now?" },
  { icon: "📋", prompt: "Show me pass rates for the latest formal assessments" },
  { icon: "💡", prompt: "Who topped the monthly hackathon assessment in April 2026?" },
  { icon: "📅", prompt: "Who solved today's POD?" },
];

// ── Markdown-lite renderer ───────────────────────────────────────────────────
function inlineFormat(text) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**"))
      return <strong key={i} style={{ fontWeight: 600, color: "#e2e6f0" }}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`"))
      return <code key={i} style={{ background: "rgba(255,255,255,0.08)", padding: "1px 5px", borderRadius: 4, fontFamily: "monospace", fontSize: 12 }}>{part.slice(1, -1)}</code>;
    return part;
  });
}

function renderMarkdown(text) {
  const lines = text.split("\n");
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];

    // Table
    if (line.includes("|") && lines[i + 1]?.match(/^\|[-| ]+\|$/)) {
      const headers = line.split("|").filter(Boolean).map(h => h.trim());
      i += 2;
      const rows = [];
      while (i < lines.length && lines[i].includes("|")) {
        rows.push(lines[i].split("|").filter(Boolean).map(c => c.trim()));
        i++;
      }
      out.push(
        <div key={`t${i}`} style={{ overflowX: "auto", margin: "8px 0" }}>
          <table style={{ borderCollapse: "collapse", fontSize: 12.5, width: "100%" }}>
            <thead>
              <tr>{headers.map((h, j) => <th key={j} style={{ padding: "5px 10px", borderBottom: "1px solid rgba(255,255,255,0.1)", color: "#7a849a", textAlign: "left", fontWeight: 500, whiteSpace: "nowrap" }}>{h}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri}>{row.map((cell, ci) => <td key={ci} style={{ padding: "4px 10px", borderBottom: "1px solid rgba(255,255,255,0.06)", color: "#c8cfd8" }}>{cell}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }

    // Headings
    if (line.startsWith("### ")) { out.push(<p key={i} style={{ fontWeight: 600, fontSize: 14, margin: "10px 0 3px", color: "#e2e6f0" }}>{inlineFormat(line.slice(4))}</p>); i++; continue; }
    if (line.startsWith("## "))  { out.push(<p key={i} style={{ fontWeight: 600, fontSize: 15, margin: "10px 0 3px", color: "#e2e6f0" }}>{inlineFormat(line.slice(3))}</p>); i++; continue; }

    // Bullet list
    if (line.match(/^[-*•] /)) {
      const items = [];
      while (i < lines.length && lines[i].match(/^[-*•] /)) {
        items.push(<li key={i} style={{ marginBottom: 3 }}>{inlineFormat(lines[i].slice(2))}</li>);
        i++;
      }
      out.push(<ul key={`ul${i}`} style={{ paddingLeft: 16, margin: "6px 0", lineHeight: 1.7 }}>{items}</ul>);
      continue;
    }

    // Numbered list
    if (line.match(/^\d+\. /)) {
      const items = [];
      while (i < lines.length && lines[i].match(/^\d+\. /)) {
        items.push(<li key={i} style={{ marginBottom: 3 }}>{inlineFormat(lines[i].replace(/^\d+\. /, ""))}</li>);
        i++;
      }
      out.push(<ol key={`ol${i}`} style={{ paddingLeft: 18, margin: "6px 0", lineHeight: 1.7 }}>{items}</ol>);
      continue;
    }

    if (line.trim() === "") { out.push(<br key={i} />); i++; continue; }
    out.push(<p key={i} style={{ margin: "2px 0", lineHeight: 1.7 }}>{inlineFormat(line)}</p>);
    i++;
  }
  return out;
}

// ── Sub-components ───────────────────────────────────────────────────────────
function TypingIndicator() {
  return (
    <div className="tt-msg tt-bot">
      <div className="tt-av tt-av-bot">T</div>
      <div className="tt-bub tt-bub-bot tt-typing">
        <span /><span /><span />
      </div>
    </div>
  );
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  };
  return (
    <button onClick={copy} className="tt-copy-btn">
      {copied ? "✓ Copied" : "⎘ Copy"}
    </button>
  );
}

function Message({ msg, threadId }) {
  const isBot = msg.role === "assistant";
  const meta = msg.domain ? DOMAIN_META[msg.domain] : null;
  return (
    <div className={`tt-msg ${isBot ? "tt-bot" : "tt-user"}`}>
      <div className={`tt-av ${isBot ? "tt-av-bot" : "tt-av-user"}`}>{isBot ? "T" : "F"}</div>
      <div className="tt-bwrap">
        <div className="tt-meta">
          {isBot && meta && (
            <span className="tt-domain-badge" style={{ color: meta.color, background: meta.bg }}>
              {meta.label}
            </span>
          )}
          <span className="tt-ts">{msg.ts || ""}</span>
        </div>
        <div className={`tt-bub ${isBot ? "tt-bub-bot" : "tt-bub-user"}`}>
          {isBot ? renderMarkdown(msg.content) : msg.content}
          {msg.sql && (
            <details className="tt-sql-wrap">
              <summary>View SQL query</summary>
              <pre className="tt-sql">{msg.sql}</pre>
            </details>
          )}
          {msg.rawData && msg.rawData.length > 0 && (
            <details className="tt-sql-wrap">
              <summary>View raw data ({msg.rawData.length} rows) — <a href="#" onClick={e => { e.preventDefault(); window.open(`/export?thread_id=${threadId}`, '_blank'); }} className="tt-export-link">Download full CSV</a></summary>
              <div style={{ overflowX: "auto", marginTop: 8 }}>
                <table style={{ borderCollapse: "collapse", fontSize: 11.5, width: "100%", minWidth: 400 }}>
                  <thead>
                    <tr>
                      {Object.keys(msg.rawData[0]).map((col, ci) => (
                        <th key={ci} style={{ padding: "5px 10px", borderBottom: "1px solid rgba(255,255,255,0.1)", color: "#7a849a", textAlign: "left", fontWeight: 500, whiteSpace: "nowrap" }}>{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {msg.rawData.map((row, ri) => (
                      <tr key={ri}>
                        {Object.values(row).map((val, ci) => (
                          <td key={ci} style={{ padding: "4px 10px", borderBottom: "1px solid rgba(255,255,255,0.06)", color: "#c8cfd8", whiteSpace: "nowrap" }}>
                            {val === null || val === undefined ? "—" : String(val)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}
        </div>
        {isBot && !msg.isError && (
          <div className="tt-copy-row"><CopyButton text={msg.content} /></div>
        )}
      </div>
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────────────────────
export default function TapTapChat({
  apiUrl = "http://localhost:8000/chat",
  faculty = "Faculty",
}) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [started, setStarted] = useState(false);
  const [selectedCollege, setSelectedCollege] = useState("");
  const [colleges, setColleges] = useState([]);
  const [threadId, setThreadId] = useState(() => crypto.randomUUID());
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    fetch("/colleges")
      .then(r => r.json())
      .then(d => setColleges(d.colleges || []))
      .catch(() => {});
  }, []);

  const greeting = (() => {
    const h = new Date().getHours();
    if (h < 12) return "Good morning";
    if (h < 17) return "Good afternoon";
    return "Good evening";
  })();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const sendMessage = useCallback(async (overrideText) => {
    const query = (overrideText || input).trim();
    if (!query || loading) return;

    setStarted(true);
    setInput("");

    const now = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    setMessages(prev => [...prev, { role: "user", content: query, ts: now }]);
    setLoading(true);

    try {
      const res = await fetch(apiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: query, college_name: selectedCollege || null, thread_id: threadId }),
      });
      if (!res.ok) throw new Error(`Server responded with ${res.status}`);
      const data = await res.json();
      const botNow = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      setMessages(prev => [...prev, {
        role: "assistant",
        content: data.answer || data.response || "No response received.",
        domain: data.intent || data.domain || null,
        sql: data.sql || null,
        rawData: data.data || null,
        ts: botNow,
      }]);
    } catch (err) {
      const botNow = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      setMessages(prev => [...prev, {
        role: "assistant",
        content: `Something went wrong: ${err.message}. Please check the server and try again.`,
        isError: true,
        ts: botNow,
      }]);
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [input, loading, apiUrl, threadId]);

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const handleTextareaChange = (e) => {
    setInput(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
  };

  const handleNewChat = () => {
    setMessages([]); setStarted(false); setInput("");
    setThreadId(crypto.randomUUID());
    setTimeout(() => inputRef.current?.focus(), 50);
  };

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
        .tt-root{--bg:#0c0e14;--surface:#13161f;--surface2:#1a1e2b;--border:rgba(255,255,255,0.07);--border2:rgba(255,255,255,0.12);--accent:#f0a500;--accent-dim:rgba(240,165,0,0.1);--text:#e2e6f0;--muted:#7a849a;--faint:#3a4155;font-family:'Sora',sans-serif;background:var(--bg);color:var(--text);display:flex;flex-direction:column;height:100%;min-height:520px;width:100%;border-radius:16px;overflow:hidden;border:1px solid var(--border2);}
        .tt-header{display:flex;align-items:center;justify-content:space-between;padding:12px 18px;border-bottom:1px solid var(--border);background:var(--surface);flex-shrink:0;}
        .tt-logo{display:flex;align-items:center;gap:10px;}
        .tt-mark{width:30px;height:30px;background:var(--accent);border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:600;font-size:12px;color:#0c0e14;letter-spacing:-0.5px;}
        .tt-name{font-size:14px;font-weight:600;letter-spacing:-0.3px;}
        .tt-sub{font-size:10.5px;color:var(--muted);}
        .tt-new-btn{background:transparent;border:1px solid var(--border2);color:var(--muted);padding:5px 12px;border-radius:7px;font-family:'Sora',sans-serif;font-size:11px;cursor:pointer;transition:all 0.15s;display:flex;align-items:center;gap:4px;}
        .tt-new-btn:hover{border-color:var(--accent);color:var(--accent);background:var(--accent-dim);}
        .tt-welcome{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:28px 20px 16px;gap:6px;position:relative;overflow:hidden;animation:tt-fade 0.35s ease;}
        .tt-glow{position:absolute;top:-80px;left:50%;transform:translateX(-50%);width:400px;height:240px;background:radial-gradient(ellipse,rgba(240,165,0,0.07) 0%,transparent 70%);pointer-events:none;}
        .tt-hi{font-size:30px;margin-bottom:2px;display:inline-block;animation:tt-wave 2.5s ease-in-out infinite;}
        .tt-welcome-title{font-size:21px;font-weight:600;letter-spacing:-0.5px;text-align:center;}
        .tt-welcome-title span{color:var(--accent);}
        .tt-welcome-sub{font-size:13px;color:var(--muted);text-align:center;max-width:320px;line-height:1.65;margin-bottom:10px;}
        .tt-chips{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;width:100%;max-width:660px;}
        .tt-chip{background:var(--surface);border:1px solid var(--border2);border-radius:10px;padding:11px 12px;cursor:pointer;transition:all 0.18s;text-align:left;display:flex;flex-direction:column;gap:5px;opacity:0;transform:translateY(10px);animation:tt-chip-in 0.35s ease forwards;}
        .tt-chip:nth-child(1){animation-delay:0.05s;}
        .tt-chip:nth-child(2){animation-delay:0.10s;}
        .tt-chip:nth-child(3){animation-delay:0.15s;}
        .tt-chip:nth-child(4){animation-delay:0.20s;}
        .tt-chip:nth-child(5){animation-delay:0.25s;}
        .tt-chip:nth-child(6){animation-delay:0.30s;}
        .tt-chip:hover{transform:translateY(-2px);}
        .tt-chip-top{display:flex;align-items:center;gap:5px;}
        .tt-chip-icon{font-size:13px;}
        .tt-chip-tag{font-size:9.5px;font-weight:600;text-transform:uppercase;letter-spacing:0.7px;}
        .tt-chip-title{font-size:12px;font-weight:500;color:var(--text);line-height:1.4;}
        .tt-msgs{flex:1;overflow-y:auto;padding:18px 16px 8px;display:flex;flex-direction:column;gap:14px;}
        .tt-msgs::-webkit-scrollbar{width:3px;}
        .tt-msgs::-webkit-scrollbar-thumb{background:var(--faint);border-radius:3px;}
        .tt-msg{display:flex;align-items:flex-start;gap:9px;animation:tt-in 0.22s ease;}
        .tt-user{flex-direction:row-reverse;}
        .tt-av{width:28px;height:28px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:600;margin-top:2px;}
        .tt-av-bot{background:var(--accent);color:#0c0e14;}
        .tt-av-user{background:rgba(59,130,246,0.15);color:#3b82f6;border:1px solid rgba(59,130,246,0.25);}
        .tt-bwrap{display:flex;flex-direction:column;gap:4px;max-width:74%;}
        .tt-user .tt-bwrap{align-items:flex-end;}
        .tt-meta{display:flex;align-items:center;gap:6px;}
        .tt-domain-badge{font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:0.6px;padding:2px 7px;border-radius:4px;}
        .tt-ts{font-size:10px;color:var(--faint);}
        .tt-bub{padding:10px 13px;border-radius:10px;font-size:13.5px;line-height:1.65;word-break:break-word;}
        .tt-bub p,.tt-bub ul,.tt-bub ol{margin:0;}
        .tt-bub-bot{background:var(--surface);border:1px solid var(--border);color:var(--text);border-radius:4px 10px 10px 10px;}
        .tt-bub-user{background:rgba(59,130,246,0.12);border:1px solid rgba(59,130,246,0.18);color:#c8dcff;border-radius:10px 4px 10px 10px;}
        .tt-copy-row{display:flex;}
        .tt-copy-btn{background:transparent;border:none;cursor:pointer;font-size:10px;color:var(--faint);font-family:'Sora',sans-serif;padding:0;transition:color 0.15s;}
        .tt-copy-btn:hover{color:var(--muted);}
        .tt-export-link{color:var(--accent);font-size:10px;text-decoration:none;margin-left:4px;}
        .tt-export-link:hover{text-decoration:underline;}
        .tt-sql-wrap{margin-top:10px;border-top:1px solid var(--border);padding-top:8px;}
        .tt-sql-wrap summary{font-size:11px;color:var(--faint);cursor:pointer;user-select:none;}
        .tt-sql-wrap summary:hover{color:var(--muted);}
        .tt-sql{margin-top:8px;font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--muted);background:rgba(0,0,0,0.28);padding:10px;border-radius:6px;overflow-x:auto;white-space:pre;line-height:1.6;}
        .tt-typing{display:flex;align-items:center;gap:5px;padding:13px 16px!important;}
        .tt-typing span{width:5px;height:5px;border-radius:50%;background:var(--faint);animation:tt-bounce 1.2s ease infinite;}
        .tt-typing span:nth-child(2){animation-delay:0.2s;}
        .tt-typing span:nth-child(3){animation-delay:0.4s;}
        .tt-input-area{padding:10px 14px 14px;border-top:1px solid var(--border);background:var(--surface);flex-shrink:0;}
        .tt-input-row{display:flex;align-items:flex-end;gap:7px;background:var(--surface2);border:1px solid var(--border2);border-radius:11px;padding:7px 7px 7px 13px;transition:border-color 0.18s;}
        .tt-input-row:focus-within{border-color:var(--accent);}
        .tt-textarea{flex:1;background:transparent;border:none;outline:none;color:var(--text);font-family:'Sora',sans-serif;font-size:13.5px;resize:none;line-height:1.5;padding:0;min-height:22px;max-height:120px;}
        .tt-textarea::placeholder{color:var(--faint);}
        .tt-send{width:32px;height:32px;border-radius:7px;background:var(--accent);border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all 0.15s;flex-shrink:0;}
        .tt-send:hover:not(:disabled){background:#ffb820;transform:scale(1.05);}
        .tt-send:active:not(:disabled){transform:scale(0.95);}
        .tt-send:disabled{opacity:0.3;cursor:not-allowed;}
        .tt-send svg{width:14px;height:14px;fill:#0c0e14;}
        .tt-hint{font-size:10px;color:var(--faint);text-align:center;margin-top:6px;}
        @keyframes tt-fade{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
        @keyframes tt-chip-in{to{opacity:1;transform:translateY(0)}}
        @keyframes tt-in{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:translateY(0)}}
        @keyframes tt-bounce{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-5px)}}
        @keyframes tt-wave{0%,100%{transform:rotate(0deg)}20%{transform:rotate(-10deg)}40%{transform:rotate(12deg)}60%{transform:rotate(-8deg)}80%{transform:rotate(10deg)}}
        .tt-quick-questions{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;width:100%;max-width:660px;margin-top:16px;}
        .tt-quick-btn{background:transparent;border:1px solid var(--border2);color:var(--muted);font-family:'Sora',sans-serif;font-size:11.5px;padding:6px 12px;border-radius:20px;cursor:pointer;transition:all 0.18s;display:flex;align-items:center;gap:5px;}
        .tt-quick-btn:hover{border-color:var(--accent);color:var(--text);background:var(--accent-dim);}
        .tt-college-select{background:var(--surface2);border:1px solid var(--border2);color:var(--text);font-family:'Sora',sans-serif;font-size:11px;padding:5px 8px;border-radius:7px;cursor:pointer;max-width:200px;transition:border-color 0.15s;}
        .tt-college-select:hover{border-color:var(--accent);}
        .tt-college-select:focus{outline:none;border-color:var(--accent);}
        @media(max-width:500px){.tt-chips{grid-template-columns:repeat(2,1fr)}.tt-bwrap{max-width:86%}}
      `}</style>

      <div className="tt-root">
        <div className="tt-header">
          <div className="tt-logo">
            <div className="tt-mark">TT</div>
            <div>
              <div className="tt-name">TapTap Analytics</div>
              <div className="tt-sub">Faculty Intelligence Assistant</div>
            </div>
          </div>
          <select
            className="tt-college-select"
            value={selectedCollege}
            onChange={e => setSelectedCollege(e.target.value)}
          >
            <option value="">All Colleges</option>
            {colleges.map((c, i) => (
              <option key={i} value={c}>{c}</option>
            ))}
          </select>
          <button className="tt-new-btn" onClick={handleNewChat}>
            <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
              <path d="M5.5 1v9M1 5.5h9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            New Chat
          </button>
        </div>

        {!started ? (
          <div className="tt-welcome">
            <div className="tt-glow" />
            <div className="tt-hi">👋</div>
            <div className="tt-welcome-title">{greeting}, <span>{faculty}</span></div>
            <div className="tt-welcome-sub">
              Ask about student performance, daily challenges, assessments, or hackathons.
            </div>
            <div className="tt-chips">
              {SUGGESTIONS.map((s, i) => {
                const meta = DOMAIN_META[s.domain];
                return (
                  <button
                    key={i}
                    className="tt-chip"
                    onClick={() => sendMessage(s.prompt)}
                    disabled={loading}
                    onMouseEnter={e => { e.currentTarget.style.borderColor = meta.color; e.currentTarget.style.background = meta.bg; }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = ""; e.currentTarget.style.background = ""; }}
                  >
                    <div className="tt-chip-top">
                      <span className="tt-chip-icon">{s.icon}</span>
                      <span className="tt-chip-tag" style={{ color: meta.color }}>{meta.label}</span>
                    </div>
                    <span className="tt-chip-title">{s.title}</span>
                  </button>
                );
              })}
            </div>
            <div className="tt-quick-questions">
              {QUICK_QUESTIONS.map((q, i) => (
                <button
                  key={i}
                  className="tt-quick-btn"
                  onClick={() => sendMessage(q.prompt)}
                  disabled={loading}
                >
                  <span>{q.icon}</span> {q.prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="tt-msgs">
            {messages.map((msg, i) => <Message key={i} msg={msg} threadId={threadId} />)}
            {loading && <TypingIndicator />}
            <div ref={bottomRef} />
          </div>
        )}

        <div className="tt-input-area">
          <div className="tt-input-row">
            <textarea
              ref={inputRef}
              className="tt-textarea"
              rows={1}
              value={input}
              onChange={handleTextareaChange}
              onKeyDown={handleKey}
              placeholder="Ask about students, scores, streaks, assessments…"
              disabled={loading}
            />
            <button className="tt-send" onClick={() => sendMessage()} disabled={!input.trim() || loading} title="Send">
              <svg viewBox="0 0 14 14"><path d="M13 7L1 1l2.5 5.5L1 13 13 7z" /></svg>
            </button>
          </div>
          <div className="tt-hint">Enter to send · Shift+Enter for new line</div>
        </div>
      </div>
    </>
  );
}