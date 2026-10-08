import { useEffect, useState } from "react";
import {
  NavLink,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  AudioLines,
  Check,
  ChevronDown,
  Command,
  Film,
  FolderOpen,
  HelpCircle,
  Images,
  LayoutGrid,
  Link2,
  LockKeyhole,
  Menu,
  Plus,
  Search,
  Send,
  Settings2,
  Upload,
  X,
  Zap,
} from "lucide-react";
import { api, setCsrf, upload, providerName } from "./api";
import type { Bootstrap, Job, System } from "./types";
import {
  Button,
  Field,
  IconButton,
  Modal,
  StudioContext,
  useStudio,
} from "./ui";
import Speed from "./Speed";
import ProjectRules, { emptyRules } from "./ProjectRules";
import XStudio from "./XStudio";
import Studio from "./Studio";
import Project from "./Project";
import Settings from "./Settings";
import { Carousels, MusicLibrary, Publishing } from "./Workspaces";

const navigation = [
  { path: "/", label: "Studio", icon: LayoutGrid },
  { path: "/speed", label: "Speed Studio", icon: Zap },
  { path: "/x", label: "X Studio", icon: Send },
  { path: "/carousels", label: "Carousels", icon: Images },
  { path: "/publishing", label: "Publishing", icon: Send },
  { path: "/music", label: "Music library", icon: AudioLines },
  { path: "/settings", label: "Settings", icon: Settings2 },
];
export function Brand() {
  return (
    <div className="brand">
      <span className="brand-mark">
        <i />
        <i />
        <i />
      </span>
      <span>
        cliper<span className="brand-period">.</span>
      </span>
    </div>
  );
}

