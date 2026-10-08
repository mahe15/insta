import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, Film, Play, Zap } from "lucide-react";
import { api, seconds } from "./api";
import type { Job } from "./types";
import ProjectRules, { emptyRules } from "./ProjectRules";
import {
  Badge,
  Button,
  ErrorBox,
  Field,
  PageHeading,
  SectionTitle,
  Switch,
  useStudio,
} from "./ui";

export default function Speed() {
  const { boot, refresh, notify } = useStudio(),
    navigate = useNavigate();
  const [url, setUrl] = useState(""),
    [rules, setRules] = useState({ ...emptyRules }),
    [mode, setMode] = useState("gemini_browser");
  const [min, setMin] = useState(6),
    [max, setMax] = useState(60),
    [count, setCount] = useState(5);
  const [scan, setScan] = useState(boot.preferences.scan_minutes),
    [focus, setFocus] = useState("");
  const [sfx, setSfx] = useState(true),
    [gain, setGain] = useState(0.12),
    [zoom, setZoom] = useState(true);
  const [music, setMusic] = useState(boot.preferences.music),
    [render, setRender] = useState(false);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<Error | null>(null);
  const jobs = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api<Job[]>("/jobs"),
    refetchInterval: 5000,
  });
  const sounds = useQuery({
    queryKey: ["speed-sounds"],
    queryFn: () =>
      api<{
        license: string;
        creator: string;
        files: { name: string; url: string }[];
      }>("/speed/sounds"),
  });
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const times = focus.trim()
        ? focus
            .trim()
            .split(/[ ,]+/)
            .map((t) => {
              const raw = t.split(":"),
                p = raw.map(Number);
              if (
                raw.some((x) => !x) ||
                p.length > 3 ||
                p.some((x) => !Number.isFinite(x) || x < 0) ||
                p.slice(1).some((x) => x >= 60)
              )
                throw Error("Use seconds or HH:MM:SS for focus times.");
              return p.reduce((a, v) => a * 60 + v, 0);
            })
        : [];
      const job = await api<Job>("/speed/jobs", "POST", {
        source: url,
        preferences: {
          clipping_mode: mode,
          min_seconds: min,
          max_seconds: max,
          clips: count,
          scan_minutes: scan,
          focus_times: times,
          sound_effects: sfx,
          sfx_gain: gain,
          reaction_zoom: zoom,
          music,
          auto_render: render,
          ...rules,
        },
      });
      refresh();
      notify(
        "Speed project added. English text and event-based editing are enabled.",
      );
      navigate(`/project/${job.id}`);
    } catch (e) {
      setError(e as Error);
    } finally {
      setBusy(false);
    }
  }
  const projects =
    jobs.data?.filter((j) => j.editorial_profile === "ishowspeed") || [];
  return (
    <div className="page speed-page">
      <PageHeading
        eyebrow="ISHOWSPEED STUDIO"
        title="Find the moment. Keep the reaction."
        description="YouTube streams into complete 6–60 second stories. English text. Original energy."
      />
      <div className="speed-layout">
        <section className="settings-section">
          <SectionTitle
            title="Start with his stream"
            note="Find challenges, surprises, fan encounters and football moments with a real payoff."
          />
          <form onSubmit={submit}>
            <Field label="YouTube stream or video link">
              <input
                required
                type="url"
                placeholder="https://www.youtube.com/watch?v=…"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
            </Field>
            <Field
              label="Discovery engine"
              hint="Gemini reads the video link using your shared browser. Audio discovery uses your selected AI provider."
            >
              <select value={mode} onChange={(e) => setMode(e.target.value)}>
                <option value="gemini_browser">
                  Gemini website · visual context
                </option>
                <option value="audio_first">
                  Caption / audio scan · selected AI
                </option>
              </select>
            </Field>
            <div className="form-grid">
              <Field label="Minimum seconds">
                <input
                  type="number"
                  min={6}
                  max={60}
                  value={min}
                  onChange={(e) => setMin(+e.target.value)}
                />
              </Field>
              <Field label="Maximum seconds">
                <input
                  type="number"
                  min={min}
                  max={60}
                  value={max}
                  onChange={(e) => setMax(+e.target.value)}
                />
              </Field>
              <Field label="Clips to discover">
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={count}
                  onChange={(e) => setCount(+e.target.value)}
                />
              </Field>
              <Field
                label="Audio scan budget · minutes"
                hint="Also used if Gemini cannot access the video. Partial scans can miss moments."
              >
                <input
                  type="number"
                  min={6}
                  max={1440}
                  value={scan}
                  onChange={(e) => setScan(+e.target.value)}
                />
              </Field>
            </div>
            <Field
              label="Focus times"
              hint="Optional source timestamps, e.g. 01:20:00 02:15:00."
            >
              <input value={focus} onChange={(e) => setFocus(e.target.value)} />
            </Field>
            <Switch
              label="Sound accents"
              description="A short licensed accent at an observed reaction beat. No repeated meme sounds."
              checked={sfx}
              onChange={setSfx}
            />
            <Field label={`Sound-effect gain · ${Math.round(gain * 100)}%`}>
              <input
                type="range"
                min={0}
                max={0.25}
                step={0.01}
                value={gain}
                onChange={(e) => setGain(+e.target.value)}
                disabled={!sfx}
              />
            </Field>
            <Switch
              label="Reaction punch-in"
              description="One subtle 6% emphasis. Wide action shots keep their full framing."
              checked={zoom}
              onChange={setZoom}
            />
            <Switch
              label="Background music"
              description="Category-matched tracks at 10% gain, lowered beneath speech."
              checked={music}
              onChange={setMusic}
            />
            <Switch
              label="Render the shortlist automatically"
              description="Skip clip selection. Your existing publishing approval setting still applies."
              checked={render}
              onChange={setRender}
            />
            <p className="info-note">
              Publishing:{" "}
              {boot.preferences.auto_publish
                ? "Automatic publishing is enabled in your clip settings."
                : "Finished clips wait for your publishing approval."}{" "}
              <Link to="/settings?tab=automation">Manage</Link>
            </p>
            <ProjectRules value={rules} onChange={setRules} />
            {error && <ErrorBox error={error} />}
            <Button variant="primary" icon={Zap} busy={busy}>
              Find Speed moments
            </Button>
          </form>
        </section>
        <aside>
          <section className="settings-section">
            <SectionTitle
              title="Every second earns its place"
              note="Duration follows the event."
            />
            <div className="speed-duration">
              <strong>6–12s</strong>
              <span>One clear reaction or visual payoff</span>
            </div>
            <div className="speed-duration">
              <strong>12–25s</strong>
              <span>A setup, a surprise, the response</span>
            </div>
            <div className="speed-duration">
              <strong>25–45s</strong>
              <span>A challenge with its actual outcome</span>
            </div>
            <div className="speed-duration">
              <strong>45–60s</strong>
              <span>A story that needs the extra context</span>
            </div>
            <p className="muted small">
              These are editing guides, not predictions of reach. A loud moment
              alone is not a complete clip.
            </p>
          </section>
          <section className="settings-section">
            <SectionTitle
              title="A little sound. A lot of restraint."
              note="Kenney · CC0 licensed accents"
            />
            {sounds.error && <ErrorBox error={sounds.error} />}{" "}
            {sounds.data?.files
              .filter((s) => s.name !== "transition.wav")
              .map((s) => (
                <div className="speed-sound" key={s.name}>
                  <span>
                    <Play size={13} /> {s.name.replace(".wav", "")}
                  </span>
                  <audio controls preload="none" src={s.url} />
                </div>
              ))}
            <p className="muted small">
              Original dialogue stays intact. Sincere moments keep their natural
              sound. Effects are skipped when no suitable beat is detected.
            </p>
          </section>
        </aside>
      </div>
      <SectionTitle
        title="Your Speed projects"
        note="The same review, export and publishing workflow."
      />
      {jobs.error && <ErrorBox error={jobs.error} />}{" "}
      {!projects.length && (
        <p className="muted">Your first Speed project will appear here.</p>
      )}
      <div className="speed-projects">
        {projects.map((j) => (
          <Link className="speed-project" to={`/project/${j.id}`} key={j.id}>
            <Film size={18} />
            <div>
              <strong>{j.title}</strong>
              <small>
                {j.clip_count} moments ·{" "}
                {j.duration ? seconds(j.duration) : "Awaiting analysis"}
              </small>
            </div>
            <Badge state={j.state} />
            <ArrowUpRight size={16} />
          </Link>
        ))}
      </div>
    </div>
  );
}
