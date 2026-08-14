import { AnimatePresence, motion } from "framer-motion";
import { Sparkles, X, Send, Eraser } from "lucide-react";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { api, ApiError } from "../../lib/api";
import { useData } from "../../context/DataContext";
import { Button } from "../ui/button";
import { Input } from "../ui/input";

type ChatMsg = { role: "user" | "assistant"; text: string };

export function AiAssistant() {
  const { rows, hasData, settings } = useData();
  const [open, setOpen] = useState(false);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [chat, setChat] = useState<ChatMsg[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open && configured === null) {
      api.get<{ configured: boolean }>("/ai/status").then((r) => setConfigured(r.configured)).catch(() => setConfigured(false));
    }
  }, [open, configured]);

  const context = () => ({
    rows,
    pollutants: settings.pollutants,
    basis: settings.basis,
    methodology: settings.methodology,
    ambient_c: settings.ambientC,
  });

  const askInsights = async () => {
    setBusy(true);
    try {
      const res = await api.post<{ text: string }>("/ai/insights", context());
      setChat((c) => [...c, { role: "assistant", text: res.text }]);
    } catch (e) {
      setChat((c) => [...c, { role: "assistant", text: e instanceof ApiError ? e.message : "Request failed." }]);
    } finally {
      setBusy(false);
    }
  };

  const send = async () => {
    const q = question.trim();
    if (!q) return;
    setQuestion("");
    setChat((c) => [...c, { role: "user", text: q }]);
    setBusy(true);
    try {
      const history = chat.slice(-6).map((m) => `${m.role}: ${m.text}`).join("\n");
      const res = await api.post<{ text: string }>("/ai/ask", { context: context(), question: q, history });
      setChat((c) => [...c, { role: "assistant", text: res.text }]);
    } catch (e) {
      setChat((c) => [...c, { role: "assistant", text: e instanceof ApiError ? e.message : "Request failed." }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <motion.button
        whileHover={{ scale: 1.08 }}
        whileTap={{ scale: 0.95 }}
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? "Close assistant" : "Open Fleet Assistant"}
        className="fixed bottom-6 right-6 z-[1000] flex h-14 w-14 items-center justify-center rounded-full bg-accent text-white shadow-lg"
      >
        {open ? <X className="h-5 w-5" /> : <Sparkles className="h-5 w-5" />}
      </motion.button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.98 }}
            transition={{ duration: 0.18 }}
            className="fixed bottom-24 right-6 z-[999] flex max-h-[64vh] w-[400px] max-w-[calc(100vw-2.5rem)] flex-col overflow-hidden rounded-2xl border border-border2 bg-card shadow-2xl"
          >
            <div className="flex items-center gap-2 border-b border-border px-4 py-3">
              <Sparkles className="h-4 w-4 text-accent" />
              <span className="font-display text-sm font-semibold text-text-prim">Fleet Assistant</span>
              <span className="ml-auto font-mono text-[9px] tracking-wide text-text-tert">GEMINI · AGGREGATES ONLY</span>
            </div>

            <div className="flex-1 space-y-2 overflow-y-auto px-4 py-3">
              {configured === false && (
                <AiMsg role="assistant">
                  Not configured — set **GEMINI_API_KEY** on the backend to enable me. Everything else works without it.
                </AiMsg>
              )}
              {configured && !hasData && (
                <AiMsg role="assistant">No data loaded yet — upload a manifest or load from the database, then ask me anything about the fleet.</AiMsg>
              )}
              {chat.map((m, i) => <AiMsg key={i} role={m.role}>{m.text}</AiMsg>)}
              {busy && <div className="font-mono text-[11px] text-text-tert">Thinking…</div>}
            </div>

            {configured && hasData && (
              <div className="space-y-2 border-t border-border p-3">
                <div className="flex gap-2">
                  <Button size="sm" variant="secondary" className="flex-1" disabled={busy} onClick={askInsights}>
                    <Sparkles className="h-3.5 w-3.5" /> Insights
                  </Button>
                  <Button size="sm" variant="ghost" disabled={busy} onClick={() => setChat([])}>
                    <Eraser className="h-3.5 w-3.5" />
                  </Button>
                </div>
                <div className="flex gap-2">
                  <Input
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && send()}
                    placeholder="e.g. which operator should we inspect first?"
                    disabled={busy}
                  />
                  <Button size="icon" disabled={busy} onClick={send} aria-label="Send">
                    <Send className="h-3.5 w-3.5" />
                  </Button>
                </div>
                <div className="font-mono text-[9.5px] leading-relaxed text-text-tert">
                  Answers use pre-computed aggregate statistics only — raw trip rows never leave the server.
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

function AiMsg({ role, children }: { role: "user" | "assistant"; children: string }) {
  if (role === "user") {
    return (
      <div
        className="ml-9 rounded-xl px-3 py-2 text-[12.5px] text-text-prim"
        style={{ background: "var(--banner-code-bg)" }}
      >
        <ReactMarkdown>{children}</ReactMarkdown>
      </div>
    );
  }
  return (
    <div className="mr-3 rounded-xl border border-border bg-card2 px-3 py-2 text-[12.5px] text-text-sec">
      <ReactMarkdown>{children}</ReactMarkdown>
    </div>
  );
}