export default function App() {
  const client = useQueryClient(),
    navigate = useNavigate(),
    location = useLocation();
  const [authError, setAuthError] = useState(""),
    [key, setKey] = useState(""),
    [logging, setLogging] = useState(false);
  const boot = useQuery({
    queryKey: ["bootstrap"],
    queryFn: async () => {
      const result = await api<Bootstrap>("/bootstrap");
      setCsrf(result.csrf);
      return result;
    },
    retry: false,
  });
  const [toast, setToast] = useState<{
      message: string;
      error: boolean;
    } | null>(null),
    [newOpen, setNewOpen] = useState(false),
    [initialUrl, setInitialUrl] = useState(""),
    [searchOpen, setSearchOpen] = useState(false),
    [help, setHelp] = useState(false),
    [mobile, setMobile] = useState(false);
  const notify = (message: string, error = false) =>
    setToast({ message, error });
  const refresh = () => {
    void client.invalidateQueries();
  };
  const create = (url = "") => {
    setInitialUrl(url);
    setNewOpen(true);
  };
  async function lockStudio() {
    try {
      await api("/session", "DELETE");
      client.clear();
      window.location.assign("/");
    } catch (e) {
      notify((e as Error).message, true);
    }
  }
  const login = async (value: string) => {
    setLogging(true);
    setAuthError("");
    try {
      const result = await api<{ csrf: string }>("/session", "POST", {
        key: value,
      });
      setCsrf(result.csrf);
      setKey("");
      await boot.refetch();
    } catch (e) {
      setAuthError((e as Error).message);
    } finally {
      setLogging(false);
    }
  };
  useEffect(() => {
    const hash = new URLSearchParams(window.location.hash.slice(1));
    const token = hash.get("key");
    if (token) {
      window.history.replaceState(null, "", window.location.pathname);
      void login(token);
    }
  }, []);
  useEffect(() => {
    const expired = () => {
      client.removeQueries({ queryKey: ["bootstrap"] });
      void boot.refetch();
    };
    window.addEventListener("session-expired", expired);
    return () => window.removeEventListener("session-expired", expired);
  }, []);
  useEffect(() => {
    if (!toast) return;
    const timeout = setTimeout(
      () => setToast(null),
      toast.error ? 10000 : 5000,
    );
    return () => clearTimeout(timeout);
  }, [toast]);
  useEffect(() => {
    setMobile(false);
  }, [location.pathname]);
  useEffect(() => {
    const shortcut = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen((v) => !v);
      }
      if (
        e.key === "?" &&
        !(
          e.target instanceof HTMLInputElement ||
          e.target instanceof HTMLTextAreaElement
        )
      ) {
        setHelp(true);
      }
      if (document.querySelector("[role=dialog]")) return;
      if (
        e.key === "n" &&
        !(
          e.target instanceof HTMLInputElement ||
          e.target instanceof HTMLTextAreaElement ||
          e.target instanceof HTMLSelectElement
        ) &&
        !e.ctrlKey &&
        !e.metaKey
      ) {
        setNewOpen(true);
      }
    };
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, []);
  const system = useQuery({
    queryKey: ["status"],
    queryFn: () => api<System>("/status"),
    enabled: !!boot.data,
    refetchInterval: 5000,
  });
  if (!boot.data)
    return (
      <div className="login-page">
        <Brand />
        <div className="login-card">
          <div className="login-icon">
            <LockKeyhole size={26} strokeWidth={1.3} />
          </div>
          <span className="eyebrow">YOUR PRIVATE PRODUCTION WORKSPACE</span>
          <h1>Welcome to your studio.</h1>
          <p>
            Great content starts with a little clarity.
            <br />
            Connect to your local CLIPER engine to get started.
          </p>
          {boot.isPending || logging ? (
            <div className="connecting">Connecting to your workspace…</div>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void login(key);
              }}
            >
              <Field
                label="Local access key"
                hint="Launch with scripts/start-web.ps1 to sign in automatically. Your key is also saved in data/web/access-key."
              >
                <input
                  autoComplete="off"
                  type="password"
                  value={key}
                  onChange={(e) => setKey(e.target.value)}
                  placeholder="Enter your studio access key"
                  required
                />
              </Field>
              {authError && (
                <p className="inline-error" role="alert">
                  {authError}
                </p>
              )}
              <Button variant="primary full" busy={logging} icon={ArrowRight}>
                Open studio
              </Button>
            </form>
          )}
          <small>
            <LockKeyhole size={12} /> Runs privately on this computer
          </small>
        </div>
        <p className="login-footer">
          CLIPER STUDIO <span>Ideas into impact.</span>
        </p>
      </div>
    );
  const active = navigation.find((n) =>
    n.path === "/"
      ? location.pathname === "/"
      : location.pathname.startsWith(n.path),
  );
  const status = system.data || boot.data.system;
  return (
    <StudioContext.Provider
      value={{ boot: boot.data, refresh, notify, create }}
    >
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <div className="app-shell">
        {mobile && (
          <button
            className="nav-scrim"
            aria-label="Close navigation"
            onClick={() => setMobile(false)}
          />
        )}
        <aside className={`sidebar ${mobile ? "mobile-open" : ""}`}>
          <NavLink to="/" aria-label="CLIPER Studio home">
            <Brand />
          </NavLink>
          <div className="workspace-switch">
            <span className="workspace-avatar">S</span>
            <div>
              <strong>My workspace</strong>
              <small>Personal studio</small>
            </div>
            <ChevronDown size={14} />
          </div>
          <Button
            variant="primary new-project"
            icon={Plus}
            onClick={() => create()}
          >
            New project <kbd>N</kbd>
          </Button>
          <span className="nav-label">WORKSPACE</span>
          <nav aria-label="Main navigation">
            {navigation.map(({ path, label, icon: Icon }) => (
              <NavLink
                key={path}
                end={path === "/"}
                to={path}
                className={({ isActive }) =>
                  isActive ? "nav-item selected" : "nav-item"
                }
              >
                <Icon size={18} strokeWidth={1.6} />
                <span>{label}</span>
                {path === "/carousels" && <small>F2</small>}
              </NavLink>
            ))}
          </nav>
          <div className="sidebar-bottom">
            <div className="engine-card">
              <span
                className={`status-dot ${status.engine.mode === "stopped" ? "off" : ""}`}
              />
              <strong>
                {status.engine.mode === "attached"
                  ? "Engine connected"
                  : status.engine.mode === "local"
                    ? "Engine running"
                    : "Engine paused"}
              </strong>
              <p>
                {status.device === "cuda"
                  ? "CUDA transcription"
                  : "Local transcription"}{" "}
                ·{" "}
                {status.encoder === "h264_nvenc"
                  ? "NVENC export"
                  : "CPU export"}
              </p>
              <button onClick={() => navigate("/settings?tab=system")}>
                View system <ArrowRight size={13} />
              </button>
            </div>
            <button
              className="nav-item help-button"
              onClick={() => setHelp(true)}
            >
              <HelpCircle size={18} />
              <span>Help & shortcuts</span>
              <kbd>?</kbd>
            </button>
            <button
              className="profile"
              title="Lock Studio"
              onClick={() => void lockStudio()}
            >
              <span className="profile-avatar">L</span>
              <div>
                <strong>Local workspace</strong>
                <small>Private by default</small>
              </div>
              <LockKeyhole size={14} />
            </button>
          </div>
        </aside>
        <div className="main-shell">
          <header className="topbar">
            <div className="breadcrumb">
              <IconButton
                icon={Menu}
                label="Open navigation"
                className="mobile-menu"
                onClick={() => setMobile(true)}
              />
              <span>Workspace</span>
              <span className="slash">/</span>
              <strong>
                {location.pathname.startsWith("/project/")
                  ? "Project review"
                  : active?.label || "Studio"}
              </strong>
            </div>
            <div className="topbar-actions">
              <button
                className="global-search"
                onClick={() => setSearchOpen(true)}
              >
                <Search size={15} />
                <span>Quick search</span>
                <kbd>Ctrl K</kbd>
              </button>
              <span className="local-tag">
                <span className="status-dot" />
                Local workspace
              </span>
            </div>
          </header>
          <main id="main" tabIndex={-1}>
            <Routes>
              <Route path="/" element={<Studio />} />
              <Route path="/project/:id" element={<Project />} />
              <Route path="/speed" element={<Speed />} />
              <Route path="/x" element={<XStudio />} />
              <Route path="/carousels" element={<Carousels />} />
              <Route path="/publishing" element={<Publishing />} />
              <Route path="/music" element={<MusicLibrary />} />
              <Route path="/settings" element={<Settings />} />
              <Route
                path="*"
                element={
                  <div className="empty-state">
                    <h1>That page isn't here.</h1>
                    <Button onClick={() => navigate("/")}>
                      Back to studio
                    </Button>
                  </div>
                }
              />
            </Routes>
          </main>
          <footer className="workspace-footer">
            <span>
              <span className="tiny-mark">▰</span> YOUR CONTENT. YOUR STUDIO.
            </span>
            <span>
              CLIPER Studio <b>1.0</b>
            </span>
          </footer>
        </div>
      </div>
      <NewProject open={newOpen} setOpen={setNewOpen} initialUrl={initialUrl} />
      <CommandMenu open={searchOpen} setOpen={setSearchOpen} />
      <Modal
        open={help}
        onOpenChange={setHelp}
        title="A little help, right here."
        description="Your engine, with room to work."
      >
        <div className="help-grid">
          <p>
            <kbd>Ctrl K</kbd> Find a project or jump to any workspace.
          </p>
          <p>
            <kbd>N</kbd> Start a new clipping project.
          </p>
          <p>
            <kbd>Esc</kbd> Close a dialog and return to your work.
          </p>
          <hr />
          <h3>One engine. Two ways to work.</h3>
          <p>
            Telegram and this workspace share saved jobs and preferences. The
            local web worker processes web-created work. When the updated
            Telegram bot owns the engine, it processes both.
          </p>
          <h3>Long streams, considered.</h3>
          <p>
            Scan depth controls how much of a long stream is examined. A
            24-minute scan is 2% of a 20-hour stream. Add focus times or
            increase the budget to explore more.
          </p>
          <h3>Publication stays deliberate.</h3>
          <p>
            Approval mode holds finished assets for review. Publish now sends
            the selected post. Auto-publish is configured separately for clips
            and carousels in Settings.
          </p>
        </div>
      </Modal>
      {toast && (
        <div
          className={`toast ${toast.error ? "error" : ""}`}
          role={toast.error ? "alert" : "status"}
        >
          {toast.error ? <HelpCircle size={18} /> : <Check size={18} />}
          <span>{toast.message}</span>
          <IconButton
            icon={X}
            label="Dismiss notification"
            onClick={() => setToast(null)}
          />
        </div>
      )}
    </StudioContext.Provider>
  );
}

