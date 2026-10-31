import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  AudioLines,
  Check,
  ChevronRight,
  Cpu,
  Database,
  Eye,
  EyeOff,
  Globe,
  KeyRound,
  Link2,
  MessageSquareQuote,
  MonitorPlay,
  Pause,
  Play,
  RotateCcw,
  Copy,
  Save,
  Search,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  Workflow,
  X,
  Youtube,
  ExternalLink,
} from "lucide-react";
import { api, providerName } from "./api";
import type {
  Connections,
  Preferences,
  PromptInfo,
  System,
  YouTubeAccount,
  YouTubeConnections,
} from "./types";
import {
  Button,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Modal,
  PageHeading,
  SectionTitle,
  Switch,
  useStudio,
} from "./ui";

const tabs = [
  ["clipping", "Clip & edit", SlidersHorizontal],
  ["ai", "AI & discovery", Sparkles],
  ["prompts", "AI Prompts", MessageSquareQuote],
  ["automation", "Automation", Workflow],
  ["connections", "Connections", Link2],
  ["system", "System", Cpu],
] as const;
export default function Settings() {
  const { boot, refresh, notify } = useStudio(),
    [params, setParams] = useSearchParams(),
    tab = params.get("tab") || "clipping";

  const [draft, setDraft] = useState<Preferences>(boot.preferences),
    [busy, setBusy] = useState(false),
    [saved, setSaved] = useState(boot.preferences);
  const [focusInvalid, setFocusInvalid] = useState(false);
  const [focusReset, setFocusReset] = useState(0);
  const dirty = JSON.stringify(draft) !== JSON.stringify(saved);
  function set<K extends keyof Preferences>(key: K, value: Preferences[K]) {
    setDraft((p) => ({ ...p, [key]: value }));
  }
  async function save() {
    setBusy(true);
    try {
      const result = await api<Preferences>("/preferences", "PUT", draft);
      setSaved(result);
      setDraft(result);
      refresh();
      notify("Preferences saved. New projects will use these settings.");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  const toggle = (
    key: keyof Preferences,
    label: string,
    description: string,
  ) => (
    <Switch
      label={label}
      description={description}
      checked={Boolean(draft[key])}
      onChange={(v) => set(key, v as never)}
    />
  );
  const select = (
    key: keyof Preferences,
    label: string,
    options: [string | number, string][],
    hint?: string,
  ) => (
    <Field label={label} hint={hint}>
      <select
        value={String(draft[key] ?? "")}
        onChange={(e) =>
          set(
            key,
            (typeof draft[key] === "number"
              ? +e.target.value
              : e.target.value || null) as never,
          )
        }
      >
        {options.map(([value, name]) => (
          <option key={value} value={value}>
            {name}
          </option>
        ))}
      </select>
    </Field>
  );
  const number = (
    key: keyof Preferences,
    label: string,
    min: number,
    max: number,
    hint?: string,
  ) => (
    <Field label={label} hint={hint}>
      <input
        type="number"
        min={min}
        max={max}
        value={Number(draft[key])}
        onChange={(e) => set(key, +e.target.value as never)}
      />
    </Field>
  );
  return (
    <div className="page settings-page">
      <PageHeading
        eyebrow="SET IT UP YOUR WAY"
        title="A studio that works like you."
        description="Thoughtful defaults. Precise control when you need it."
      >
        {!["connections", "system", "prompts"].includes(tab) && (
          <Button
            variant="primary"
            icon={Check}
            disabled={!dirty || focusInvalid}
            busy={busy}
            onClick={() => void save()}
          >
            Save changes
          </Button>
        )}
      </PageHeading>
      <div className="settings-layout">
        <nav className="settings-nav" aria-label="Settings sections">
          {tabs.map(([key, label, Icon]) => (
            <button
              key={key}
              className={tab === key ? "selected" : ""}
              onClick={() => setParams({ tab: key })}
            >
              <Icon size={17} />
              {label}
              <ChevronRight size={13} />
            </button>
          ))}
          <div className="settings-nav-note">
            <ShieldCheck size={18} />
            <p>
              Preferences apply to new jobs. Existing projects keep their
              original settings.
            </p>
          </div>
        </nav>
        <div className="settings-content">
          {tab === "clipping" && (
            <>
              <section className="settings-section">
                <SectionTitle
                  title="The shape of your clips"
                  note="Set the format once. Keep your output consistent."
                />
                <div className="layout-choice">
                  <button
                    className={draft.layout === "square_hook" ? "selected" : ""}
                    onClick={() => set("layout", "square_hook")}
                  >
                    <div className="layout-diagram square">
                      <i />
                      <b />
                      <span />
                    </div>
                    <div>
                      <strong>Square + hook</strong>
                      <small>1:1 video on a 9:16 canvas</small>
                    </div>
                    {draft.layout === "square_hook" && <Check size={16} />}
                  </button>
                  <button
                    className={draft.layout === "four_three_hook" ? "selected" : ""}
                    onClick={() => set("layout", "four_three_hook")}
                  >
                    <div className="layout-diagram four-three">
                      <i />
                      <b />
                      <span />
                    </div>
                    <div>
                      <strong>4:3 + hook</strong>
                      <small>4:3 video on a 9:16 canvas (Fast Cut)</small>
                    </div>
                    {draft.layout === "four_three_hook" && <Check size={16} />}
                  </button>
                  <button
                    className={draft.layout === "legacy" ? "selected" : ""}
                    onClick={() => set("layout", "legacy")}
                  >
                    <div className="layout-diagram vertical">
                      <b />
                      <span />
                    </div>
                    <div>
                      <strong>Full vertical</strong>
                      <small>Immersive 9:16 video</small>
                    </div>
                    {draft.layout === "legacy" && <Check size={16} />}
                  </button>
                </div>
              </section>
              <section className="settings-section">
                <SectionTitle
                  title="Fast Cut defaults"
                  note="Sequential video slicing into fixed-duration parts with Part header labels."
                />
                {toggle(
                  "fast_cut",
                  "Enable Fast Cut mode by default",
                  "Bypasses AI discovery to slice full video into sequential numbered parts.",
                )}
                {draft.fast_cut && (
                  <>
                    <div className="form-grid">
                      {number(
                        "fast_cut_duration",
                        "Part duration (seconds)",
                        10,
                        600,
                        "Length of each sequential clip (default: 90 seconds).",
                      )}
                    </div>
                    {toggle(
                      "fast_cut_skip_intro",
                      "Skip first 3 min",
                      "When enabled, skips the first 180 seconds (3 minutes) before cutting parts.",
                    )}
                  </>
                )}
              </section>
              <section className="settings-section">
                <SectionTitle
                  title="Video rendering & resolution"
                  note="Canvas sizing and framing parameters."
                />
                <div className="form-grid">
                  {select("width", "Export resolution", [
                    [1080, "1080 × 1920 · Full HD"],
                    [720, "720 × 1280"],
                    [360, "360 × 640 · draft"],
                  ])}
                  {select("reframe", "Reframing", [
                    ["auto", "Auto · face aware"],
                    ["center", "Center crop"],
                    ["blur", "Preserve frame + blur"],
                  ])}
                  {select(
                    "fps",
                    "Export frame rate",
                    [
                      [60, "60 fps"],
                      [30, "30 fps"],
                    ],
                    "Lower-frame-rate sources retain their original motion.",
                  )}
                  {select(
                    "export_quality",
                    "Export quality",
                    [
                      ["high", "High-quality master"],
                      ["compact", "Compact · Telegram size budget"],
                    ],
                    "Large masters get a separate smaller Telegram delivery copy.",
                  )}
                  {select("color_grade", "Colour finish", [
                    ["natural", "Natural · subtle contrast and detail"],
                    ["vivid", "Vivid · restrained extra colour"],
                    ["off", "Off · preserve source look"],
                  ])}
                  {number(
                    "min_seconds",
                    "Minimum clip length · seconds",
                    6,
                    90,
                  )}
                  {number(
                    "max_seconds",
                    "Maximum clip length · seconds",
                    6,
                    120,
                  )}
                </div>
                {toggle(
                  "smart_crop",
                  "Smart face tracking",
                  "Follow face groups with stable, scene-aware crop motion.",
                )}
                {toggle(
                  "preserve_wide_groups",
                  "Preserve wide groups",
                  "Fit wide shots when a square crop would cut people off.",
                )}
                {toggle(
                  "trim_edges",
                  "Tidy the beginning and end",
                  "Trim unnecessary edge silence while retaining the complete thought.",
                )}
              </section>
              <section className="settings-section">
                <SectionTitle
                  title="Titles & captions"
                  note="Make every word earn its place."
                />
                <div className="form-grid">
                  {select("hook_style", "Hook direction", [
                    ["auto", "Editorial choice"],
                    ["curiosity", "Earned curiosity"],
                    ["contrast", "Honest contrast"],
                    ["direct", "Direct value"],
                  ])}
                  {select(
                    "text_mode",
                    "Hook & caption language",
                    [
                      ["romanized", "English letters · keep spoken language"],
                      ["english", "Translate to English"],
                      ["source", "Original language and script"],
                    ],
                    "Romanized keeps Hindi as Hinglish with original word timing. English translations use phrase timing.",
                  )}
                  {select("style", "Caption style", [
                    ["studio", "Studio · mint highlight"],
                    ["bold", "Bold · yellow highlight"],
                    ["minimal", "Minimal · white"],
                  ])}
                  <Field
                    label="Speech language"
                    hint="Use auto, en, hi or another Whisper language code."
                  >
                    <input
                      value={draft.language}
                      onChange={(e) => set("language", e.target.value)}
                    />
                  </Field>
                </div>
                {toggle(
                  "captions",
                  "Burn in captions",
                  "Keep readable word-timed subtitles in the finished video.",
                )}
              </section>
              <section className="settings-section">
                <SectionTitle
                  title="Music that supports the story"
                  note="Tracks come from your category library."
                />
                {toggle(
                  "music",
                  "Background music",
                  "Match the editorial mood with a random category track.",
                )}
                <Field
                  label={`Music gain · ${Math.round(draft.music_gain * 100)}%`}
                  hint="Linear gain after normalization; speech ducking can lower it further."
                >
                  <div className="range-field">
                    <span>0%</span>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.01"
                      value={draft.music_gain}
                      onChange={(e) => set("music_gain", +e.target.value)}
                    />
                    <span>100%</span>
                  </div>
                </Field>
                {toggle(
                  "music_normalize",
                  "Normalize track loudness",
                  "Keep quieter and louder library tracks more consistent.",
                )}
                {toggle(
                  "music_ducking",
                  "Let dialogue lead",
                  "Lower the music automatically while someone is speaking.",
                )}
              </section>
            </>
          )}
          {tab === "ai" && (
            <>
              <section className="settings-section">
                <SectionTitle
                  title="Your editorial partner"
                  note="Switch providers without changing your editing workflow."
                />
                <div className="provider-grid">
                  {boot.providers.map((p) => (
                    <button
                      className={draft.ai_provider === p.id ? "selected" : ""}
                      key={p.id}
                      onClick={() => {
                        set("ai_provider", p.id);
                        set("ai_model", null);
                      }}
                    >
                      <span className="provider-monogram">
                        {p.id === "chatgpt_browser"
                          ? "C"
                          : p.id === "heuristic"
                            ? "H"
                            : p.id === "openai"
                              ? "O"
                              : p.id === "xai"
                                ? "X"
                                : "G"}
                      </span>
                      <div>
                        <strong>{providerName(p.id)}</strong>
                        <small>
                          {p.id === "chatgpt_browser"
                            ? "Your shared Chromium session"
                            : p.id === "heuristic"
                              ? "Local, basic ranking"
                              : p.configured
                                ? "API key configured"
                                : "API key needed"}
                        </small>
                      </div>
                      {draft.ai_provider === p.id ? (
                        <Check size={16} />
                      ) : (
                        <span className="radio-ring" />
                      )}
                    </button>
                  ))}
                </div>
                <div className="form-grid">
                  <Field
                    label="Model override"
                    hint="Leave blank to use the provider default. Browser mode uses your website session."
                  >
                    <input
                      value={draft.ai_model || ""}
                      placeholder={
                        boot.providers.find((p) => p.id === draft.ai_provider)
                          ?.model || "Provider default"
                      }
                      onChange={(e) => set("ai_model", e.target.value || null)}
                      disabled={["chatgpt_browser", "heuristic"].includes(
                        draft.ai_provider || "",
                      )}
                    />
                  </Field>
                  {select("clipping_mode", "Link clipping mode", [
                    ["audio_first", "Normal / stream clipping"],
                    ["gemini_browser", "Gemini browser · YouTube link"],
                  ])}
                </div>
                {toggle(
                  "gemini_verify_captions",
                  "Verify Gemini caption timing locally",
                  "Use CUDA transcription on selected video ranges before export.",
                )}
                <div className="info-note">
                  <Globe size={16} />
                  <span>
                    ChatGPT and Gemini reuse the original project Chromium
                    profile. Website limits still apply. There is no automatic
                    switch to a paid provider.
                  </span>
                </div>
              </section>
              <section className="settings-section">
                <SectionTitle
                  title="Look deeper. Or move faster."
                  note="Choose how much of a long source to examine."
                />
                <div className="form-grid">
                  {number(
                    "scan_minutes",
                    "Long-stream discovery · minutes",
                    6,
                    1440,
                    "Default 24 minutes. Partial scans can miss highlights.",
                  )}
                  {number(
                    "clips",
                    "Clips to discover",
                    1,
                    10,
                    "The engine can return fewer complete moments.",
                  )}
                </div>
                <FocusField
                  key={focusReset}
                  onValidityChange={setFocusInvalid}
                  value={draft.focus_times}
                  onChange={(v) => set("focus_times", v)}
                />
                <div className="budget-example">
                  <span>
                    {Math.min(100, (draft.scan_minutes / 1200) * 100).toFixed(
                      1,
                    )}
                    %
                  </span>
                  <p>
                    of a 20-hour stream with this budget.
                    <br />
                    Short sources up to {boot.system.long_source_minutes}{" "}
                    minutes are fully analyzed by default.
                  </p>
                </div>
              </section>
            </>
          )}
          {tab === "automation" && (
            <>
              <section className="settings-section">
                <SectionTitle
                  title="Production switches"
                  note="Pause a feature without losing its queue."
                />
                {toggle(
                  "f1_enabled",
                  "Video clipping",
                  "Discover and render moments from submitted sources.",
                )}
                {toggle(
                  "f2_enabled",
                  "Carousel production",
                  "Generate reference-led images and complete carousel stories.",
                )}
                {select("active_feature", "Default Telegram feature", [
                  ["f1", "Clips"],
                  ["f2", "Carousels"],
                  ["both", "Both features"],
                ])}
              </section>
              <section className="settings-section">
                <SectionTitle
                  title="From shortlist to published"
                  note="Choose where you want to stay in the loop."
                />
                {toggle(
                  "auto_render",
                  "Render shortlisted clips automatically",
                  "Skip the selection step for new clipping jobs.",
                )}
                {toggle(
                  "auto_publish",
                  "Auto-publish clips",
                  "First clip publishes when ready. Remaining clips wait two hours after the previous publication.",
                )}
                {toggle(
                  "f2_auto_publish",
                  "Auto-publish carousels",
                  "Publish QA-approved carousels; automatic posts keep the existing three-hour spacing.",
                )}
                <Field
                  label="Instagram account for clips"
                  hint="Matches an account key in your Connections configuration."
                >
                  <input
                    value={draft.instagram_account}
                    onChange={(e) => set("instagram_account", e.target.value)}
                  />
                </Field>
                {toggle(
                  "youtube_auto_publish",
                  "Auto-publish to YouTube Shorts",
                  "Automatically queue and upload verified clips directly to YouTube Shorts.",
                )}
                <Field
                  label="YouTube account for clips"
                  hint="Choose the default YouTube channel destination for generated clips."
                >
                  <input
                    value={draft.youtube_account || "main"}
                    placeholder="main"
                    onChange={(e) => set("youtube_account", e.target.value)}
                  />
                </Field>
                <div className="info-note">
                  <Eye size={16} />
                  <span>
                    With auto-publish off, finished assets wait in Publishing.
                    Disabling it also holds queued automatic posts for approval.
                  </span>
                </div>
              </section>
              <section className="settings-section">
                <SectionTitle
                  title="Active carousel niches"
                  note="Choose the themes your studio is allowed to produce."
                />
                {Object.entries(boot.niches).map(([key, label]) => (
                  <Switch
                    key={key}
                    label={label}
                    checked={draft.enabled_niches.includes(key)}
                    onChange={(on) =>
                      set(
                        "enabled_niches",
                        on
                          ? [...draft.enabled_niches, key]
                          : draft.enabled_niches.filter((k) => k !== key),
                      )
                    }
                  />
                ))}
                {select(
                  "selected_niche",
                  "Default niche",
                  Object.entries(boot.niches),
                )}
              </section>
            </>
          )}
          {tab === "prompts" && <AIPromptsManager />}
          {tab === "connections" && <ConnectionSettings />}
          {tab === "system" && <SystemSettings />}
          {!["connections", "system", "prompts"].includes(tab) && (
            <div className={`settings-savebar ${dirty ? "dirty" : ""}`}>
              <span>
                {dirty
                  ? "You have unsaved changes."
                  : "Your preferences are up to date."}
              </span>
              <div>
                <Button
                  variant="ghost"
                  disabled={!dirty && !focusInvalid}
                  onClick={() => {
                    setDraft(saved);
                    setFocusInvalid(false);
                    setFocusReset((n) => n + 1);
                  }}
                >
                  Discard changes
                </Button>
                <Button
                  variant="primary"
                  icon={Check}
                  disabled={!dirty || focusInvalid}
                  busy={busy}
                  onClick={() => void save()}
                >
                  Save changes
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function FocusField({
  value,
  onChange,
  onValidityChange,
}: {
  value: number[];
  onChange: (v: number[]) => void;
  onValidityChange: (invalid: boolean) => void;
}) {
  const [text, setText] = useState(value.join(" ")),
    [error, setError] = useState("");
  useEffect(() => () => onValidityChange(false), [onValidityChange]);
  return (
    <Field
      label="Focus timestamps"
      hint={
        error ||
        "Optional: 01:20:00 08:10:00, or seconds. Clear this before unrelated sources."
      }
    >
      <input
        value={text}
        aria-invalid={!!error}
        onChange={(e) => {
          setText(e.target.value);
          try {
            const parsed = e.target.value.trim()
              ? e.target.value
                  .trim()
                  .split(/[ ,]+/)
                  .map((t) => {
                    const pieces = t.split(":").map(Number);
                    if (
                      pieces.length > 3 ||
                      t.split(":").some((p) => !p.trim()) ||
                      pieces.some((n) => !Number.isFinite(n) || n < 0) ||
                      pieces.slice(1).some((n) => n >= 60)
                    )
                      throw Error();
                    return pieces.reduce((a, n) => a * 60 + n, 0);
                  })
              : [];
            onChange(parsed);
            setError("");
            onValidityChange(false);
          } catch {
            setError("Use valid HH:MM:SS timestamps or seconds.");
            onValidityChange(true);
          }
        }}
      />
    </Field>
  );
}

function ConnectionSettings() {
  const { boot, notify, refresh } = useStudio(),
    query = useQuery({
      queryKey: ["connections"],
      queryFn: () => api<Connections>("/connections"),
    });
  const [keys, setKeys] = useState<Record<string, string>>({}),
    [busy, setBusy] = useState(false),
    [account, setAccount] = useState<{
      key: string;
      ig_user_id: string;
      login: string;
    } | null>(null),
    [igToken, setIgToken] = useState(""),
    [host, setHost] = useState("");
  async function saveKeys() {
    setBusy(true);
    try {
      const body = Object.fromEntries(
        Object.entries(keys).filter(([, v]) => v.trim()),
      );
      if (!Object.keys(body).length) return;
      const result = await api<{ message: string }>("/system", "PUT", body);
      setKeys({});
      notify(result.message);
      refresh();
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  async function saveAccount() {
    if (!account) return;
    setBusy(true);
    try {
      await api(`/connections/${account.key}`, "PUT", {
        ig_user_id: account.ig_user_id,
        login: account.login,
        token: igToken || undefined,
        media_base_url: host || undefined,
      });
      setAccount(null);
      setIgToken("");
      setHost("");
      refresh();
      notify(
        "Connection saved locally. Restart the engine to apply changed credentials.",
      );
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  const ytQuery = useQuery({
    queryKey: ["youtube-connections"],
    queryFn: () => api<YouTubeConnections>("/youtube/connections"),
  });
  const [ytConfigModal, setYtConfigModal] = useState(false),
    [ytClientId, setYtClientId] = useState(""),
    [ytClientSecret, setYtClientSecret] = useState(""),
    [ytAccount, setYtAccount] = useState<YouTubeAccount | null>(null),
    [ytTags, setYtTags] = useState(""),
    [authBusy, setAuthBusy] = useState(false);

  async function saveYtConfig() {
    setBusy(true);
    try {
      await api("/youtube/config", "PUT", {
        client_id: ytClientId || undefined,
        client_secret: ytClientSecret || undefined,
      });
      setYtConfigModal(false);
      setYtClientId("");
      setYtClientSecret("");
      ytQuery.refetch();
      notify("Google OAuth API configuration saved.");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  async function saveYtAccount() {
    if (!ytAccount) return;
    setBusy(true);
    try {
      await api(`/youtube/accounts/${ytAccount.key}`, "PUT", {
        title: ytAccount.title,
        privacy: ytAccount.privacy,
        default_tags: ytTags,
        auto_publish: ytAccount.auto_publish,
      });
      setYtAccount(null);
      ytQuery.refetch();
      notify("YouTube channel destination saved.");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  async function deleteYtAccount(key: string) {
    if (!window.confirm(`Delete YouTube destination "${key}"?`)) return;
    setBusy(true);
    try {
      await api(`/youtube/accounts/${key}`, "DELETE");
      setYtAccount(null);
      ytQuery.refetch();
      notify(`YouTube destination "${key}" removed.`);
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  async function startYtAuth(accountKey: string) {
    setAuthBusy(true);
    try {
      const res = await api<{ auth_url: string; redirect_uri: string }>(
        `/youtube/auth-url?account=${encodeURIComponent(accountKey)}`,
      );
      const width = 600,
        height = 700;
      const left = window.screenX + (window.outerWidth - width) / 2;
      const top = window.screenY + (window.outerHeight - height) / 2;
      const popup = window.open(
        res.auth_url,
        "youtube_oauth",
        `width=${width},height=${height},left=${left},top=${top},status=0,menubar=0`,
      );
      const listener = (event: MessageEvent) => {
        if (event.data?.type === "YOUTUBE_AUTH_SUCCESS") {
          window.removeEventListener("message", listener);
          notify(`YouTube account "${accountKey}" connected successfully!`);
          ytQuery.refetch();
          setYtAccount(null);
        }
      };
      window.addEventListener("message", listener);
      const timer = setInterval(() => {
        if (!popup || popup.closed) {
          clearInterval(timer);
          window.removeEventListener("message", listener);
          ytQuery.refetch();
          setAuthBusy(false);
        }
      }, 1000);
    } catch (e) {
      notify((e as Error).message, true);
      setAuthBusy(false);
    }
  }

  return (
    <>
      {query.error && <ErrorBox error={query.error} />}
      <section className="settings-section">
        <SectionTitle
          title="AI connections"
          note="Keys stay on this computer and are never returned by the API."
        />
        {[
          ["OPENAI_API_KEY", "OpenAI", "openai"],
          ["XAI_API_KEY", "xAI Grok", "xai"],
          ["GEMINI_API_KEY", "Google Gemini", "gemini"],
        ].map(([key, label, id]) => (
          <Field
            key={key}
            label={label}
            hint={
              boot.providers.find((p) => p.id === id)?.configured
                ? "A key is configured. Enter a new one only to replace it."
                : "No API key configured."
            }
          >
            <input
              type="password"
              autoComplete="new-password"
              placeholder="Leave blank to keep the current key"
              value={keys[key] || ""}
              onChange={(e) => setKeys({ ...keys, [key]: e.target.value })}
            />
          </Field>
        ))}
        <Button
          icon={KeyRound}
          disabled={!Object.values(keys).some((v) => v.trim())}
          busy={busy}
          onClick={() => void saveKeys()}
        >
          Save API keys
        </Button>
        <div className="connection-line">
          <Globe size={18} />
          <div>
            <strong>Shared Chromium</strong>
            <small>
              ChatGPT text, Gemini images and Gemini link clipping use the
              existing project profile.
            </small>
          </div>
          <span className="connection-label">Browser</span>
        </div>
      </section>
      <section className="settings-section">
        <SectionTitle
          title="Instagram destinations"
          note="Professional account connections for clips and niche carousels."
        />
        {query.data?.accounts.map((a) => (
          <button
            className="account-row"
            key={a.key}
            onClick={() => {
              setAccount(a);
              setIgToken("");
            }}
          >
            <span className="account-avatar">
              {a.key.slice(0, 1).toUpperCase()}
            </span>
            <div>
              <strong>{a.key}</strong>
              <small>{a.ig_user_id || "Account ID not set"}</small>
            </div>
            <span
              className={
                a.token_configured && a.owner_allowed
                  ? "connection-label"
                  : "muted small"
              }
            >
              {a.token_configured && a.owner_allowed
                ? "Configured"
                : "Setup needed"}
            </span>
            <ChevronRight size={15} />
          </button>
        ))}
        {!query.data?.accounts.length && (
          <p className="muted">
            Add your first professional account to enable publishing.
          </p>
        )}
        <Button
          onClick={() =>
            setAccount({ key: "clips", ig_user_id: "", login: "instagram" })
          }
        >
          Configure an account
        </Button>
        <div className="connection-line">
          <Link2 size={18} />
          <div>
            <strong>Public media hosting</strong>
            <small>
              Instagram must be able to fetch your approved exports over HTTPS.
            </small>
          </div>
          <span className="connection-label">
            {query.data?.media_host_configured ? "Configured" : "Setup needed"}
          </span>
        </div>
      </section>
      <section className="settings-section">
        <SectionTitle
          title="YouTube destinations"
          note="Multiple channel auto-posting and manual publishing for YouTube Shorts & videos."
        />
        <div className="connection-line" style={{ marginBottom: "1rem" }}>
          <Youtube size={18} color="#ef4444" />
          <div style={{ flex: 1 }}>
            <strong>Google Cloud API Credentials</strong>
            <small style={{ display: "block" }}>
              {ytQuery.data?.configured
                ? "OAuth Client ID & Secret configured. Ready to authorize channels."
                : "Configure OAuth Client ID & Secret from Google Cloud Console to connect channels."}
            </small>
          </div>
          <Button
            variant="ghost"
            onClick={() => {
              setYtClientId(ytQuery.data?.client_id || "");
              setYtConfigModal(true);
            }}
          >
            {ytQuery.data?.configured ? "Edit Credentials" : "Setup Google API"}
          </Button>
          <span
            className={
              ytQuery.data?.configured ? "connection-label" : "muted small"
            }
          >
            {ytQuery.data?.configured ? "Configured" : "Setup needed"}
          </span>
        </div>

        {ytQuery.data?.accounts.map((a) => (
          <button
            className="account-row"
            key={a.key}
            onClick={() => {
              setYtAccount(a);
              setYtTags(a.default_tags.join(", "));
            }}
          >
            <span
              className="account-avatar"
              style={{
                background: "rgba(239, 68, 68, 0.15)",
                color: "#ef4444",
                overflow: "hidden",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {a.thumbnail ? (
                <img
                  src={a.thumbnail}
                  alt=""
                  style={{ width: "100%", height: "100%", objectFit: "cover" }}
                />
              ) : (
                <Youtube size={16} />
              )}
            </span>
            <div style={{ flex: 1, textAlign: "left" }}>
              <strong>{a.title || a.key}</strong>
              <small style={{ display: "block" }}>
                {a.channel_id
                  ? `Channel ID: ${a.channel_id} · Key: ${a.key}`
                  : `Key: ${a.key} · Not connected yet`}
              </small>
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                marginRight: "8px",
              }}
            >
              <span
                className="muted small"
                style={{ textTransform: "capitalize" }}
              >
                {a.privacy}
              </span>
              <span
                className={a.authorized ? "connection-label" : "muted small"}
              >
                {a.authorized ? "Connected" : "Needs Auth"}
              </span>
            </div>
            <ChevronRight size={15} />
          </button>
        ))}

        {!ytQuery.data?.accounts.length && (
          <p className="muted">
            Add a YouTube channel destination to start auto-posting or manual
            publishing.
          </p>
        )}

        <Button
          onClick={() => {
            const nextIdx = (ytQuery.data?.accounts.length || 0) + 1;
            setYtAccount({
              key: `channel_${nextIdx}`,
              title: `Channel ${nextIdx}`,
              channel_id: "",
              privacy: "public",
              default_tags: ["shorts", "clips"],
              thumbnail: "",
              auto_publish: false,
              owner_allowed: true,
              authorized: false,
            });
            setYtTags("shorts, clips");
          }}
        >
          Add YouTube channel
        </Button>
        <div className="connection-line" style={{ marginTop: "1rem" }}>
          <ShieldCheck size={18} />
          <div>
            <strong>Direct Local Upload</strong>
            <small>
              Unlike Instagram, YouTube Shorts upload directly from your local
              disk via official API. No public HTTPS reverse proxy needed!
            </small>
          </div>
          <span className="connection-label">Supported</span>
        </div>
      </section>
      <section className="settings-section">
        <SectionTitle
          title="Telegram"
          note="Your existing bot remains a second way into the same studio."
        />
        <div className="connection-line">
          <MonitorPlay size={18} />
          <div>
            <strong>Telegram bot</strong>
            <small>
              {query.data?.telegram_configured
                ? "Token configured locally. Keep the bot running for Telegram delivery."
                : "Add a Telegram token in your local .env to use the bot."}
            </small>
          </div>
          <span className="connection-label">
            {query.data?.telegram_configured ? "Configured" : "Optional"}
          </span>
        </div>
      </section>
      <Modal
        open={!!account}
        onOpenChange={(v) => {
          if (!v) setAccount(null);
        }}
        title="Connect an Instagram destination"
        description="Save the account mapping locally. Tokens are write-only."
      >
        {account && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void saveAccount();
            }}
          >
            <div className="form-grid">
              <Field label="Account key">
                <input
                  required
                  pattern="[a-z0-9_]+"
                  value={account.key}
                  onChange={(e) =>
                    setAccount({ ...account, key: e.target.value })
                  }
                />
              </Field>
              <Field label="Professional account ID">
                <input
                  required
                  pattern="[0-9]+"
                  value={account.ig_user_id}
                  onChange={(e) =>
                    setAccount({ ...account, ig_user_id: e.target.value })
                  }
                />
              </Field>
            </div>
            <Field label="Login flow">
              <select
                value={account.login}
                onChange={(e) =>
                  setAccount({ ...account, login: e.target.value })
                }
              >
                <option value="instagram">Instagram Login</option>
                <option value="facebook">Facebook Login</option>
              </select>
            </Field>
            <Field
              label="Access token"
              hint="Leave blank to preserve the existing token."
            >
              <input
                type="password"
                autoComplete="new-password"
                value={igToken}
                onChange={(e) => setIgToken(e.target.value)}
              />
            </Field>
            <Field
              label="Public media base URL"
              hint="Optional replacement. Must point to your existing HTTPS media hosting."
            >
              <input
                type="url"
                placeholder="https://media.example.com/cliper"
                value={host}
                onChange={(e) => setHost(e.target.value)}
              />
            </Field>
            <div className="modal-footer">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setAccount(null)}
              >
                Cancel
              </Button>
              <Button variant="primary" icon={Check} busy={busy}>
                Save connection
              </Button>
            </div>
          </form>
        )}
      </Modal>

      <Modal
        open={ytConfigModal}
        onOpenChange={(v) => {
          if (!v) setYtConfigModal(false);
        }}
        title="Google Cloud OAuth API Credentials"
        description="Configure your Google OAuth Client ID and Secret to enable YouTube publishing."
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void saveYtConfig();
          }}
        >
          <Field
            label="OAuth Client ID"
            hint="Ends with .apps.googleusercontent.com"
          >
            <input
              required
              placeholder="e.g. 123456789-abcdef.apps.googleusercontent.com"
              value={ytClientId}
              onChange={(e) => setYtClientId(e.target.value)}
            />
          </Field>
          <Field
            label="OAuth Client Secret"
            hint="Leave blank to keep existing secret if already configured"
          >
            <input
              type="password"
              placeholder="GOCSPX-..."
              value={ytClientSecret}
              onChange={(e) => setYtClientSecret(e.target.value)}
            />
          </Field>
          <div
            className="info-note"
            style={{ fontSize: "12px", lineHeight: "1.5" }}
          >
            <Sparkles size={16} />
            <span>
              <strong>Quick 2-minute Setup:</strong> In Google Cloud Console,
              enable <strong>YouTube Data API v3</strong>, create an{" "}
              <strong>OAuth client ID (Desktop app)</strong>, or select Web
              Application and add redirect URI:{" "}
              <code style={{ color: "#38bdf8" }}>
                http://localhost:8788/api/youtube/callback
              </code>
              .
            </span>
          </div>
          <div className="modal-footer">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setYtConfigModal(false)}
            >
              Cancel
            </Button>
            <Button variant="primary" icon={Check} busy={busy}>
              Save Credentials
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        open={!!ytAccount}
        onOpenChange={(v) => {
          if (!v) setYtAccount(null);
        }}
        title={
          ytAccount
            ? ytAccount.authorized
              ? `Channel: ${ytAccount.title}`
              : `Setup Channel: ${ytAccount.key}`
            : "YouTube Channel"
        }
        description="Configure channel properties, default tags, privacy, and Google authorization."
      >
        {ytAccount && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void saveYtAccount();
            }}
          >
            <div className="form-grid">
              <Field
                label="Account key"
                hint="Internal identifier (e.g. main, gaming, shorts)"
              >
                <input
                  required
                  pattern="[a-z0-9_-]+"
                  value={ytAccount.key}
                  disabled={ytAccount.authorized}
                  onChange={(e) =>
                    setYtAccount({ ...ytAccount, key: e.target.value })
                  }
                />
              </Field>
              <Field label="Channel Title">
                <input
                  required
                  value={ytAccount.title}
                  onChange={(e) =>
                    setYtAccount({ ...ytAccount, title: e.target.value })
                  }
                />
              </Field>
            </div>
            <div className="form-grid">
              <Field label="Default Privacy">
                <select
                  value={ytAccount.privacy}
                  onChange={(e) =>
                    setYtAccount({
                      ...ytAccount,
                      privacy: e.target.value as
                        "public" | "unlisted" | "private",
                    })
                  }
                >
                  <option value="public">Public</option>
                  <option value="unlisted">Unlisted</option>
                  <option value="private">Private</option>
                </select>
              </Field>
            </div>
            <Switch
              label="Auto-publish clips to this channel"
              description="Automatically queue and upload verified clips to this YouTube destination."
              checked={ytAccount.auto_publish}
              onChange={(checked: boolean) =>
                setYtAccount({ ...ytAccount, auto_publish: checked })
              }
            />
            <Field
              label="Default Tags"
              hint="Comma-separated tags for Shorts (e.g. shorts, clips, viral)"
            >
              <input
                value={ytTags}
                placeholder="shorts, viral, gaming"
                onChange={(e) => setYtTags(e.target.value)}
              />
            </Field>

            <div
              style={{
                marginTop: "1.25rem",
                padding: "1rem",
                background: "rgba(255, 255, 255, 0.04)",
                borderRadius: "8px",
                border: "1px solid rgba(255, 255, 255, 0.08)",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: "0.5rem",
                }}
              >
                <strong>Channel Authorization</strong>
                <span
                  className={
                    ytAccount.authorized ? "connection-label" : "muted small"
                  }
                >
                  {ytAccount.authorized ? "Connected" : "Not Authorized"}
                </span>
              </div>
              {ytAccount.authorized ? (
                <div>
                  <p className="small muted" style={{ margin: "4px 0 12px" }}>
                    Connected as <strong>{ytAccount.title}</strong>{" "}
                    {ytAccount.channel_id && `(ID: ${ytAccount.channel_id})`}.
                  </p>
                  <Button
                    type="button"
                    variant="ghost"
                    icon={Youtube}
                    busy={authBusy}
                    onClick={() => void startYtAuth(ytAccount.key)}
                  >
                    Re-authenticate Channel
                  </Button>
                </div>
              ) : (
                <div>
                  <p className="small muted" style={{ margin: "4px 0 12px" }}>
                    Click below to open Google's authorization screen in a popup
                    window and link your YouTube channel.
                  </p>
                  <Button
                    type="button"
                    variant="primary"
                    icon={Youtube}
                    busy={authBusy}
                    onClick={() => void startYtAuth(ytAccount.key)}
                    style={{ background: "#ef4444" }}
                  >
                    Authorize with Google / YouTube
                  </Button>
                </div>
              )}
            </div>

            <div className="modal-footer" style={{ marginTop: "1.5rem" }}>
              <Button
                type="button"
                variant="danger"
                icon={Trash2}
                onClick={() => void deleteYtAccount(ytAccount.key)}
              >
                Delete
              </Button>
              <div style={{ flex: 1 }} />
              <Button
                type="button"
                variant="ghost"
                onClick={() => setYtAccount(null)}
              >
                Cancel
              </Button>
              <Button variant="primary" icon={Check} busy={busy}>
                Save Channel
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </>
  );
}

function SystemSettings() {
  const { boot, refresh, notify } = useStudio(),
    query = useQuery({
      queryKey: ["status"],
      queryFn: () => api<System>("/status"),
      refetchInterval: 5000,
    }),
    status = query.data || boot.system;
  const [draft, setDraft] = useState<Record<string, string>>({
      WHISPER_MODEL: status.whisper_model,
      WHISPER_DEVICE: status.device,
      WHISPER_COMPUTE_TYPE: status.compute_type,
      VIDEO_ENCODER: status.encoder,
      MAX_SOURCE_MINUTES: String(status.max_source_minutes),
      MAX_DOWNLOAD_MB: String(status.max_download_mb),
      MAX_ACTIVE_JOBS: String(status.max_active_jobs),
      LONG_SOURCE_MINUTES: String(status.long_source_minutes),
      SCAN_DOWNLOAD_WORKERS: String(status.scan_download_workers),
      RETENTION_DAYS: String(status.retention_days),
    }),
    [busy, setBusy] = useState(false),
    [confirm, setConfirm] = useState(false);
  async function engine(action: string) {
    setBusy(true);
    try {
      await api(`/engine/${action}`, "POST");
      refresh();
      notify(
        action === "stop"
          ? "Web engine stopped. Queued work is retained."
          : "Engine connected.",
      );
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
      setConfirm(false);
    }
  }
  async function save() {
    setBusy(true);
    try {
      const result = await api<{ message: string }>("/system", "PUT", draft);
      notify(result.message);
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  const number = (key: string, label: string, min: number, max: number) => (
    <Field label={label}>
      <input
        type="number"
        min={min}
        max={max}
        value={draft[key]}
        onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
      />
    </Field>
  );
  return (
    <>
      <section className="settings-section">
        <SectionTitle
          title="Your local engine"
          note="One engine lock prevents competing workers."
        />
        <div className="system-status">
          <span
            className={`status-dot ${status.engine.mode === "stopped" ? "off" : ""}`}
          />
          <div>
            <strong>
              {status.engine.mode === "local"
                ? "Web engine is running"
                : status.engine.mode === "attached"
                  ? "Connected to the existing worker"
                  : "Web engine is stopped"}
            </strong>
            <p>
              {status.engine.mode === "local"
                ? "Processes web-origin clips, carousels and publications."
                : status.engine.mode === "attached"
                  ? "Telegram owns the engine. Restart an older bot to load web delivery support."
                  : "Start the engine to process queued web projects."}
            </p>
          </div>
          <Button
            busy={busy}
            icon={status.engine.mode === "stopped" ? Play : Pause}
            onClick={() =>
              status.engine.mode === "stopped"
                ? void engine("start")
                : setConfirm(true)
            }
          >
            {status.engine.mode === "stopped" ? "Start" : "Stop"}
          </Button>
        </div>
        <div className="system-facts">
          <div>
            <Cpu size={18} />
            <span>Transcription</span>
            <strong>
              {status.device.toUpperCase()} · {status.whisper_model}
            </strong>
          </div>
          <div>
            <MonitorPlay size={18} />
            <span>Video encoding</span>
            <strong>{status.encoder}</strong>
          </div>
          <div>
            <Eye size={18} />
            <span>Face detector</span>
            <strong>
              {status.face_model ? "YuNet installed" : "Haar fallback"}
            </strong>
          </div>
        </div>
        <div className="disk-status">
          <div>
            <strong>{status.free_gb} GB free</strong>
            <span>{status.total_gb} GB volume</span>
          </div>
          <i>
            <b
              style={{
                width: `${(1 - status.free_gb / status.total_gb) * 100}%`,
              }}
            />
          </i>
        </div>
      </section>
      <section className="settings-section">
        <SectionTitle
          title="Performance profile"
          note="Saved to .env. Restart the web server and bot to apply changes."
        />
        <div className="form-grid">
          <Field label="Whisper model">
            <input
              value={draft.WHISPER_MODEL}
              onChange={(e) =>
                setDraft({ ...draft, WHISPER_MODEL: e.target.value })
              }
            />
          </Field>
          <Field label="Transcription device">
            <select
              value={draft.WHISPER_DEVICE}
              onChange={(e) =>
                setDraft({ ...draft, WHISPER_DEVICE: e.target.value })
              }
            >
              <option value="cuda">CUDA · NVIDIA GPU</option>
              <option value="cpu">CPU</option>
            </select>
          </Field>
          <Field label="Compute precision">
            <select
              value={draft.WHISPER_COMPUTE_TYPE}
              onChange={(e) =>
                setDraft({ ...draft, WHISPER_COMPUTE_TYPE: e.target.value })
              }
            >
              {[
                "int8_float16",
                "float16",
                "int8",
                "float32",
                "int8_float32",
              ].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </Field>
          <Field label="Video encoder">
            <select
              value={draft.VIDEO_ENCODER}
              onChange={(e) =>
                setDraft({ ...draft, VIDEO_ENCODER: e.target.value })
              }
            >
              <option value="h264_nvenc">NVIDIA NVENC</option>
              <option value="libx264">CPU · libx264</option>
            </select>
          </Field>
          {number("SCAN_DOWNLOAD_WORKERS", "Concurrent scan downloads", 1, 3)}
          {number("MAX_ACTIVE_JOBS", "Maximum active jobs", 1, 50)}
        </div>
      </section>
      <section className="settings-section">
        <SectionTitle
          title="Source & storage limits"
          note="Set resource boundaries that suit this machine."
        />
        <div className="form-grid">
          {number("MAX_SOURCE_MINUTES", "Maximum source · minutes", 1, 1440)}
          {number(
            "LONG_SOURCE_MINUTES",
            "Long-source threshold · minutes",
            1,
            1440,
          )}
          {number("MAX_DOWNLOAD_MB", "Download limit · MB", 10, 100000)}
          {number("RETENTION_DAYS", "Finished-job retention · days", 1, 3650)}
        </div>
        <div className="info-note">
          <Database size={16} />
          <span>
            Original CLI files are never removed by retention. Pending
            publications protect their source jobs from cleanup.
          </span>
        </div>
      </section>
      <div className="settings-savebar">
        <span>Engine changes require a restart.</span>
        <Button
          variant="primary"
          busy={busy}
          icon={Save}
          onClick={() => void save()}
        >
          Save system settings
        </Button>
      </div>
      <Modal
        open={confirm}
        onOpenChange={setConfirm}
        title="Stop the web engine?"
        description="Active web processing will stop safely. Saved progress and queued work remain available."
      >
        <div className="modal-footer">
          <Button onClick={() => setConfirm(false)}>Keep running</Button>
          <Button
            variant="danger"
            busy={busy}
            onClick={() => void engine("stop")}
          >
            Stop engine
          </Button>
        </div>
      </Modal>
    </>
  );
}

function AIPromptsManager() {
  const { notify } = useStudio();
  const [activeCategory, setActiveCategory] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<Record<string, string>>({});
  const [diffView, setDiffView] = useState<Record<string, boolean>>({});
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [resetModal, setResetModal] = useState<string | null>(null);
  const [resetAllModal, setResetAllModal] = useState(false);

  const promptsQuery = useQuery({
    queryKey: ["prompts"],
    queryFn: () => api<PromptInfo[]>("/prompts"),
  });

  const prompts = promptsQuery.data || [];

  const categories = [
    { key: "all", label: "All Prompts" },
    { key: "carousels", label: "Instagram Carousels (F2)" },
    { key: "clips", label: "Clips Studio (F1)" },
    { key: "speed", label: "Speed Studio" },
    { key: "x", label: "X Studio" },
    { key: "display", label: "Captions & Display" },
  ];

  const filtered = prompts.filter((p) => {
    if (activeCategory !== "all" && p.category !== activeCategory) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      return (
        p.title.toLowerCase().includes(q) ||
        p.description.toLowerCase().includes(q) ||
        p.key.toLowerCase().includes(q) ||
        (editing[p.key] ?? p.value).toLowerCase().includes(q)
      );
    }
    return true;
  });

  async function handleSave(key: string) {
    const val = editing[key] ?? prompts.find((p) => p.key === key)?.value;
    if (!val || !val.trim()) {
      notify("Prompt content cannot be empty.", true);
      return;
    }
    setBusyKey(key);
    try {
      await api(`/prompts/${key}`, "PUT", { value: val.trim() });
      await promptsQuery.refetch();
      setEditing((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
      notify("Prompt updated and saved for all new generations.");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusyKey(null);
    }
  }

  async function handleReset(key: string) {
    setBusyKey(key);
    try {
      await api(`/prompts/${key}/reset`, "POST");
      await promptsQuery.refetch();
      setEditing((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
      setResetModal(null);
      notify("Prompt reset to factory default.");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusyKey(null);
    }
  }

  async function handleResetAll() {
    setBusyKey("all");
    try {
      await api("/prompts/reset", "POST");
      await promptsQuery.refetch();
      setEditing({});
      setResetAllModal(false);
      notify(
        "All prompts across all features have been reset to factory defaults.",
      );
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusyKey(null);
    }
  }

  function insertVariable(key: string, variable: string) {
    const current =
      editing[key] ?? prompts.find((p) => p.key === key)?.value ?? "";
    setEditing((prev) => ({
      ...prev,
      [key]: current + " " + variable,
    }));
  }

  return (
    <div className="prompts-manager">
      <section className="settings-section">
        <div className="prompts-header">
          <div>
            <SectionTitle
              title="AI Prompt Engineering & Control"
              note="Review and edit the exact instructions given to AI across every feature. Prompts update live for all new generation runs."
            />
          </div>
          <div className="prompts-header-actions">
            <Button
              variant="ghost"
              icon={RotateCcw}
              onClick={() => setResetAllModal(true)}
              disabled={!prompts.some((p) => p.is_custom)}
            >
              Reset all to defaults
            </Button>
          </div>
        </div>

        <div className="prompts-filters">
          <div className="category-pills">
            {categories.map((c) => {
              const count =
                c.key === "all"
                  ? prompts.length
                  : prompts.filter((p) => p.category === c.key).length;
              return (
                <button
                  type="button"
                  key={c.key}
                  className={activeCategory === c.key ? "selected" : ""}
                  onClick={() => setActiveCategory(c.key)}
                >
                  {c.label}
                  <span className="count-pill">{count}</span>
                </button>
              );
            })}
          </div>
          <div className="prompts-search-wrapper">
            <Search size={15} />
            <input
              type="text"
              placeholder="Search prompts by keyword, description or variable..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            {search && (
              <button
                type="button"
                className="clear-search"
                onClick={() => setSearch("")}
              >
                <X size={13} />
              </button>
            )}
          </div>
        </div>

        {promptsQuery.isLoading ? (
          <Loading />
        ) : filtered.length === 0 ? (
          <Empty
            icon={MessageSquareQuote}
            title="No matching prompts found"
            description="Try a different search term or category filter."
          />
        ) : (
          <div className="prompts-list">
            {filtered.map((p) => {
              const currentVal = editing[p.key] ?? p.value;
              const isDirty = currentVal !== p.value;
              const wordCount = currentVal
                .trim()
                .split(/\s+/)
                .filter(Boolean).length;
              const showDiff = !!diffView[p.key];

              return (
                <div
                  key={p.key}
                  className={`prompt-card ${p.is_custom ? "is-custom" : ""}`}
                >
                  <div className="prompt-card-header">
                    <div className="prompt-meta">
                      <div className="prompt-title-row">
                        <h3>{p.title}</h3>
                        <span
                          className={`status-pill ${
                            p.is_custom ? "custom" : "default"
                          }`}
                        >
                          {p.is_custom ? "Customized" : "Factory Default"}
                        </span>
                        {isDirty && (
                          <span className="status-pill unsaved">
                            Unsaved Edits
                          </span>
                        )}
                      </div>
                      <p className="prompt-description">{p.description}</p>
                    </div>
                    <div className="prompt-card-actions">
                      <Button
                        variant="ghost"
                        icon={showDiff ? EyeOff : Eye}
                        onClick={() =>
                          setDiffView((prev) => ({
                            ...prev,
                            [p.key]: !prev[p.key],
                          }))
                        }
                      >
                        {showDiff ? "Hide Default" : "Compare Default"}
                      </Button>
                      {p.is_custom && (
                        <Button
                          variant="ghost"
                          icon={RotateCcw}
                          onClick={() => setResetModal(p.key)}
                          disabled={busyKey === p.key}
                        >
                          Reset
                        </Button>
                      )}
                      <Button
                        variant="primary"
                        icon={Save}
                        disabled={!isDirty || busyKey === p.key}
                        busy={busyKey === p.key}
                        onClick={() => void handleSave(p.key)}
                      >
                        Save prompt
                      </Button>
                    </div>
                  </div>

                  {p.variables && p.variables.length > 0 && (
                    <div className="prompt-variables">
                      <span className="var-label">Available Variables:</span>
                      {p.variables.map((v) => (
                        <button
                          key={v}
                          type="button"
                          className="var-tag"
                          title="Click to insert variable into prompt"
                          onClick={() => insertVariable(p.key, v)}
                        >
                          <code>{v}</code>
                        </button>
                      ))}
                    </div>
                  )}

                  <div className="prompt-editor-area">
                    <textarea
                      rows={Math.min(
                        16,
                        Math.max(7, currentVal.split("\n").length + 2),
                      )}
                      value={currentVal}
                      onChange={(e) => {
                        const val = e.target.value;
                        setEditing((prev) => ({ ...prev, [p.key]: val }));
                      }}
                      className="prompt-textarea"
                    />
                    <div className="prompt-editor-footer">
                      <span className="counter-stats">
                        {currentVal.length} characters · {wordCount} words
                      </span>
                      {isDirty && (
                        <button
                          type="button"
                          className="link-button"
                          onClick={() => {
                            setEditing((prev) => {
                              const next = { ...prev };
                              delete next[p.key];
                              return next;
                            });
                          }}
                        >
                          Discard changes
                        </button>
                      )}
                    </div>
                  </div>

                  {showDiff && (
                    <div className="prompt-diff-box">
                      <div className="diff-header">
                        <strong>Factory Default Version</strong>
                        <button
                          type="button"
                          className="button ghost small"
                          onClick={() => {
                            setEditing((prev) => ({
                              ...prev,
                              [p.key]: p.default,
                            }));
                          }}
                        >
                          <Copy size={12} />
                          Copy default to editor
                        </button>
                      </div>
                      <pre className="diff-pre">{p.default}</pre>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Reset Confirmation Modal */}
      <Modal
        open={!!resetModal}
        onOpenChange={(v) => {
          if (!v) setResetModal(null);
        }}
        title="Reset prompt to factory default?"
        description="Any custom modifications to this prompt will be discarded, and the original default will be restored."
      >
        <div className="modal-footer">
          <Button onClick={() => setResetModal(null)}>Cancel</Button>
          <Button
            variant="danger"
            busy={!!busyKey}
            onClick={() => {
              if (resetModal) void handleReset(resetModal);
            }}
          >
            Reset to default
          </Button>
        </div>
      </Modal>

      {/* Reset All Confirmation Modal */}
      <Modal
        open={resetAllModal}
        onOpenChange={setResetAllModal}
        title="Reset ALL prompts to factory defaults?"
        description="This will restore all prompts across Carousels, Clips Studio, Speed Studio, X Studio and Display Text back to their original system defaults."
      >
        <div className="modal-footer">
          <Button onClick={() => setResetAllModal(false)}>Cancel</Button>
          <Button
            variant="danger"
            busy={busyKey === "all"}
            onClick={() => void handleResetAll()}
          >
            Reset all prompts
          </Button>
        </div>
      </Modal>
    </div>
  );
}
