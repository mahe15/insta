import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Award,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clipboard,
  Clock,
  Copy,
  ExternalLink,
  Eye,
  Film,
  HelpCircle,
  Layers,
  ListFilter,
  Mic,
  Percent,
  Play,
  RefreshCw,
  Save,
  Scissors,
  Search,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Type,
  Upload,
  Video,
  Volume2,
  X,
  Zap,
} from "lucide-react";
import { api } from "./api";
import type {
  ChaptersResult,
  DeadAirResult,
  HookFormula,
  HookScoreResult,
  Job,
  PackageLintResult,
  RetentionResult,
  SwipeResult,
} from "./types";
import {
  Button,
  Empty,
  ErrorBox,
  Field,
  IconButton,
  Loading,
  SectionTitle,
  useStudio,
} from "./ui";

function Tag({
  children,
  variant = "default",
  style,
}: {
  children: React.ReactNode;
  variant?: string;
  style?: React.CSSProperties;
}) {
  return (
    <span className={`badge ${variant}`} style={style}>
      {children}
    </span>
  );
}

const SAMPLE_HOOKS = [
  "97% of creators quit before video 30. Here is what the other 3% do.",
  "Everyone says post daily. I posted once a week for a year and tripled the channel.",
  "Your first 30 seconds are why nobody finishes your videos. It is not the topic.",
  "This guy went from 400 subscribers to 200,000 in seven months on one format. I mapped it.",
  "Never start a video with 'Hey guys'. Here is what you should say instead.",
];