function NewProject({
  open,
  setOpen,
  initialUrl,
}: {
  open: boolean;
  setOpen: (v: boolean) => void;
  initialUrl: string;
}) {
  const { boot, notify, refresh } = useStudio(),
    navigate = useNavigate();
  const [url, setUrl] = useState(initialUrl),
    [rules, setRules] = useState({ ...emptyRules }),
    [tab, setTab] = useState("link"),
    [mode, setMode] = useState(boot.preferences.clipping_mode),
    [scan, setScan] = useState(boot.preferences.scan_minutes),
    [clips, setClips] = useState(boot.preferences.clips),
    [focus, setFocus] = useState(""),
    [busy, setBusy] = useState(false),
    [file, setFile] = useState<File | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    if (open) {
      setUrl(initialUrl);
      setRules({ ...emptyRules });
      setMode(boot.preferences.clipping_mode);
      setScan(boot.preferences.scan_minutes);
      setClips(boot.preferences.clips);
      setError("");
      setFile(null);
      setFocus(boot.preferences.focus_times.map((v) => String(v)).join(" "));
    }
  }, [open, initialUrl]);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      let result: Job;
      if (tab === "upload") {
        if (!file) throw new Error("Choose a video file first.");
        result = (await upload("/jobs/upload", file, rules)) as unknown as Job;
      } else {
        const focusTimes = focus.trim()
          ? focus
              .trim()
              .split(/[ ,]+/)
              .map((t) => {
                const p = t.split(":").map(Number);
                if (
                  p.some((v) => !Number.isFinite(v) || v < 0) ||
                  p.length > 3 ||
                  p.slice(1).some((v) => v >= 60)
                )
                  throw new Error(
                    "Use seconds, MM:SS or HH:MM:SS for focus times.",
                  );
                return p.reduce((a, v) => a * 60 + v, 0);
              })
          : [];
        result = await api<Job>("/jobs", "POST", {
          source: url,
          preferences: {
            clipping_mode: mode,
            scan_minutes: scan,
            clips,
            focus_times: focusTimes,
            ...rules,
          },
        });
      }
      refresh();
      setOpen(false);
      navigate(`/project/${result.id}`);
      notify("Project added to your production queue.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      open={open}
      onOpenChange={(v) => {
        if (!busy) setOpen(v);
      }}
      title="Start with a good source."
      description="Bring a video. We'll help you find the moments worth sharing."
    >
      <form onSubmit={submit}>
        <div className="segmented intake-tabs">
          <button
            type="button"
            className={tab === "link" ? "chosen" : ""}
            onClick={() => setTab("link")}
          >
            <Link2 size={15} />
            Paste a link
          </button>
          <button
            type="button"
            className={tab === "upload" ? "chosen" : ""}
            onClick={() => setTab("upload")}
          >
            <Upload size={15} />
            Upload a video
          </button>
        </div>
        {tab === "link" ? (
          <>
            <Field label="Video or saved stream URL">
              <input
                type="url"
                placeholder="https://youtube.com/watch?v=…"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                required
                autoFocus
              />
            </Field>
            <div className="form-grid">
              <Field label="Clipping engine">
                <select value={mode} onChange={(e) => setMode(e.target.value)}>
                  <option value="audio_first">Normal / stream clipping</option>
                  <option value="gemini_browser">
                    Gemini link clipping · YouTube
                  </option>
                </select>
              </Field>
              <Field label="Clips to discover">
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={clips}
                  onChange={(e) => setClips(+e.target.value)}
                />
              </Field>
            </div>
            {mode === "audio_first" && (
              <>
                <div className="form-grid">
                  <Field
                    label="Long-stream scan budget"
                    hint="Minutes examined, not the source duration."
                  >
                    <input
                      type="number"
                      min={6}
                      max={1440}
                      value={scan}
                      onChange={(e) => setScan(+e.target.value)}
                    />
                  </Field>
                  <Field
                    label="Focus timestamps"
                    hint="Optional. Separate timestamps with spaces."
                  >
                    <input
                      value={focus}
                      onChange={(e) => setFocus(e.target.value)}
                      placeholder="01:20:00 08:10:00"
                    />
                  </Field>
                </div>
                <div className="info-note">
                  <Film size={16} />
                  <span>
                    Captions first. Otherwise, scan audio windows and download
                    only selected video ranges. Partial scans can miss
                    highlights.
                  </span>
                </div>
              </>
            )}
          </>
        ) : (
          <label className="upload-zone">
            <Upload size={26} />
            <strong>{file ? file.name : "Choose a video file"}</strong>
            <span>
              MP4, MOV, MKV or WebM · up to {boot.system.max_download_mb} MB
            </span>
            <input
              type="file"
              accept=".mp4,.mov,.mkv,.webm,.m4v"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </label>
        )}
        <ProjectRules value={rules} onChange={setRules} />
        <div className="project-summary">
          <span>
            {providerName(
              boot.preferences.ai_provider || boot.default_provider,
            )}
          </span>
          <span>
            {boot.preferences.min_seconds}–{boot.preferences.max_seconds}s clips
          </span>
          <span>{boot.preferences.width}p export</span>
        </div>
        {error && (
          <div className="inline-error" role="alert">
            {error}
          </div>
        )}
        <div className="modal-footer">
          <Button
            type="button"
            variant="ghost"
            onClick={() => setOpen(false)}
            disabled={busy}
          >
            Cancel
          </Button>
          <Button variant="primary" busy={busy} icon={ArrowRight}>
            {busy ? "Adding project…" : "Create project"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function CommandMenu({
  open,
  setOpen,
}: {
  open: boolean;
  setOpen: (v: boolean) => void;
}) {
  const [search, setSearch] = useState("");
  const navigate = useNavigate();
  const { data: jobs = [] } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api<Job[]>("/jobs"),
    enabled: open,
  });
  const go = (path: string) => {
    navigate(path);
    setOpen(false);
    setSearch("");
  };
  return (
    <Modal open={open} onOpenChange={setOpen} title="Jump to your next move.">
      <div className="command-input">
        <Search size={18} />
        <input
          aria-label="Search projects and pages"
          placeholder="Search projects or pages…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          autoFocus
        />
      </div>
      <div className="command-results">
        <span className="eyebrow">WORKSPACE</span>
        {navigation
          .filter((n) => n.label.toLowerCase().includes(search.toLowerCase()))
          .map((n) => (
            <button key={n.path} onClick={() => go(n.path)}>
              <n.icon size={17} />
              {n.label}
              <ArrowRight size={14} />
            </button>
          ))}
        <span className="eyebrow">PROJECTS</span>
        {jobs
          .filter((j) =>
            (j.title + j.id).toLowerCase().includes(search.toLowerCase()),
          )
          .slice(0, 6)
          .map((j) => (
            <button key={j.id} onClick={() => go("/project/" + j.id)}>
              <FolderOpen size={17} />
              <span>{j.title}</span>
              <ArrowRight size={14} />
            </button>
          ))}
        {!jobs.length && (
          <p className="muted">Your projects will appear here.</p>
        )}
      </div>
    </Modal>
  );
}
