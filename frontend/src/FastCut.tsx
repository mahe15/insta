import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Scissors,
  Upload,
  Link as LinkIcon,
  Clock,
  FastForward,
  AlertCircle,
  Share2,
  Sparkles,
  ArrowRight,
  Video,
} from "lucide-react";
import { api, upload, when } from "./api";
import type { Job } from "./types";
import {
  Button,
  Field,
  PageHeading,
  SectionTitle,
  Switch,
  Badge,
  useStudio,
} from "./ui";

export default function FastCut() {
  const { boot, notify, refresh } = useStudio();
  const navigate = useNavigate();

  // Intake State
  const [tab, setTab] = useState<"link" | "upload">("link");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fast Cut Parameters
  const [duration, setDuration] = useState<number>(boot.preferences.fast_cut_duration ?? 90);
  const [skipIntro, setSkipIntro] = useState<boolean>(boot.preferences.fast_cut_skip_intro ?? false);
  const [captions, setCaptions] = useState<boolean>(boot.preferences.captions ?? true);
  const [captionStyle, setCaptionStyle] = useState<string>(boot.preferences.style || "studio");

  // Submission State
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Query existing jobs
  const jobsQuery = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api<Job[]>("/jobs"),
    refetchInterval: 4000,
  });

  const fastCutJobs = (jobsQuery.data || []).filter(
    (j) => j.preferences?.fast_cut === true
  );

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);

    try {
      let result: Job;
      const fastCutPrefs = {
        fast_cut: true,
        fast_cut_duration: duration,
        fast_cut_skip_intro: skipIntro,
        layout: "four_three_hook",
        clipping_mode: "audio_first",
        captions,
        style: captionStyle,
        clips: 250, // allow up to 250 sequential parts
      };

      if (tab === "upload") {
        if (!file) throw new Error("Please select or drop a video file first.");
        result = (await upload("/jobs/upload", file, fastCutPrefs)) as unknown as Job;
      } else {
        if (!url.trim()) throw new Error("Please enter a video URL.");
        result = await api<Job>("/jobs", "POST", {
          source: url.trim(),
          preferences: fastCutPrefs,
        });
      }

      refresh();
      notify(`Fast Cut project created with ${duration}s parts!`);
      navigate(`/project/${result.id}`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function handleFileDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const f = e.dataTransfer.files[0];
      if (f.type.startsWith("video/") || f.name.match(/\.(mp4|mov|mkv|webm|avi)$/i)) {
        setFile(f);
      } else {
        setError("Please choose a valid video file (.mp4, .mov, .mkv, .webm)");
      }
    }
  }

  return (
    <div className="fast-cut-workspace">
      <PageHeading
        title="Fast Cut Studio"
        description="Slice any long-form video or upload into sequential 90s parts with 4:3 hook framing & Part 1, Part 2 header banners"
      >
        <span className="fast-cut-chip">
          <Scissors size={12} />
          4:3 Ratio
        </span>
        <span className="fast-cut-chip">
          <Sparkles size={12} />
          Part 1, Part 2 Headers
        </span>
      </PageHeading>

      <div className="fast-cut-grid">
        {/* Main Intake Form Card */}
        <div className="card fast-cut-intake-card">
          <form onSubmit={handleSubmit}>
            <div className="fast-cut-tabs">
              <button
                type="button"
                className={tab === "link" ? "active" : ""}
                onClick={() => setTab("link")}
              >
                <LinkIcon size={15} />
                Video URL (Any Platform)
              </button>
              <button
                type="button"
                className={tab === "upload" ? "active" : ""}
                onClick={() => setTab("upload")}
              >
                <Upload size={15} />
                Upload Raw Video File
              </button>
            </div>

            {error && (
              <div className="captions-off-banner" style={{ margin: "16px 0" }}>
                <AlertCircle size={16} />
                <span>{error}</span>
              </div>
            )}

            {tab === "link" ? (
              <div className="fast-cut-tab-pane">
                <Field
                  label="Video URL"
                  hint="Supports YouTube, TikTok, Twitter/X, Instagram, Vimeo, Twitch streams or direct video URLs"
                >
                  <input
                    type="url"
                    className="input"
                    placeholder="https://www.youtube.com/watch?v=... or any platform link"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    required={tab === "link"}
                  />
                </Field>
              </div>
            ) : (
              <div className="fast-cut-tab-pane">
                <div
                  className={`fast-cut-dropzone ${dragActive ? "drag-active" : ""} ${file ? "has-file" : ""}`}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDragActive(true);
                  }}
                  onDragLeave={() => setDragActive(false)}
                  onDrop={handleFileDrop}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <input
                    type="file"
                    ref={fileInputRef}
                    style={{ display: "none" }}
                    accept="video/*,.mp4,.mov,.mkv,.webm"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        setFile(e.target.files[0]);
                      }
                    }}
                  />
                  {file ? (
                    <div className="dropzone-file-info">
                      <Video size={28} color="#34d399" />
                      <div>
                        <strong>{file.name}</strong>
                        <p>{(file.size / (1024 * 1024)).toFixed(1)} MB · Ready to slice</p>
                      </div>
                      <Button
                        variant="secondary"
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setFile(null);
                        }}
                      >
                        Change file
                      </Button>
                    </div>
                  ) : (
                    <div className="dropzone-prompt">
                      <Upload size={32} />
                      <strong>Drop raw video file here, or click to browse</strong>
                      <p>MP4, MOV, MKV, WebM up to 4GB</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Fast Cut Parameters Configuration */}
            <div className="fast-cut-config-box">
              <div className="fast-cut-section-header">
                <Scissors size={16} />
                <strong>Fast Cut Slicing Parameters</strong>
              </div>

              {/* Clip Duration */}
              <div className="fast-cut-param-row">
                <div className="param-label-group">
                  <div className="param-title">
                    <Clock size={14} />
                    <span>Clip Duration:</span>
                    <strong className="param-value-highlight">{duration} seconds</strong>
                  </div>
                  <small>Length of each sequential part. Default is 90 seconds.</small>
                </div>

                <div className="param-controls">
                  <div className="preset-chips">
                    {[30, 60, 90, 120, 180].map((sec) => (
                      <button
                        key={sec}
                        type="button"
                        className={`preset-chip ${duration === sec ? "active" : ""}`}
                        onClick={() => setDuration(sec)}
                      >
                        {sec}s {sec === 90 ? "★" : ""}
                      </button>
                    ))}
                  </div>
                  <input
                    type="range"
                    min={10}
                    max={300}
                    step={5}
                    value={duration}
                    onChange={(e) => setDuration(Number(e.target.value))}
                    className="fast-cut-slider"
                  />
                </div>
              </div>

              {/* Skip First 3 Min Toggle */}
              <div className="fast-cut-param-row skip-intro-row">
                <div className="param-label-group">
                  <div className="param-title">
                    <FastForward size={14} />
                    <span>Skip first 3 min (180s)</span>
                    <span className={`status-pill ${skipIntro ? "on" : "off"}`}>
                      {skipIntro ? "ON (Starts at 3:00)" : "OFF (Starts at 0:00)"}
                    </span>
                  </div>
                  <small>
                    Bypass video intro, stream countdowns, and sponsor plugs. Part 1 will start at 3:00.
                  </small>
                </div>
                <Switch
                  checked={skipIntro}
                  onChange={setSkipIntro}
                  label="Skip first 3 min"
                />
              </div>

              {/* Aspect Ratio & Hook Framing Info */}
              <div className="fast-cut-framing-preview">
                <div className="framing-diagram-wrap">
                  <div className="mini-four-three-diagram">
                    <span className="diagram-header">Part 1</span>
                    <div className="diagram-screen">4:3 Video Frame</div>
                    <span className="diagram-captions">Captions</span>
                  </div>
                </div>
                <div className="framing-explainer">
                  <strong>4:3 Crop Ratio with Top Header Banners</strong>
                  <p>
                    Every clip is cropped to <strong>4:3 ratio (1080×810)</strong> centered on a
                    9:16 vertical canvas. The top banner automatically renders <code>Part 1</code>, <code>Part 2</code>, etc.
                    directly above the clip, leaving the bottom area for word-level subtitles.
                  </p>
                  <div className="caption-sub-toggle">
                    <Switch
                      checked={captions}
                      onChange={setCaptions}
                      label="Include animated word captions"
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="fast-cut-actions">
              <Button
                variant="primary"
                type="submit"
                disabled={busy || (tab === "link" ? !url.trim() : !file)}
                icon={Scissors}
              >
                {busy ? "Analyzing & Slicing..." : `Start Fast Cut (${duration}s parts)`}
              </Button>
            </div>
          </form>
        </div>

        {/* Sidebar Info & How It Works */}
        <div className="fast-cut-info-sidebar">
          <div className="card fast-cut-guide-card">
            <h3>How Fast Cut Works</h3>
            <ol className="fast-cut-steps">
              <li>
                <strong>1. Universal Ingest</strong>
                <p>Accepts any video link (YouTube, TikTok, Twitter/X, Twitch, etc.) or raw upload.</p>
              </li>
              <li>
                <strong>2. Instant Sequential Slicing</strong>
                <p>
                  A 2-hour video is split into ~80 parts of {duration}s each. Residual fragments under 5s
                  are smoothly absorbed.
                </p>
              </li>
              <li>
                <strong>3. Automated 4:3 Hook Framing</strong>
                <p>Crops to 4:3 with bold "Part 1", "Part 2" headers placed cleanly above the frame.</p>
              </li>
              <li>
                <strong>4. Direct Publishing Integration</strong>
                <p>Schedule all parts to YouTube Shorts and Instagram Reels with one click.</p>
              </li>
            </ol>
          </div>
        </div>
      </div>

      {/* Existing Fast Cut Projects */}
      <div className="fast-cut-projects-section">
        <SectionTitle
          title="Recent Fast Cut Projects"
          note={`${fastCutJobs.length} active or finished Fast Cut projects`}
        />

        {fastCutJobs.length === 0 ? (
          <div className="empty-state fast-cut-empty">
            <Scissors size={32} />
            <h3>No Fast Cut projects yet</h3>
            <p>Paste a video link or upload a file above to slice your first video into sequential 90s parts.</p>
          </div>
        ) : (
          <div className="fast-cut-projects-grid">
            {fastCutJobs.map((j) => (
              <div key={j.id} className="card fast-cut-project-card">
                <div className="project-card-header">
                  <div className="badge-row">
                    <span className="fast-cut-project-badge">
                      <Scissors size={11} />
                      Fast Cut ({j.preferences?.fast_cut_duration || 90}s)
                    </span>
                    <Badge state={j.state} />
                  </div>
                  <span className="project-date">{when(j.created)}</span>
                </div>

                <h4 className="project-title" title={j.title || j.source}>
                  {j.title || j.source || "Untitled Fast Cut Project"}
                </h4>

                <div className="project-stats-row">
                  <span>
                    <strong>{j.clip_count}</strong> parts generated
                  </span>
                  <span>
                    Ratio: <strong>4:3 Hook</strong>
                  </span>
                  {j.preferences?.fast_cut_skip_intro && (
                    <span className="skip-indicator">Skipped 3m</span>
                  )}
                </div>

                <div className="project-card-actions">
                  <Button
                    variant="secondary"
                    type="button"
                    onClick={() => navigate(`/project/${j.id}`)}
                    icon={ArrowRight}
                  >
                    Open in Editor
                  </Button>
                  <Button
                    variant="ghost"
                    type="button"
                    onClick={() => navigate("/publishing")}
                    icon={Share2}
                  >
                    Publish
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