export default function YouTubeAgent() {
  const { notify } = useStudio();
  const [activeTab, setActiveTab] = useState<
    "hook" | "package" | "deadair" | "chapters" | "retention" | "swipe" | "voice"
  >("hook");

  // Fetch jobs for transcript reuse
  const jobsQuery = useQuery({
    queryKey: ["jobs-list"],
    queryFn: () => api<Job[]>("/jobs"),
  });

  // Fetch formulas list
  const formulasQuery = useQuery({
    queryKey: ["yt-formulas"],
    queryFn: () => api<{ count: number; formulas: HookFormula[] }>("/yt/formulas"),
  });

  // Fetch voice profile
  const voiceQuery = useQuery({
    queryKey: ["yt-voice"],
    queryFn: () => api<{ content: string }>("/yt/voice"),
  });

  // --- Hook Studio State ---
  const [hookInput, setHookInput] = useState(SAMPLE_HOOKS[0]);
  const [isMultiHook, setIsMultiHook] = useState(false);
  const [multiHookText, setMultiHookText] = useState(SAMPLE_HOOKS.join("\n"));
  const [hookLoading, setHookLoading] = useState(false);
  const [singleHookResult, setSingleHookResult] = useState<HookScoreResult | null>(null);
  const [multiHookResults, setMultiHookResults] = useState<HookScoreResult[]>([]);
  const [showFormulaDrawer, setShowFormulaDrawer] = useState(false);

  // --- Package Linter State ---
  const [titleInput, setTitleInput] = useState("How to Build an AI Agent in 2026");
  const [thumbInput, setThumbInput] = useState("AGENT RUNS");
  const [lintLoading, setLintLoading] = useState(false);
  const [lintResult, setLintResult] = useState<PackageLintResult | null>(null);

  // --- Dead Air State ---
  const [selectedJobId, setSelectedJobId] = useState<string>("");
  const [deadAirSrt, setDeadAirSrt] = useState<string>("");
  const [deadAirFloor, setDeadAirFloor] = useState<number>(0.45);
  const [deadAirLoading, setDeadAirLoading] = useState(false);
  const [deadAirResult, setDeadAirResult] = useState<DeadAirResult | null>(null);

  // --- Chapters State ---
  const [chaptersJobId, setChaptersJobId] = useState<string>("");
  const [chaptersSrt, setChaptersSrt] = useState<string>("");
  const [chaptersTarget, setChaptersTarget] = useState<number>(7);
  const [chaptersLoading, setChaptersLoading] = useState(false);
  const [chaptersResult, setChaptersResult] = useState<ChaptersResult | null>(null);
  const [copiedChapters, setCopiedChapters] = useState(false);

  // --- Retention State ---
  const [retentionCsv, setRetentionCsv] = useState<string>(
    `Position,Retention\n0,100\n5,92\n10,84\n15,79\n20,74\n25,70\n30,66\n45,63\n60,59\n90,56\n120,53\n180,48\n240,42\n300,38\n360,34\n420,30\n480,26`
  );
  const [retentionDuration, setRetentionDuration] = useState<number>(480);
  const [retentionJobId, setRetentionJobId] = useState<string>("");
  const [retentionLoading, setRetentionLoading] = useState(false);
  const [retentionResult, setRetentionResult] = useState<RetentionResult | null>(null);

  // --- Swipe State ---
  const [swipeJson, setSwipeJson] = useState<string>(
    JSON.stringify(
      [
        { channel: "TechGrowth", title: "97% of creators quit before video 30", views: 420000 },
        { channel: "TechGrowth", title: "My simple weekly workflow", views: 45000 },
        { channel: "TechGrowth", title: "Why I stopped using Premiere", views: 52000 },
        { channel: "TechGrowth", title: "Top 5 microphones in 2026", views: 48000 },
        { channel: "SaaS Blueprint", title: "From $0 to $100k MRR in 90 days with 1 prompt", views: 890000 },
        { channel: "SaaS Blueprint", title: "How to hire developers", views: 80000 },
        { channel: "SaaS Blueprint", title: "Our tech stack review", views: 95000 },
        { channel: "SaaS Blueprint", title: "Customer acquisition guide", views: 110000 }
      ],
      null,
      2
    )
  );
  const [swipeMin, setSwipeMin] = useState<number>(2.0);
  const [swipeLoading, setSwipeLoading] = useState(false);
  const [swipeResult, setSwipeResult] = useState<SwipeResult | null>(null);

  // --- Voice Profile State ---
  const [voiceContent, setVoiceContent] = useState<string>("");
  const [voiceSaving, setVoiceSaving] = useState(false);

  useEffect(() => {
    if (voiceQuery.data?.content) {
      setVoiceContent(voiceQuery.data.content);
    }
  }, [voiceQuery.data]);

  // Initial scores
  useEffect(() => {
    void handleScoreHook(SAMPLE_HOOKS[0]);
    void handleLintTitle(titleInput, thumbInput);
  }, []);

  // Handlers
  async function handleScoreHook(text: string) {
    if (!text.trim()) return;
    setHookLoading(true);
    try {
      const res = await api<HookScoreResult>("/yt/hookscore", "POST", { hook: text });
      setSingleHookResult(res);
    } catch (e: any) {
      notify(e.message || "Could not score hook", true);
    } finally {
      setHookLoading(false);
    }
  }

  async function handleScoreMultiHooks() {
    const list = multiHookText
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
    if (!list.length) return;
    setHookLoading(true);
    try {
      const res = await api<{ results: HookScoreResult[]; count: number }>("/yt/hookscore", "POST", {
        hooks: list,
      });
      setMultiHookResults(res.results);
    } catch (e: any) {
      notify(e.message || "Could not score hooks", true);
    } finally {
      setHookLoading(false);
    }
  }

  async function handleLintTitle(title: string, thumb?: string) {
    if (!title.trim()) return;
    setLintLoading(true);
    try {
      const res = await api<PackageLintResult>("/yt/package-lint", "POST", {
        title,
        thumb: thumb || null,
      });
      setLintResult(res);
    } catch (e: any) {
      notify(e.message || "Could not lint packaging", true);
    } finally {
      setLintLoading(false);
    }
  }

  async function handleRunDeadAir() {
    setDeadAirLoading(true);
    try {
      const res = await api<DeadAirResult>("/yt/deadair", "POST", {
        job_id: selectedJobId || null,
        srt: deadAirSrt || null,
        floor: deadAirFloor,
      });
      setDeadAirResult(res);
      notify(`EDL computed: ${res.cuts.length} cuts (${res.removed_seconds}s saved)`);
    } catch (e: any) {
      notify(e.message || "Failed to analyze dead air", true);
    } finally {
      setDeadAirLoading(false);
    }
  }

  async function handleRunChapters() {
    setChaptersLoading(true);
    try {
      const res = await api<ChaptersResult>("/yt/chapters", "POST", {
        job_id: chaptersJobId || null,
        srt: chaptersSrt || null,
        target: chaptersTarget,
      });
      setChaptersResult(res);
      notify(`Generated ${res.chapters.length} chapters.`);
    } catch (e: any) {
      notify(e.message || "Failed to generate chapters", true);
    } finally {
      setChaptersLoading(false);
    }
  }

  async function handleRunRetention() {
    setRetentionLoading(true);
    try {
      const res = await api<RetentionResult>("/yt/retention", "POST", {
        csv_text: retentionCsv,
        duration: retentionDuration || null,
        job_id: retentionJobId || null,
      });
      setRetentionResult(res);
      notify(`Retention diagnostic complete: ${res.hook_verdict} hook.`);
    } catch (e: any) {
      notify(e.message || "Retention analysis failed", true);
    } finally {
      setRetentionLoading(false);
    }
  }

  async function handleRunSwipe() {
    setSwipeLoading(true);
    try {
      const data = JSON.parse(swipeJson);
      const videos = Array.isArray(data) ? data : data.videos || [];
      const res = await api<SwipeResult>("/yt/swipe", "POST", {
        videos,
        min_multiple: swipeMin,
      });
      setSwipeResult(res);
      notify(`Found ${res.outliers.length} viral outliers.`);
    } catch (e: any) {
      notify(e.message || "Swipe outlier analysis failed", true);
    } finally {
      setSwipeLoading(false);
    }
  }

  async function handleSaveVoice() {
    setVoiceSaving(true);
    try {
      await api("/yt/voice", "POST", { content: voiceContent });
      notify("Voice profile saved to config/voice.md and synced with ~/.claude/youtube/voice.md");
    } catch (e: any) {
      notify(e.message || "Failed to save voice profile", true);
    } finally {
      setVoiceSaving(false);
    }
  }

  const finishedJobs = (jobsQuery.data || []).filter(
    (j) => j.state === "complete" || j.state === "awaiting_selection"
  );

  return (
    <div className="workspace-view" style={{ maxWidth: 1200, margin: "0 auto", paddingBottom: 64 }}>
      {/* Header Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: 24,
          padding: "24px 28px",
          background: "linear-gradient(135deg, rgba(239, 68, 68, 0.08) 0%, rgba(30, 41, 59, 0.5) 100%)",
          borderRadius: 16,
          border: "1px solid rgba(239, 68, 68, 0.2)",
          backdropFilter: "blur(12px)",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 36,
                height: 36,
                borderRadius: 10,
                background: "linear-gradient(135deg, #ef4444 0%, #dc2626 100%)",
                color: "#fff",
                boxShadow: "0 4px 12px rgba(239, 68, 68, 0.35)",
              }}
            >
              <Video size={20} />
            </span>
            <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0, letterSpacing: "-0.02em" }}>
              YouTube Agent Studio
            </h1>
            <Tag variant="success">11 Skills Engine Active</Tag>
          </div>
          <p style={{ margin: 0, color: "var(--text-muted, #94a3b8)", fontSize: 14, maxWidth: 740, lineHeight: 1.5 }}>
            Autonomous YouTube channel operations based on Jake Schincariol's YouTube Agent Skill Suite: 21 hook formulas,
            mobile vs. desktop packaging linter, dead air and filler EDL, validated chapters, retention diagnostic, and niche outlier ranker.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Button
            variant="ghost"
            onClick={() => setShowFormulaDrawer(!showFormulaDrawer)}
            style={{ display: "flex", alignItems: "center", gap: 6 }}
          >
            <BookOpen size={16} /> 21 Hook Formulas
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          gap: 6,
          borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
          marginBottom: 24,
          overflowX: "auto",
          paddingBottom: 4,
        }}
      >
        {[
          { key: "hook", label: "Hook Scorer", icon: Sparkles },
          { key: "package", label: "Packaging Linter", icon: Type },
          { key: "deadair", label: "Dead Air (EDL)", icon: Scissors },
          { key: "chapters", label: "Chapters", icon: Layers },
          { key: "retention", label: "Retention Diagnostic", icon: TrendingDown },
          { key: "swipe", label: "Viral Swipe Ranker", icon: TrendingUp },
          { key: "voice", label: "Creator Voice", icon: Mic },
        ].map((tab) => {
          const Icon = tab.icon;
          const active = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as any)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "10px 16px",
                borderRadius: "8px 8px 0 0",
                border: "none",
                background: active ? "rgba(239, 68, 68, 0.15)" : "transparent",
                color: active ? "#f87171" : "var(--text-muted, #94a3b8)",
                borderBottom: active ? "2px solid #ef4444" : "2px solid transparent",
                fontWeight: active ? 600 : 500,
                fontSize: 14,
                cursor: "pointer",
                transition: "all 0.15s ease",
                whiteSpace: "nowrap",
              }}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* 21 Formulas Drawer */}
      {showFormulaDrawer && (
        <div
          style={{
            marginBottom: 24,
            padding: 20,
            borderRadius: 12,
            background: "rgba(15, 23, 42, 0.8)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <h3 style={{ margin: 0, fontSize: 16, display: "flex", alignItems: "center", gap: 8 }}>
              <BookOpen size={18} color="#ef4444" />
              The 21 YouTube Hook Formulas (Classified by Words & Speech)
            </h3>
            <IconButton icon={X} label="Close" onClick={() => setShowFormulaDrawer(false)} />
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
              gap: 12,
              maxHeight: 400,
              overflowY: "auto",
              paddingRight: 8,
            }}
          >
            {(formulasQuery.data?.formulas || []).map((f) => (
              <div
                key={f.id}
                style={{
                  padding: 12,
                  borderRadius: 8,
                  background: "rgba(30, 41, 59, 0.6)",
                  border: "1px solid rgba(255, 255, 255, 0.06)",
                }}
              >
                <div style={{ fontWeight: 600, color: "#f87171", fontSize: 13, marginBottom: 4 }}>
                  {f.name}
                </div>
                <div style={{ fontSize: 12, color: "#cbd5e1", marginBottom: 6 }}>{f.shape}</div>
                <div
                  style={{
                    fontSize: 11,
                    fontStyle: "italic",
                    color: "#94a3b8",
                    background: "rgba(0,0,0,0.2)",
                    padding: "4px 8px",
                    borderRadius: 4,
                  }}
                >
                  "{f.example}"
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 1: HOOK SCORER */}
      {activeTab === "hook" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
          {/* Input Panel */}
          <div
            style={{
              padding: 24,
              borderRadius: 14,
              background: "rgba(15, 23, 42, 0.6)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <SectionTitle title="Hook Panel & Formulas" note="Scores 5 properties & applies weakest-link weighting" />
              <Button variant="ghost" onClick={() => setIsMultiHook(!isMultiHook)}>
                {isMultiHook ? "Single Mode" : "Multi-Rank Mode"}
              </Button>
            </div>

            {!isMultiHook ? (
              <>
                <Field label="Opening Hook Speech (First 15 seconds)">
                  <textarea
                    rows={4}
                    value={hookInput}
                    onChange={(e) => setHookInput(e.target.value)}
                    placeholder="Enter opening sentence(s)..."
                    style={{
                      width: "100%",
                      padding: 12,
                      borderRadius: 8,
                      background: "rgba(0, 0, 0, 0.25)",
                      border: "1px solid rgba(255, 255, 255, 0.12)",
                      color: "#fff",
                      fontSize: 14,
                      resize: "vertical",
                    }}
                  />
                </Field>
                <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
                  <Button
                    variant="primary"
                    onClick={() => handleScoreHook(hookInput)}
                    disabled={hookLoading}
                    style={{ background: "#ef4444" }}
                  >
                    {hookLoading ? "Scoring..." : "Score Hook"}
                  </Button>
                </div>
                <div style={{ marginTop: 16 }}>
                  <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 8 }}>Test worked formulas:</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {SAMPLE_HOOKS.map((sample, idx) => (
                      <button
                        key={idx}
                        onClick={() => {
                          setHookInput(sample);
                          void handleScoreHook(sample);
                        }}
                        style={{
                          textAlign: "left",
                          padding: "6px 10px",
                          borderRadius: 6,
                          background: "rgba(255,255,255,0.03)",
                          border: "1px solid rgba(255,255,255,0.06)",
                          color: "#cbd5e1",
                          fontSize: 12,
                          cursor: "pointer",
                        }}
                      >
                        {sample}
                      </button>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <>
                <Field label="Paste Multiple Hooks (One per line to rank)">
                  <textarea
                    rows={10}
                    value={multiHookText}
                    onChange={(e) => setMultiHookText(e.target.value)}
                    placeholder="One hook per line..."
                    style={{
                      width: "100%",
                      padding: 12,
                      borderRadius: 8,
                      background: "rgba(0, 0, 0, 0.25)",
                      border: "1px solid rgba(255, 255, 255, 0.12)",
                      color: "#fff",
                      fontSize: 13,
                      resize: "vertical",
                    }}
                  />
                </Field>
                <div style={{ marginTop: 12 }}>
                  <Button
                    variant="primary"
                    onClick={handleScoreMultiHooks}
                    disabled={hookLoading}
                    style={{ background: "#ef4444" }}
                  >
                    {hookLoading ? "Ranking..." : "Rank All Hooks"}
                  </Button>
                </div>
              </>
            )}
          </div>

          {/* Results Panel */}
          <div
            style={{
              padding: 24,
              borderRadius: 14,
              background: "rgba(15, 23, 42, 0.6)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
            }}
          >
            {!isMultiHook ? (
              singleHookResult ? (
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
                    <div>
                      <div style={{ fontSize: 13, color: "#94a3b8", marginBottom: 4 }}>Verdict Score</div>
                      <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
                        <span style={{ fontSize: 36, fontWeight: 800, color: singleHookResult.verdict >= 70 ? "#4ade80" : singleHookResult.verdict >= 55 ? "#facc15" : "#f87171" }}>
                          {singleHookResult.verdict}
                        </span>
                        <span style={{ fontSize: 16, color: "#94a3b8" }}>/ 100</span>
                        <Tag
                          variant={singleHookResult.band === "STRONG" ? "success" : singleHookResult.band === "WORKABLE" ? "warning" : "error"}
                        >
                          {singleHookResult.band}
                        </Tag>
                      </div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 4 }}>Classified Formula</div>
                      <Tag variant="primary" style={{ background: "rgba(239,68,68,0.2)", color: "#f87171", border: "1px solid rgba(239,68,68,0.4)" }}>
                        {singleHookResult.formula}
                      </Tag>
                    </div>
                  </div>

                  {/* 5 Properties Progress Bars */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 10, margin: "20px 0" }}>
                    {(Object.entries(singleHookResult.properties) as [keyof typeof singleHookResult.properties, number][]).map(([prop, val]) => (
                      <div key={prop}>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
                          <span style={{ fontWeight: 600, color: singleHookResult.weakest === prop ? "#f87171" : "#cbd5e1" }}>
                            {prop} {singleHookResult.weakest === prop && "⚠️ (Weakest)"}
                          </span>
                          <span style={{ color: "#94a3b8" }}>{val} / 100</span>
                        </div>
                        <div
                          style={{
                            height: 8,
                            width: "100%",
                            background: "rgba(255,255,255,0.08)",
                            borderRadius: 4,
                            overflow: "hidden",
                          }}
                        >
                          <div
                            style={{
                              height: "100%",
                              width: `${val}%`,
                              background:
                                prop === singleHookResult.weakest
                                  ? "#ef4444"
                                  : val >= 70
                                  ? "#22c55e"
                                  : "#eab308",
                              borderRadius: 4,
                              transition: "width 0.3s ease",
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Weakest Link Fix */}
                  <div
                    style={{
                      padding: 14,
                      borderRadius: 8,
                      background: "rgba(239, 68, 68, 0.08)",
                      border: "1px solid rgba(239, 68, 68, 0.2)",
                      marginBottom: 16,
                    }}
                  >
                    <div style={{ fontSize: 12, fontWeight: 700, color: "#f87171", marginBottom: 2 }}>
                      Prescriptive Fix for Weakest Link ({singleHookResult.weakest}):
                    </div>
                    <div style={{ fontSize: 13, color: "#f1f5f9" }}>{singleHookResult.fix}</div>
                  </div>

                  {/* Formula Worked Example */}
                  {singleHookResult.formula_info && (
                    <div
                      style={{
                        padding: 14,
                        borderRadius: 8,
                        background: "rgba(30, 41, 59, 0.5)",
                        border: "1px solid rgba(255, 255, 255, 0.06)",
                      }}
                    >
                      <div style={{ fontSize: 12, fontWeight: 600, color: "#94a3b8", marginBottom: 4 }}>
                        Formula Shape: {singleHookResult.formula_info.shape}
                      </div>
                      <div style={{ fontSize: 12, color: "#cbd5e1", fontStyle: "italic" }}>
                        Example: "{singleHookResult.formula_info.example}"
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <Empty
                  icon={Sparkles}
                  title="No hook evaluated yet"
                  description="Type opening speech or select an example above and click Evaluate Hook."
                />
              )
            ) : multiHookResults.length ? (
              <div>
                <h4 style={{ margin: "0 0 12px 0", fontSize: 14 }}>Ranked Results ({multiHookResults.length})</h4>
                <div style={{ display: "flex", flexDirection: "column", gap: 10, maxHeight: 480, overflowY: "auto" }}>
                  {multiHookResults.map((r, i) => (
                    <div
                      key={i}
                      style={{
                        padding: 12,
                        borderRadius: 8,
                        background: "rgba(30, 41, 59, 0.4)",
                        border: "1px solid rgba(255, 255, 255, 0.06)",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span style={{ fontSize: 12, fontWeight: 700, color: "#94a3b8" }}>#{i + 1}</span>
                          <span style={{ fontWeight: 700, fontSize: 15, color: r.verdict >= 70 ? "#4ade80" : "#facc15" }}>
                            {r.verdict}/100
                          </span>
                          <Tag variant={r.band === "STRONG" ? "success" : "warning"}>{r.band}</Tag>
                        </div>
                        <Tag variant="primary">{r.formula}</Tag>
                      </div>
                      <div style={{ fontSize: 13, color: "#f8fafc", marginBottom: 6 }}>"{r.hook}"</div>
                      <div style={{ fontSize: 11, color: "#94a3b8" }}>
                        Weakest: <span style={{ color: "#f87171" }}>{r.weakest}</span> — {r.fix}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <Empty
                icon={ListFilter}
                title="No hooks ranked"
                description="Click 'Rank All Hooks' to evaluate the candidate list."
              />
            )}
          </div>
        </div>
      )}

      {/* TAB 2: PACKAGING LINTER */}
      {activeTab === "package" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
          {/* Inputs */}
          <div
            style={{
              padding: 24,
              borderRadius: 14,
              background: "rgba(15, 23, 42, 0.6)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
            }}
          >
            <SectionTitle
              title="Title & Thumbnail Synergy"
              note="Lints character limits, mobile feed cuts, and duplication between title and thumbnail"
            />
            <Field label="YouTube Video Title">
              <input
                type="text"
                value={titleInput}
                onChange={(e) => {
                  setTitleInput(e.target.value);
                  void handleLintTitle(e.target.value, thumbInput);
                }}
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  borderRadius: 8,
                  background: "rgba(0,0,0,0.25)",
                  border: "1px solid rgba(255,255,255,0.12)",
                  color: "#fff",
                  fontSize: 14,
                }}
              />
            </Field>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "#94a3b8", marginTop: 4 }}>
              <span>Desktop search truncates at ~60, Mobile at ~40</span>
              <span style={{ color: titleInput.length > 60 ? "#f87171" : titleInput.length > 40 ? "#facc15" : "#4ade80" }}>
                {titleInput.length} chars
              </span>
            </div>

            <div style={{ marginTop: 20 }}>
              <Field label="Thumbnail Text (Optional — 3-4 words max)">
                <input
                  type="text"
                  value={thumbInput}
                  onChange={(e) => {
                    setThumbInput(e.target.value);
                    void handleLintTitle(titleInput, e.target.value);
                  }}
                  placeholder="e.g. AI RAN IT"
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    borderRadius: 8,
                    background: "rgba(0,0,0,0.25)",
                    border: "1px solid rgba(255,255,255,0.12)",
                    color: "#fff",
                    fontSize: 14,
                  }}
                />
              </Field>
            </div>

            <div style={{ marginTop: 20 }}>
              <Button
                variant="primary"
                onClick={() => handleLintTitle(titleInput, thumbInput)}
                disabled={lintLoading}
                style={{ background: "#ef4444" }}
              >
                {lintLoading ? "Linting..." : "Re-Lint Packaging"}
              </Button>
            </div>
          </div>

          {/* Previews and Lint Report */}
          <div
            style={{
              padding: 24,
              borderRadius: 14,
              background: "rgba(15, 23, 42, 0.6)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
            }}
          >
            {lintResult ? (
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                  <div>
                    <div style={{ fontSize: 12, color: "#94a3b8" }}>Packaging Quality Score</div>
                    <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
                      <span
                        style={{
                          fontSize: 36,
                          fontWeight: 800,
                          color: lintResult.score >= 75 ? "#4ade80" : lintResult.score >= 50 ? "#facc15" : "#f87171",
                        }}
                      >
                        {lintResult.score}
                      </span>
                      <span style={{ fontSize: 16, color: "#94a3b8" }}>/ 100</span>
                      <Tag variant={lintResult.status === "PASS" ? "success" : lintResult.status === "WARN" ? "warning" : "error"}>
                        {lintResult.status}
                      </Tag>
                    </div>
                  </div>
                </div>

                {/* Feed Previews */}
                <div style={{ marginBottom: 20 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "#94a3b8", marginBottom: 6 }}>
                    📱 Mobile Feed Simulation (Cuts at ~40 chars):
                  </div>
                  <div
                    style={{
                      padding: "10px 14px",
                      borderRadius: 8,
                      background: "rgba(0,0,0,0.3)",
                      border: "1px solid rgba(255,255,255,0.06)",
                      fontSize: 13,
                      fontWeight: 600,
                      color: "#f8fafc",
                    }}
                  >
                    {lintResult.mobile_preview}
                  </div>
                </div>

                <div style={{ marginBottom: 20 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "#94a3b8", marginBottom: 6 }}>
                    💻 Desktop Search Simulation (Cuts at ~60 chars):
                  </div>
                  <div
                    style={{
                      padding: "10px 14px",
                      borderRadius: 8,
                      background: "rgba(0,0,0,0.3)",
                      border: "1px solid rgba(255,255,255,0.06)",
                      fontSize: 13,
                      fontWeight: 600,
                      color: "#f8fafc",
                    }}
                  >
                    {lintResult.desktop_preview}
                  </div>
                </div>

                {/* Issues List */}
                {lintResult.issues.length > 0 && (
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: "#f87171", marginBottom: 6 }}>
                      ⚠️ Things to Address:
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      {lintResult.issues.map((iss, i) => (
                        <div
                          key={i}
                          style={{
                            display: "flex",
                            alignItems: "flex-start",
                            gap: 8,
                            padding: "8px 10px",
                            borderRadius: 6,
                            background: "rgba(239, 68, 68, 0.08)",
                            border: "1px solid rgba(239, 68, 68, 0.2)",
                            fontSize: 12,
                            color: "#fecaca",
                          }}
                        >
                          <AlertTriangle size={14} style={{ marginTop: 2, flexShrink: 0 }} />
                          <span>{iss.message}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Good Points List */}
                {lintResult.good.length > 0 && (
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: "#4ade80", marginBottom: 6 }}>
                      ✅ Working Well:
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      {lintResult.good.map((g, i) => (
                        <div
                          key={i}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 8,
                            padding: "6px 10px",
                            borderRadius: 6,
                            background: "rgba(34, 197, 94, 0.06)",
                            fontSize: 12,
                            color: "#bbf7d0",
                          }}
                        >
                          <CheckCircle2 size={14} style={{ flexShrink: 0 }} />
                          <span>{g}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <Empty
                icon={Type}
                title="Enter title to lint"
                description="Type your video title and optional thumbnail text to run character truncation and duplication diagnostics."
              />
            )}
          </div>
        </div>
      )}

      {/* TAB 3: DEAD AIR & EDL */}
      {activeTab === "deadair" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
          <div
            style={{
              padding: 24,
              borderRadius: 14,
              background: "rgba(15, 23, 42, 0.6)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
            }}
          >
            <SectionTitle
              title="Edit Decision List (EDL)"
              note="Finds silence dead-air gaps, filler cues ('um', 'basically') and retakes from transcript"
            />

            {finishedJobs.length > 0 && (
              <Field label="Load Transcript from Existing Studio Job">
                <select
                  value={selectedJobId}
                  onChange={(e) => {
                    setSelectedJobId(e.target.value);
                    if (e.target.value) setDeadAirSrt("");
                  }}
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    borderRadius: 8,
                    background: "rgba(0,0,0,0.25)",
                    border: "1px solid rgba(255,255,255,0.12)",
                    color: "#fff",
                    fontSize: 13,
                  }}
                >
                  <option value="">-- Or paste SRT / Whisper JSON below --</option>
                  {finishedJobs.map((j) => (
                    <option key={j.id} value={j.id}>
                      Job {j.id} ({j.source.split("/").pop()})
                    </option>
                  ))}
                </select>
              </Field>
            )}

            {!selectedJobId && (
              <div style={{ marginTop: 12 }}>
                <Field label="Paste SRT / VTT / Whisper JSON Transcript">
                  <textarea
                    rows={8}
                    value={deadAirSrt}
                    onChange={(e) => setDeadAirSrt(e.target.value)}
                    placeholder="1&#10;00:00:01,000 --> 00:00:03,500&#10;Welcome back..."
                    style={{
                      width: "100%",
                      padding: 12,
                      borderRadius: 8,
                      background: "rgba(0,0,0,0.25)",
                      border: "1px solid rgba(255,255,255,0.12)",
                      color: "#fff",
                      fontSize: 12,
                      fontFamily: "monospace",
                    }}
                  />
                </Field>
              </div>
            )}

            <div style={{ marginTop: 16 }}>
              <Field label={`Dead Air Silence Floor: ${deadAirFloor}s`}>
                <input
                  type="range"
                  min="0.2"
                  max="1.5"
                  step="0.05"
                  value={deadAirFloor}
                  onChange={(e) => setDeadAirFloor(parseFloat(e.target.value))}
                  style={{ width: "100%" }}
                />
              </Field>
              <div style={{ fontSize: 11, color: "#94a3b8" }}>
                Pauses longer than this threshold are cut from the middle (preserving breathing room).
              </div>
            </div>

            <div style={{ marginTop: 20 }}>
              <Button
                variant="primary"
                onClick={handleRunDeadAir}
                disabled={deadAirLoading || (!selectedJobId && !deadAirSrt.trim())}
                style={{ background: "#ef4444" }}
              >
                {deadAirLoading ? "Analyzing..." : "Generate Edit Decision List"}
              </Button>
            </div>
          </div>

          {/* EDL Results */}
          <div
            style={{
              padding: 24,
              borderRadius: 14,
              background: "rgba(15, 23, 42, 0.6)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
            }}
          >
            {deadAirResult ? (
              <div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 20 }}>
                  <div style={{ padding: 12, borderRadius: 8, background: "rgba(0,0,0,0.25)", textAlign: "center" }}>
                    <div style={{ fontSize: 11, color: "#94a3b8" }}>Original Duration</div>
                    <div style={{ fontSize: 18, fontWeight: 700 }}>{deadAirResult.duration.toFixed(1)}s</div>
                  </div>
                  <div style={{ padding: 12, borderRadius: 8, background: "rgba(239,68,68,0.1)", textAlign: "center" }}>
                    <div style={{ fontSize: 11, color: "#f87171" }}>Time Removed</div>
                    <div style={{ fontSize: 18, fontWeight: 700, color: "#f87171" }}>
                      -{deadAirResult.removed_seconds.toFixed(1)}s
                    </div>
                  </div>
                  <div style={{ padding: 12, borderRadius: 8, background: "rgba(34,197,94,0.1)", textAlign: "center" }}>
                    <div style={{ fontSize: 11, color: "#4ade80" }}>Runtime Saved</div>
                    <div style={{ fontSize: 18, fontWeight: 700, color: "#4ade80" }}>
                      {deadAirResult.percent_saved}%
                    </div>
                  </div>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>Proposed Cuts ({deadAirResult.cuts.length})</div>
                  <Button
                    variant="ghost"
                    onClick={() => {
                      navigator.clipboard.writeText(JSON.stringify(deadAirResult.cuts, null, 2));
                      notify("Cuts copied to clipboard");
                    }}
                  >
                    <Copy size={14} /> Copy Cuts
                  </Button>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: 380, overflowY: "auto" }}>
                  {deadAirResult.cuts.map((c, i) => (
                    <div
                      key={i}
                      style={{
                        padding: "8px 12px",
                        borderRadius: 6,
                        background: "rgba(255,255,255,0.03)",
                        border: "1px solid rgba(255,255,255,0.06)",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        fontSize: 12,
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <Tag
                          variant={c.kind === "DEAD" ? "default" : c.kind === "FILLER" ? "warning" : "error"}
                        >
                          {c.kind}
                        </Tag>
                        <span style={{ fontFamily: "monospace", color: "#f1f5f9" }}>
                          {c.start.toFixed(2)}s → {c.end.toFixed(2)}s
                        </span>
                      </div>
                      <div style={{ color: "#94a3b8" }}>{c.why}</div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <Empty
                icon={Scissors}
                title="No cuts generated"
                description="Select a job or paste SRT transcript to generate an edit decision list."
              />
            )}
          </div>
        </div>
      )}

      {/* TAB 4: CHAPTERS GENERATOR */}
      {activeTab === "chapters" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
          <div
            style={{
              padding: 24,
              borderRadius: 14,
              background: "rgba(15, 23, 42, 0.6)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
            }}
          >
            <SectionTitle
              title="YouTube Chapters Generator"
              note="Generates timestamps validated against YouTube's 3 rules (00:00 start, 3+ chapters, 10s+ each)"
            />

            {finishedJobs.length > 0 && (
              <Field label="Load Transcript from Existing Studio Job">
                <select
                  value={chaptersJobId}
                  onChange={(e) => {
                    setChaptersJobId(e.target.value);
                    if (e.target.value) setChaptersSrt("");
                  }}
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    borderRadius: 8,
                    background: "rgba(0,0,0,0.25)",
                    border: "1px solid rgba(255,255,255,0.12)",
                    color: "#fff",
                    fontSize: 13,
                  }}
                >
                  <option value="">-- Or paste SRT / Whisper JSON below --</option>
                  {finishedJobs.map((j) => (
                    <option key={j.id} value={j.id}>
                      Job {j.id} ({j.source.split("/").pop()})
                    </option>
                  ))}
                </select>
              </Field>
            )}

            {!chaptersJobId && (
              <div style={{ marginTop: 12 }}>
                <Field label="Paste SRT / VTT / Whisper JSON Transcript">
                  <textarea
                    rows={8}
                    value={chaptersSrt}
                    onChange={(e) => setChaptersSrt(e.target.value)}
                    placeholder="Transcript text..."
                    style={{
                      width: "100%",
                      padding: 12,
                      borderRadius: 8,
                      background: "rgba(0,0,0,0.25)",
                      border: "1px solid rgba(255,255,255,0.12)",
                      color: "#fff",
                      fontSize: 12,
                      fontFamily: "monospace",
                    }}
                  />
                </Field>
              </div>
            )}

            <div style={{ marginTop: 16 }}>
              <Field label={`Target Number of Chapters: ${chaptersTarget}`}>
                <input
                  type="range"
                  min="3"
                  max="15"
                  value={chaptersTarget}
                  onChange={(e) => setChaptersTarget(parseInt(e.target.value))}
                  style={{ width: "100%" }}
                />
              </Field>
            </div>

            <div style={{ marginTop: 20 }}>
              <Button
                variant="primary"
                onClick={handleRunChapters}
                disabled={chaptersLoading || (!chaptersJobId && !chaptersSrt.trim())}
                style={{ background: "#ef4444" }}
              >
                {chaptersLoading ? "Generating..." : "Generate Chapters"}
              </Button>
            </div>
          </div>

          {/* Chapters Output */}
          <div
            style={{
              padding: 24,
              borderRadius: 14,
              background: "rgba(15, 23, 42, 0.6)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
            }}
          >
            {chaptersResult ? (
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700 }}>Generated Chapters ({chaptersResult.chapters.length})</div>
                    <div style={{ fontSize: 12, color: "#94a3b8" }}>
                      Status:{" "}
                      <Tag variant={chaptersResult.valid ? "success" : "error"}>
                        {chaptersResult.valid ? "YouTube Compliant" : "Invalid Specs"}
                      </Tag>
                    </div>
                  </div>
                  <Button
                    variant="primary"
                    onClick={() => {
                      navigator.clipboard.writeText(chaptersResult.formatted_text);
                      setCopiedChapters(true);
                      setTimeout(() => setCopiedChapters(false), 2000);
                      notify("Chapters block copied!");
                    }}
                    style={{ background: "#22c55e" }}
                  >
                    {copiedChapters ? <Check size={14} /> : <Copy size={14} />}
                    {copiedChapters ? "Copied" : "Copy Description Block"}
                  </Button>
                </div>

                <div
                  style={{
                    padding: 16,
                    borderRadius: 8,
                    background: "rgba(0,0,0,0.3)",
                    border: "1px solid rgba(255,255,255,0.08)",
                    fontFamily: "monospace",
                    fontSize: 13,
                    lineHeight: 1.8,
                    color: "#f8fafc",
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {chaptersResult.formatted_text}
                </div>

                <div style={{ marginTop: 16, fontSize: 12, color: "#94a3b8" }}>
                  💡 Tip: Retitle every draft line into your own words before publishing; the draft titles are generated from topic keywords.
                </div>
              </div>
            ) : (
              <Empty
                icon={Clock}
                title="No chapters generated"
                description="Select a job or paste transcript to generate compliant YouTube timestamps."
              />
            )}
          </div>
        </div>
      )}

      {/* TAB 5: RETENTION DIAGNOSTIC */}
      {activeTab === "retention" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
          <div
            style={{
              padding: 24,
              borderRadius: 14,
              background: "rgba(15, 23, 42, 0.6)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
            }}
          >
            <SectionTitle
              title="Audience Retention Diagnostic"
              note="Upload YouTube Studio Retention CSV to diagnose Hook Leak, Cliff Moments, and Slide rate"
            />
            <Field label="Retention CSV (Position, Percentage)">
              <textarea
                rows={8}
                value={retentionCsv}
                onChange={(e) => setRetentionCsv(e.target.value)}
                placeholder="0,100&#10;5,92&#10;10,84..."
                style={{
                  width: "100%",
                  padding: 12,
                  borderRadius: 8,
                  background: "rgba(0,0,0,0.25)",
                  border: "1px solid rgba(255,255,255,0.12)",
                  color: "#fff",
                  fontSize: 12,
                  fontFamily: "monospace",
                }}
              />
            </Field>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 12 }}>
              <Field label="Video Duration (Seconds)">
                <input
                  type="number"
                  value={retentionDuration}
                  onChange={(e) => setRetentionDuration(parseFloat(e.target.value))}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    borderRadius: 6,
                    background: "rgba(0,0,0,0.25)",
                    border: "1px solid rgba(255,255,255,0.1)",
                    color: "#fff",
                  }}
                />
              </Field>
              {finishedJobs.length > 0 && (
                <Field label="Correlate Transcript (Optional)">
                  <select
                    value={retentionJobId}
                    onChange={(e) => setRetentionJobId(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      borderRadius: 6,
                      background: "rgba(0,0,0,0.25)",
                      border: "1px solid rgba(255,255,255,0.1)",
                      color: "#fff",
                      fontSize: 12,
                    }}
                  >
                    <option value="">-- No transcript mapping --</option>
                    {finishedJobs.map((j) => (
                      <option key={j.id} value={j.id}>
                        Job {j.id}
                      </option>
                    ))}
                  </select>
                </Field>
              )}
            </div>

            <div style={{ marginTop: 20 }}>
              <Button
                variant="primary"
                onClick={handleRunRetention}
                disabled={retentionLoading || !retentionCsv.trim()}
                style={{ background: "#ef4444" }}
              >
                {retentionLoading ? "Analyzing..." : "Diagnose Retention"}
              </Button>
            </div>
          </div>

          {/* Retention Diagnostic Results */}
          <div
            style={{
              padding: 24,
              borderRadius: 14,
              background: "rgba(15, 23, 42, 0.6)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
            }}
          >
            {retentionResult ? (
              <div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
                  <div style={{ padding: 16, borderRadius: 10, background: "rgba(0,0,0,0.3)" }}>
                    <div style={{ fontSize: 12, color: "#94a3b8" }}>Hook Leak (First 30s)</div>
                    <div style={{ fontSize: 24, fontWeight: 800, color: retentionResult.hook_leak < 25 ? "#4ade80" : retentionResult.hook_leak < 40 ? "#facc15" : "#f87171" }}>
                      {retentionResult.hook_leak.toFixed(1)}% lost
                    </div>
                    <Tag
                      variant={retentionResult.hook_verdict === "healthy" ? "success" : retentionResult.hook_verdict === "leaking" ? "warning" : "error"}
                      style={{ marginTop: 6 }}
                    >
                      {retentionResult.hook_verdict.toUpperCase()}
                    </Tag>
                  </div>
                  <div style={{ padding: 16, borderRadius: 10, background: "rgba(0,0,0,0.3)" }}>
                    <div style={{ fontSize: 12, color: "#94a3b8" }}>Middle Slide Rate</div>
                    <div style={{ fontSize: 24, fontWeight: 800, color: "#94a3b8" }}>
                      {retentionResult.slide_rate.toFixed(3)}%/s
                    </div>
                    <div style={{ fontSize: 11, color: "#cbd5e1", marginTop: 6 }}>Flat pacing bleed rate</div>
                  </div>
                </div>

                <div
                  style={{
                    padding: 12,
                    borderRadius: 8,
                    background: "rgba(239, 68, 68, 0.08)",
                    border: "1px solid rgba(239, 68, 68, 0.2)",
                    marginBottom: 20,
                    fontSize: 13,
                    color: "#fecaca",
                  }}
                >
                  <strong>Diagnostic Recommendation:</strong> {retentionResult.advice}
                </div>

                <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8 }}>
                  Steepest Cliff Drops (Moments Viewers Left):
                </div>
                {retentionResult.cliffs.length > 0 ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {retentionResult.cliffs.map((c, i) => (
                      <div
                        key={i}
                        style={{
                          padding: "10px 12px",
                          borderRadius: 6,
                          background: "rgba(255,255,255,0.03)",
                          border: "1px solid rgba(255,255,255,0.06)",
                          fontSize: 12,
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                          <span style={{ fontWeight: 700, color: "#f87171" }}>-{c.lost.toFixed(1)}% drop</span>
                          <span style={{ color: "#94a3b8", fontFamily: "monospace" }}>at {c.label}</span>
                        </div>
                        {c.spoken && (
                          <div style={{ color: "#cbd5e1", fontStyle: "italic", fontSize: 11 }}>
                            Spoken words: "{c.spoken}"
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ fontSize: 12, color: "#94a3b8" }}>No steep cliff drops found; loss is gradual pacing slide.</div>
                )}
              </div>
            ) : (
              <Empty
                icon={TrendingDown}
                title="No retention data"
                description="Paste retention CSV to diagnose audience dropoff, hook leak, and middle slide."
              />
            )}
          </div>
        </div>
      )}

      {/* TAB 6: VIRAL SWIPE OUTLIERS */}
      {activeTab === "swipe" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
          <div
            style={{
              padding: 24,
              borderRadius: 14,
              background: "rgba(15, 23, 42, 0.6)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
            }}
          >
            <SectionTitle
              title="Viral Swipe Outlier Ranker"
              note="Ranks videos by how far each beat its OWN channel median, not channel size"
            />
            <Field label="Collected Videos JSON">
              <textarea
                rows={10}
                value={swipeJson}
                onChange={(e) => setSwipeJson(e.target.value)}
                placeholder='[{"channel": "...", "title": "...", "views": 100000}, ...]'
                style={{
                  width: "100%",
                  padding: 12,
                  borderRadius: 8,
                  background: "rgba(0,0,0,0.25)",
                  border: "1px solid rgba(255,255,255,0.12)",
                  color: "#fff",
                  fontSize: 12,
                  fontFamily: "monospace",
                }}
              />
            </Field>

            <div style={{ marginTop: 12 }}>
              <Field label={`Minimum Multiple: ${swipeMin}x median`}>
                <input
                  type="range"
                  min="1.2"
                  max="5.0"
                  step="0.1"
                  value={swipeMin}
                  onChange={(e) => setSwipeMin(parseFloat(e.target.value))}
                  style={{ width: "100%" }}
                />
              </Field>
            </div>

            <div style={{ marginTop: 20 }}>
              <Button
                variant="primary"
                onClick={handleRunSwipe}
                disabled={swipeLoading || !swipeJson.trim()}
                style={{ background: "#ef4444" }}
              >
                {swipeLoading ? "Ranking Outliers..." : "Identify Outliers"}
              </Button>
            </div>
          </div>

          {/* Swipe Outlier Results */}
          <div
            style={{
              padding: 24,
              borderRadius: 14,
              background: "rgba(15, 23, 42, 0.6)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
            }}
          >
            {swipeResult ? (
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                  <div style={{ fontSize: 13, fontWeight: 700 }}>
                    Outliers Found ({swipeResult.outliers.length} videos)
                  </div>
                  <Tag variant="primary">Over {swipeMin}x Median</Tag>
                </div>

                {swipeResult.top_formulas.length > 0 && (
                  <div style={{ marginBottom: 16, padding: 12, borderRadius: 8, background: "rgba(0,0,0,0.25)" }}>
                    <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 6 }}>Outlier Formula Frequency:</div>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      {swipeResult.top_formulas.map((f, i) => (
                        <Tag key={i} variant="default" style={{ fontSize: 11 }}>
                          {f.count}x {f.formula}
                        </Tag>
                      ))}
                    </div>
                  </div>
                )}

                <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: 380, overflowY: "auto" }}>
                  {swipeResult.outliers.map((o, i) => (
                    <div
                      key={i}
                      style={{
                        padding: "10px 12px",
                        borderRadius: 6,
                        background: "rgba(255,255,255,0.03)",
                        border: "1px solid rgba(255,255,255,0.06)",
                        fontSize: 12,
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                        <span style={{ fontWeight: 800, color: "#4ade80", fontSize: 14 }}>
                          {o.multiple.toFixed(2)}x
                        </span>
                        <Tag variant="primary">{o.formula}</Tag>
                      </div>
                      <div style={{ fontWeight: 600, color: "#f8fafc", marginBottom: 4 }}>"{o.title}"</div>
                      <div style={{ fontSize: 11, color: "#94a3b8" }}>
                        Channel: {o.channel} · Views: {o.views.toLocaleString()} (vs {o.median.toLocaleString()} median)
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <Empty
                icon={TrendingUp}
                title="No outliers identified"
                description="Paste collected niche JSON to calculate own-channel median multiples."
              />
            )}
          </div>
        </div>
      )}

      {/* TAB 7: CREATOR VOICE PROFILE */}
      {activeTab === "voice" && (
        <div
          style={{
            padding: 24,
            borderRadius: 14,
            background: "rgba(15, 23, 42, 0.6)",
            border: "1px solid rgba(255, 255, 255, 0.08)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <SectionTitle
              title="Creator Voice Profile (voice.md)"
              note="All 11 YouTube agent skills read this file to match how you talk on camera and respect your boundaries"
            />
            <Button
              variant="primary"
              onClick={handleSaveVoice}
              disabled={voiceSaving}
              style={{ background: "#22c55e", display: "flex", alignItems: "center", gap: 6 }}
            >
              <Save size={16} />
              {voiceSaving ? "Saving..." : "Save & Sync Voice Profile"}
            </Button>
          </div>

          <Field label="config/voice.md (Synced with ~/.claude/youtube/voice.md)">
            <textarea
              rows={16}
              value={voiceContent}
              onChange={(e) => setVoiceContent(e.target.value)}
              placeholder="Paste or write your voice profile markdown..."
              style={{
                width: "100%",
                padding: 16,
                borderRadius: 8,
                background: "rgba(0,0,0,0.3)",
                border: "1px solid rgba(255,255,255,0.12)",
                color: "#f8fafc",
                fontSize: 13,
                fontFamily: "monospace",
                lineHeight: 1.6,
              }}
            />
          </Field>
          <div style={{ marginTop: 12, fontSize: 12, color: "#94a3b8" }}>
            💡 Spending ten minutes calibrating your voice file ensures generated scripts, comments, and titles sound like you rather than generic AI copy.
          </div>
        </div>
      )}
    </div>
  );
}
