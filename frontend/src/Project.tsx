import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCheck,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Copy,
  Download,
  ExternalLink,
  FileText,
  Film,
  Globe,
  Info,
  Layers,
  Play,
  RefreshCw,
  Scissors,
  Search,
  Send,
  Settings2,
  Share2,
  Square,
  TriangleAlert,
  X,
  Youtube,
} from "lucide-react";
import { api, dateTime, providerName, seconds } from "./api";
import type { Clip, Job, YouTubeConnections } from "./types";
import {
  Badge,
  Button,
  Empty,
  ErrorBox,
  Field,
  IconButton,
  Loading,
  Modal,
  Switch,
  useStudio,
} from "./ui";

const categories = {
  cinematic_epic: "Cinematic / Epic",
  emotional_sad: "Emotional / Sad",
  suspense_thriller: "Suspense / Thriller",
  energetic_hype: "Energetic / Hype",
  chill_ambient: "Chill / Ambient",
};
export default function Project() {
  const { id } = useParams(),
    navigate = useNavigate(),
    { notify, refresh } = useStudio();
  const query = useQuery({
    queryKey: ["job", id],
    queryFn: () => api<Job>(`/jobs/${id}`),
    refetchInterval: 4000,
  });
  const [selected, setSelected] = useState<number[]>([]),
    [current, setCurrent] = useState<number | null>(null),
    [tab, setTab] = useState("editor"),
    [busy, setBusy] = useState(false),
    [confirm, setConfirm] = useState(false),
    [dirty, setDirty] = useState(false),
    [editSettings, setEditSettings] = useState(false),
    [publishClip, setPublishClip] = useState<Clip | null>(null);
  const job = query.data,
    clips = job?.analysis?.clips || [],
    clip = clips.find((c) => c.id === current) || clips[0];
  useEffect(() => {
    setSelected([]);
    setCurrent(null);
    setDirty(false);
  }, [id]);
  async function action(name: string) {
    setBusy(true);
    try {
      const result = await api<Job>(`/jobs/${id}/actions/${name}`, "POST");
      refresh();
      if (name === "duplicate") navigate(`/project/${result.id}`);
      notify(
        name === "cancel"
          ? "Project cancelled."
          : name === "retry"
            ? "Project queued for retry."
            : "New project created.",
      );
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
      setConfirm(false);
    }
  }
  async function render() {
    setBusy(true);
    try {
      await api(`/jobs/${id}/render`, "POST", { ids: selected });
      refresh();
      notify(`${selected.length} clips queued for rendering.`);
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  if (query.error)
    return (
      <div className="page">
        <ErrorBox error={query.error} retry={() => void query.refetch()} />
      </div>
    );
  if (!job) return <Loading />;
  const editable = job.state === "awaiting_selection";
  return (
    <div className="page project-page">
      <div className="project-breadcrumb">
        <Link to="/">
          <ArrowLeft size={15} />
          All projects
        </Link>
        <span>PROJECT {job.id.slice(0, 6).toUpperCase()}</span>
      </div>
      <div className="project-heading">
        <div>
          <h1>{job.title}</h1>
          <div className="project-heading-meta">
            <Badge state={job.state} />
            <span>{dateTime(job.created)}</span>
            <span>{providerName(job.provider)}</span>
          </div>
        </div>
        <div className="heading-actions">
          {job.state === "failed" && (
            <Button
              icon={RefreshCw}
              onClick={() => void action("retry")}
              busy={busy}
            >
              Retry
            </Button>
          )}
          {["complete", "failed", "cancelled"].includes(job.state) ? (
            <Button
              icon={Copy}
              busy={busy}
              onClick={() => void action("duplicate")}
            >
              Duplicate project
            </Button>
          ) : (
            <Button variant="ghost" onClick={() => setConfirm(true)}>
              Cancel project
            </Button>
          )}
          {editable && (
            <Button icon={Settings2} onClick={() => setEditSettings(true)}>
              Edit settings
            </Button>
          )}
          {editable && (
            <Button
              icon={Play}
              variant="primary"
              disabled={!selected.length || dirty}
              busy={busy}
              onClick={() => void render()}
            >
              Render {selected.length || ""} selected
            </Button>
          )}
        </div>
      </div>
      {job.error && (
        <div className="error-box" role="alert">
          <TriangleAlert size={19} />
          <div>
            <strong>This project needs attention</strong>
            <p>{job.error}</p>
          </div>
        </div>
      )}
      <div className="project-facts">
        <div>
          <span>Source length</span>
          <strong>
            {job.duration ? seconds(job.duration) : "Inspecting source"}
          </strong>
        </div>
        <div>
          <span>Discovery coverage</span>
          <strong>
            {job.coverage.fraction !== undefined
              ? `${(job.coverage.fraction * 100).toFixed(1)}%`
              : "—"}
            {job.coverage.partial && <small>Partial scan</small>}
          </strong>
        </div>
        <div>
          <span>Shortlisted</span>
          <strong>{clips.length} moments</strong>
        </div>
        <div>
          <span>Exported</span>
          <strong>{job.rendered} clips</strong>
        </div>
        <a
          href={`/api/jobs/${id}/files/captions-and-edit-plans.zip`}
          className="button"
          download
        >
          <Download size={15} />
          Export edit data
        </a>
      </div>
      {job.coverage.partial && (
        <div className="coverage-note">
          <Info size={14} />
          <span>
            {Math.round((job.coverage.analyzed_seconds || 0) / 60)} minutes
            examined across the source. Unexamined moments may be missed.
          </span>
          <button onClick={() => setTab("coverage")}>
            View scan map <ArrowRight size={12} />
          </button>
        </div>
      )}
      <div className="project-workspace">
        <aside className="shortlist">
          <div className="shortlist-heading">
            <h2>
              Shortlist <span className="count">{clips.length}</span>
            </h2>
            {editable && (
              <button
                onClick={() =>
                  setSelected(
                    selected.length === clips.length
                      ? []
                      : clips.map((c) => c.id),
                  )
                }
              >
                {selected.length === clips.length ? "Clear" : "Select all"}
              </button>
            )}
          </div>
          {clips.length ? (
            clips.map((c, index) => (
              <div
                key={c.id}
                className={`shortlist-item ${clip?.id === c.id ? "selected" : ""}`}
              >
                <label className="clip-checkbox">
                  <input
                    type="checkbox"
                    aria-label={`Select clip ${c.id}`}
                    disabled={!editable}
                    checked={selected.includes(c.id)}
                    onChange={(e) =>
                      setSelected(
                        e.target.checked
                          ? [...selected, c.id]
                          : selected.filter((n) => n !== c.id),
                      )
                    }
                  />
                </label>
                <button
                  onClick={() => {
                    if (dirty && c.id !== clip?.id) {
                      notify(
                        "Save or reset your current clip edits first.",
                        true,
                      );
                      return;
                    }
                    setCurrent(c.id);
                  }}
                >
                  <div className="shortlist-number">
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <span>{Math.round(c.end - c.start)}s</span>
                  </div>
                  <h3>{c.title}</h3>
                  <div className="shortlist-score">
                    <span>
                      {seconds(c.start)} — {seconds(c.end)}
                    </span>
                    <strong>
                      {c.score}
                      <small>/100</small>
                    </strong>
                  </div>
                  {c.video && (
                    <div className="shortlist-actions-bar">
                      <span className="rendered-label">
                        <Check size={11} />
                        Export ready
                      </span>
                      {c.publications?.some(
                        (p) =>
                          p.platform === "youtube" && p.state === "published",
                      ) ? (
                        <span
                          className="shortlist-yt-live"
                          title="Published to YouTube Shorts"
                        >
                          <span className="yt-dot" /> Live
                        </span>
                      ) : null}
                      <span
                        role="button"
                        tabIndex={0}
                        className="shortlist-publish-btn"
                        title="Publish now to YouTube Shorts"
                        onClick={(e) => {
                          e.stopPropagation();
                          setPublishClip(c);
                        }}
                      >
                        <Send size={11} /> Publish
                      </span>
                    </div>
                  )}
                </button>
              </div>
            ))
          ) : (
            <p className="shortlist-empty">
              Your selected moments will appear here after analysis.
            </p>
          )}
          <div className="shortlist-footnote">
            <Info size={13} />
            Scores are editorial estimates, not predicted views.
          </div>
        </aside>
        <section className="editor-workspace">
          <div
            className="editor-tabs"
            role="tablist"
            aria-label="Project panels"
          >
            {[
              ["editor", "Clip editor", Scissors],
              ["transcript", "Transcript", FileText],
              ["coverage", "Scan map", Layers],
            ].map(([key, label, Icon]) => {
              const I = Icon as typeof Scissors;
              return (
                <button
                  key={String(key)}
                  role="tab"
                  aria-selected={tab === key}
                  onClick={() => setTab(String(key))}
                >
                  <I size={15} />
                  {String(label)}
                </button>
              );
            })}
          </div>
          {tab === "editor" ? (
            clip ? (
              <ClipEditor
                key={clip.id}
                clip={clip}
                job={job}
                editable={editable}
                onDirty={setDirty}
                onPublish={setPublishClip}
              />
            ) : (
              <div className="processing-empty">
                <div className="processing-symbol">
                  <Film size={30} strokeWidth={1.25} />
                  {["analyzing", "rendering"].includes(job.state) && <i />}
                </div>
                <h2>
                  {job.state === "failed"
                    ? "Let's get this back on track."
                    : job.state === "cancelled"
                      ? "This project is paused in time."
                      : "Finding the moments that matter."}
                </h2>
                <p>{job.stage}</p>
                <div className="process-steps">
                  {[
                    "Inspect source",
                    "Discover moments",
                    "Review shortlist",
                    "Render & finish",
                  ].map((s, i) => (
                    <div key={s} className={i === 0 ? "current" : ""}>
                      <span>{i + 1}</span>
                      {s}
                    </div>
                  ))}
                </div>
                <p className="muted small">
                  You can leave this page. Progress is saved by the engine.
                </p>
              </div>
            )
          ) : tab === "transcript" ? (
            <TranscriptView id={id!} />
          ) : (
            <div className="scan-map">
              <h2>The parts we examined.</h2>
              <p>
                Each interval below contributed to discovery. Open gaps were not
                examined.
              </p>
              <div className="coverage-track">
                {job.coverage.ranges?.map((r, i) => (
                  <span
                    key={i}
                    style={{
                      left: `${(r.start / (job.duration || 1)) * 100}%`,
                      width: `${((r.end - r.start) / (job.duration || 1)) * 100}%`,
                    }}
                    title={`${seconds(r.start)}–${seconds(r.end)}`}
                  />
                ))}
              </div>
              <div className="timeline-ends">
                <span>00:00</span>
                <span>{seconds(job.duration || 0)}</span>
              </div>
              <div className="scan-ranges">
                {job.coverage.ranges?.map((r, i) => (
                  <div key={i}>
                    <span>{String(i + 1).padStart(2, "0")}</span>
                    <strong>
                      {seconds(r.start)} — {seconds(r.end)}
                    </strong>
                    <span>{r.reason}</span>
                    <small>{Math.round((r.end - r.start) / 60)} min</small>
                  </div>
                )) || (
                  <Empty
                    icon={Layers}
                    title="No scan map for this project"
                    description="Local uploads and older projects may use a full transcript instead of discovery windows."
                  />
                )}
              </div>
            </div>
          )}
        </section>
      </div>
      <ProjectPreferences
        job={job}
        open={editSettings}
        setOpen={setEditSettings}
      />
      <PublishClipModal
        clip={publishClip}
        job={job}
        open={!!publishClip}
        setOpen={(v: boolean) => !v && setPublishClip(null)}
      />
      <Modal
        open={confirm}
        onOpenChange={setConfirm}
        title="Cancel this project?"
        description="Processing will stop. Completed files remain in your workspace."
      >
        <p className="confirm-subject">{job.title}</p>
        <div className="modal-footer">
          <Button onClick={() => setConfirm(false)}>Keep working</Button>
          <Button
            variant="danger"
            busy={busy}
            onClick={() => void action("cancel")}
          >
            Cancel project
          </Button>
        </div>
      </Modal>
    </div>
  );
}

function ClipEditor({
  clip,
  job,
  editable,
  onDirty,
  onPublish,
}: {
  clip: Clip;
  job: Job;
  editable: boolean;
  onDirty: (v: boolean) => void;
  onPublish: (c: Clip) => void;
}) {
  const { notify, refresh } = useStudio(),
    [draft, setDraft] = useState({
      title: clip.title,
      start: clip.start,
      end: clip.end,
      caption: clip.caption || "",
      hashtags: clip.hashtags || [],
      music_category: clip.music_category,
    }),
    [saving, setSaving] = useState(false),
    [panel, setPanel] = useState("story");
  const base = {
      title: clip.title,
      start: clip.start,
      end: clip.end,
      caption: clip.caption || "",
      hashtags: clip.hashtags || [],
      music_category: clip.music_category,
    },
    dirty = JSON.stringify(base) !== JSON.stringify(draft);
  useEffect(() => {
    onDirty(dirty);
    return () => onDirty(false);
  }, [dirty]);
  async function save() {
    setSaving(true);
    try {
      await api(`/jobs/${job.id}/clips/${clip.id}`, "PUT", draft);
      refresh();
      notify("Clip edits saved. Review the rendered result before publishing.");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setSaving(false);
    }
  }
  return (
    <div className="clip-editor">
      <div className="preview-column">
        <div className="video-stage">
          {clip.video ? (
            <video
              key={clip.video}
              controls
              preload="metadata"
              poster={clip.cover || undefined}
              src={clip.video}
            />
          ) : (
            <div className="unrendered-preview">
              <p>{draft.title}</p>
              <div>
                <Film size={38} strokeWidth={1} />
                <strong>Your clip, coming into focus.</strong>
                <span>The preview appears after rendering.</span>
              </div>
              <small>
                {seconds(draft.start)} → {seconds(draft.end)}
              </small>
            </div>
          )}
        </div>
        <div className="preview-caption">
          <span>
            <Square size={12} />{" "}
            {job.preferences?.layout === "square_hook"
              ? "1:1 video · 9:16 canvas"
              : "9:16 vertical"}
          </span>
          <span>
            {Math.round(draft.end - draft.start)} sec ·{" "}
            {job.preferences?.width || 1080}p
          </span>
        </div>
        {clip.video && (
          <div className="preview-publish-wrap">
            <div className="preview-downloads">
              <Button
                variant="primary"
                icon={Send}
                className="btn-publish-now-hero"
                onClick={() => onPublish(clip)}
              >
                Publish now
              </Button>
              <a
                className="button"
                href={clip.video}
                download={`clip_${clip.id}.mp4`}
              >
                <Download size={14} />
                Download
              </a>
              <a
                className="text-link"
                href={`/api/jobs/${job.id}/files/clip_${String(clip.id).padStart(2, "0")}.srt`}
                download
              >
                Subtitles
              </a>
            </div>
            {clip.publications
              ?.filter((p) => p.state === "published")
              .map((pub) => (
                <div key={pub.id} className="clip-live-banner">
                  <div className="live-banner-left">
                    <span className="live-dot" />
                    <strong>
                      {pub.platform === "youtube"
                        ? "YouTube Shorts"
                        : "Instagram"}
                    </strong>
                    <span>Live</span>
                  </div>
                  {pub.platform === "youtube" && pub.media_id && (
                    <a
                      href={`https://www.youtube.com/shorts/${pub.media_id}`}
                      target="_blank"
                      rel="noreferrer"
                      className="live-banner-link"
                    >
                      Watch Short <ExternalLink size={12} />
                    </a>
                  )}
                </div>
              ))}
          </div>
        )}
        <div className="editorial-summary">
          <div>
            <span className="eyebrow">EDITORIAL SCORE</span>
            <strong>
              {clip.score}
              <small>/100</small>
            </strong>
          </div>
          <p>{clip.reason}</p>
          <div className="rating-bars">
            {Object.entries(clip.ratings).map(([name, score]) => (
              <div key={name}>
                <span>{name}</span>
                <i>
                  <b style={{ width: `${score}%` }} />
                </i>
                <small>{score}</small>
              </div>
            ))}
          </div>
        </div>
        {clip.qa && (
          <div className="quality-summary">
            <CheckCheck size={17} />
            <div>
              <strong>Technical checks passed</strong>
              <span>Decode, dimensions, duration and audio verified.</span>
            </div>
          </div>
        )}
      </div>
      <div className="clip-inspector">
        <div className="inspector-heading">
          <h2>Make the moment yours.</h2>
          <p>
            {editable
              ? "Fine-tune the story before you render."
              : "Your saved editorial and export details."}
          </p>
        </div>
        <div className="segmented inspector-tabs">
          <button
            className={panel === "story" ? "chosen" : ""}
            onClick={() => setPanel("story")}
          >
            Story & hook
          </button>
          <button
            className={panel === "publish" ? "chosen" : ""}
            onClick={() => setPanel("publish")}
          >
            Caption & music
          </button>
        </div>
        {panel === "story" ? (
          <>
            <Field
              label="Hook title"
              hint="The white title above your clip. Keep the promise grounded in the source."
            >
              <textarea
                rows={3}
                maxLength={90}
                value={draft.title}
                disabled={!editable}
                onChange={(e) => setDraft({ ...draft, title: e.target.value })}
              />
              <span className="character-count">{draft.title.length}/90</span>
            </Field>
            {editable && clip.hook_variants?.length > 0 && (
              <div className="hook-alternatives">
                <span className="eyebrow">OTHER DIRECTIONS</span>
                {clip.hook_variants.map((hook, i) => (
                  <button
                    key={i}
                    onClick={() =>
                      setDraft({ ...draft, title: hook.slice(0, 90) })
                    }
                  >
                    <span>{String(i + 1).padStart(2, "0")}</span>
                    {hook}
                    <ArrowRight size={13} />
                  </button>
                ))}
              </div>
            )}
            <div className="form-grid">
              <Field label="Start · seconds">
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={draft.start}
                  disabled={!editable}
                  onChange={(e) =>
                    setDraft({ ...draft, start: +e.target.value })
                  }
                />
              </Field>
              <Field label="End · seconds">
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={draft.end}
                  disabled={!editable}
                  onChange={(e) => setDraft({ ...draft, end: +e.target.value })}
                />
              </Field>
            </div>
            <div className="inspector-note">
              <Clock3 size={14} />
              <span>
                {Math.round((draft.end - draft.start) * 100) / 100} seconds ·
                requested {job.preferences?.min_seconds}–
                {job.preferences?.max_seconds}s
              </span>
            </div>
            <div className="spoken-excerpt">
              <span className="eyebrow">IN THEIR WORDS</span>
              <p>“{clip.text}”</p>
            </div>
          </>
        ) : (
          <>
            <Field label="Instagram caption">
              <textarea
                rows={6}
                maxLength={1800}
                value={draft.caption}
                disabled={!editable}
                onChange={(e) =>
                  setDraft({ ...draft, caption: e.target.value })
                }
              />
            </Field>
            <Field
              label="Hashtags"
              hint="Up to five relevant hashtags, separated by spaces."
            >
              <input
                value={draft.hashtags.join(" ")}
                disabled={!editable}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    hashtags: e.target.value.split(/\s+/).filter(Boolean),
                  })
                }
              />
            </Field>
            <Field
              label="Music direction"
              hint="A random track is selected from the matching library folder."
            >
              <select
                disabled={!editable}
                value={draft.music_category}
                onChange={(e) =>
                  setDraft({ ...draft, music_category: e.target.value })
                }
              >
                {Object.entries(categories).map(([key, name]) => (
                  <option key={key} value={key}>
                    {name}
                  </option>
                ))}
              </select>
            </Field>
            <div className="info-note">
              <Info size={15} />
              <span>
                Speech stays in front. Music uses your saved gain, normalization
                and ducking settings.
              </span>
            </div>
          </>
        )}
        {editable ? (
          <div className="inspector-save">
            <span>{dirty ? "Unsaved changes" : "All changes saved"}</span>
            <Button
              disabled={!dirty || saving}
              variant="ghost"
              onClick={() => setDraft(base)}
            >
              Reset
            </Button>
            <Button
              variant="primary"
              disabled={!dirty}
              busy={saving}
              icon={Check}
              onClick={() => void save()}
            >
              Save edits
            </Button>
          </div>
        ) : (
          <p className="inspector-readonly">
            <Info size={14} />
            Duplicate the project to make a new edit.
          </p>
        )}
      </div>
    </div>
  );
}

function TranscriptView({ id }: { id: string }) {
  const [search, setSearch] = useState(""),
    [offset, setOffset] = useState(0);
  const query = useQuery({
    queryKey: ["transcript", id, search, offset],
    queryFn: () =>
      api<{
        segments: { start: number; end: number; text: string }[];
        total: number;
      }>(
        `/jobs/${id}/transcript?q=${encodeURIComponent(search)}&offset=${offset}`,
      ),
  });
  return (
    <div className="transcript-panel">
      <div className="transcript-heading">
        <h2>The source, in words.</h2>
        <label className="search-field">
          <Search size={16} />
          <input
            placeholder="Search transcript…"
            aria-label="Search transcript"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setOffset(0);
            }}
          />
        </label>
      </div>
      {query.error ? (
        <ErrorBox error={query.error} />
      ) : query.isPending ? (
        <Loading />
      ) : query.data?.segments.length ? (
        <>
          {query.data.segments.map((s, i) => (
            <div className="transcript-line" key={i}>
              <span>{seconds(s.start)}</span>
              <p>{s.text}</p>
            </div>
          ))}
          <div className="pagination">
            <Button
              disabled={!offset}
              onClick={() => setOffset(Math.max(0, offset - 200))}
            >
              Previous
            </Button>
            <span>
              {offset + 1}–{Math.min(offset + 200, query.data.total)} of{" "}
              {query.data.total} segments
            </span>
            <Button
              disabled={offset + 200 >= query.data.total}
              onClick={() => setOffset(offset + 200)}
            >
              Next
            </Button>
          </div>
        </>
      ) : (
        <Empty
          icon={FileText}
          title="No transcript lines to show"
          description="The transcript appears after discovery. If you searched, try another phrase."
        />
      )}
    </div>
  );
}

function ProjectPreferences({
  job,
  open,
  setOpen,
}: {
  job: Job;
  open: boolean;
  setOpen: (v: boolean) => void;
}) {
  const { notify, refresh } = useStudio(),
    [draft, setDraft] = useState(job.preferences!),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    if (open && job.preferences) setDraft(job.preferences);
  }, [open]);
  if (!draft) return null;
  async function save() {
    setBusy(true);
    try {
      const keys = [
        "style",
        "captions",
        "reframe",
        "width",
        "fps",
        "color_grade",
        "export_quality",
        "layout",
        "music",
        "music_gain",
        "music_normalize",
        "music_ducking",
        "smart_crop",
        "preserve_wide_groups",
        "trim_edges",
        "text_mode",
        "sound_effects",
        "sfx_gain",
        "reaction_zoom",
        "description_suffix",
        "overlay_text",
      ] as const;
      await api(
        `/jobs/${job.id}/preferences`,
        "PUT",
        Object.fromEntries(keys.map((k) => [k, draft[k]])),
      );
      refresh();
      setOpen(false);
      notify("Editing settings saved for this project only.");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      open={open}
      onOpenChange={setOpen}
      title="The finishing touches."
      description="These settings apply only to this project, before rendering."
    >
      <ProjectRules value={draft} onChange={rules => setDraft({ ...draft, ...rules })} discovered />
      <div className="form-grid">
        <Field label="Project layout">
          <select
            value={draft.layout}
            onChange={(e) => setDraft({ ...draft, layout: e.target.value })}
          >
            <option value="square_hook">Square video + hook</option>
            <option value="legacy">Full vertical</option>
          </select>
        </Field>
        <Field label="Project resolution">
          <select
            value={draft.width}
            onChange={(e) => setDraft({ ...draft, width: +e.target.value })}
          >
            {[1080, 720, 360].map((w) => (
              <option key={w} value={w}>
                {w}p
              </option>
            ))}
          </select>
        </Field>
        <Field label="Project reframing">
          <select
            value={draft.reframe}
            onChange={(e) => setDraft({ ...draft, reframe: e.target.value })}
          >
            <option value="auto">Face aware</option>
            <option value="center">Center crop</option>
            <option value="blur">Preserve frame + blur</option>
          </select>
        </Field>
        <Field label="Project frame rate">
          <select
            value={draft.fps}
            onChange={(e) => setDraft({ ...draft, fps: +e.target.value })}
          >
            <option value={60}>60 fps</option>
            <option value={30}>30 fps</option>
          </select>
        </Field>
        <Field label="Project colour finish">
          <select
            value={draft.color_grade}
            onChange={(e) =>
              setDraft({ ...draft, color_grade: e.target.value })
            }
          >
            <option value="natural">Natural</option>
            <option value="vivid">Vivid</option>
            <option value="off">Off</option>
          </select>
        </Field>
        <Field label="Project export quality">
          <select
            value={draft.export_quality}
            onChange={(e) =>
              setDraft({ ...draft, export_quality: e.target.value })
            }
          >
            <option value="high">High-quality master</option>
            <option value="compact">Compact · Telegram budget</option>
          </select>
        </Field>
        <Field label="Project caption style">
          <select
            value={draft.style}
            onChange={(e) => setDraft({ ...draft, style: e.target.value })}
          >
            {["studio", "bold", "minimal"].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </Field>
        <Field label="Project text language">
          <select
            value={draft.text_mode}
            disabled={draft.editorial_profile === "ishowspeed"}
            onChange={(e) => setDraft({ ...draft, text_mode: e.target.value })}
          >
            <option value="romanized">
              English letters · original language
            </option>
            <option value="english">English translation</option>
            <option value="source">Original script</option>
          </select>
        </Field>
      </div>
      {(
        [
          ["captions", "Burn in captions"],
          ["smart_crop", "Track face groups"],
          ["preserve_wide_groups", "Preserve wide groups"],
          ["trim_edges", "Tidy clip edges"],
          ["sound_effects", "Speed sound accents"],
          ["reaction_zoom", "Speed reaction punch-in"],
          ["music", "Background music"],
          ["music_normalize", "Normalize music"],
          ["music_ducking", "Duck music beneath speech"],
        ] as const
      ).map(
        ([key, label]) =>
          (!["sound_effects", "reaction_zoom"].includes(key) ||
            draft.editorial_profile === "ishowspeed") && (
            <Switch
              key={key}
              label={label}
              checked={draft[key]}
              onChange={(v) => setDraft({ ...draft, [key]: v })}
            />
          ),
      )}
      {draft.editorial_profile === "ishowspeed" && (
        <Field
          label={`Sound-effect gain · ${Math.round(draft.sfx_gain * 100)}%`}
        >
          <input
            type="range"
            min={0}
            max={0.25}
            step={0.01}
            value={draft.sfx_gain}
            onChange={(e) => setDraft({ ...draft, sfx_gain: +e.target.value })}
          />
        </Field>
      )}
      <Field
        label={`Project music gain · ${Math.round(draft.music_gain * 100)}%`}
      >
        <input
          type="range"
          min="0"
          max="0.3"
          step="0.01"
          value={draft.music_gain}
          onChange={(e) => setDraft({ ...draft, music_gain: +e.target.value })}
        />
      </Field>
      <div className="modal-footer">
        <Button onClick={() => setOpen(false)}>Cancel</Button>
        <Button
          variant="primary"
          icon={Check}
          busy={busy}
          onClick={() => void save()}
        >
          Save project settings
        </Button>
      </div>
    </Modal>
  );
}

function PublishClipModal({
  clip,
  job,
  open,
  setOpen,
}: {
  clip: Clip | null;
  job: Job;
  open: boolean;
  setOpen: (o: boolean) => void;
}) {
  const { notify, refresh } = useStudio();
  const connectionsQuery = useQuery({
    queryKey: ["youtube-connections"],
    queryFn: () => api<YouTubeConnections>("/youtube/connections"),
    enabled: open,
  });

  const [platform, setPlatform] = useState<"youtube" | "instagram">("youtube");
  const [account, setAccount] = useState("main");
  const [title, setTitle] = useState("");
  const [caption, setCaption] = useState("");
  const [tags, setTags] = useState("");
  const [privacy, setPrivacy] = useState("public");
  const [submitting, setSubmitting] = useState(false);
  const [copied, setCopied] = useState(false);
  const [publishedResult, setPublishedResult] = useState<{
    url: string;
    media_id: string;
    channel_title: string;
  } | null>(null);

  useEffect(() => {
    if (clip && open) {
      setPublishedResult(null);
      setCopied(false);
      const rawTitle = clip.title || `Clip #${clip.id}`;
      setTitle(rawTitle);
      setCaption(clip.caption || clip.text || rawTitle);
      const tagList = Array.from(
        new Set([
          "shorts",
          "clips",
          "viral",
          ...(clip.hashtags || []).map((t) => t.replace(/^#/, "")),
        ]),
      );
      setTags(tagList.join(" "));

      if (connectionsQuery.data?.accounts?.length) {
        const authed = connectionsQuery.data.accounts.find((a) => a.authorized);
        if (authed) {
          setAccount(authed.key);
          setPrivacy(authed.privacy || "public");
        } else {
          setAccount(connectionsQuery.data.accounts[0].key);
        }
      }
    }
  }, [clip, open, connectionsQuery.data]);

  if (!clip) return null;

  const ytAccounts = connectionsQuery.data?.accounts || [];
  const selectedYtAccount = ytAccounts.find((a) => a.key === account);

  async function handlePublish(publishNow: boolean) {
    if (!clip) return;
    setSubmitting(true);
    try {
      const tagArray = tags
        .split(/[\s,]+/)
        .map((t) => t.replace(/^#/, "").trim())
        .filter(Boolean);

      const res = await api<{
        ok: boolean;
        state: string;
        platform: string;
        media_id?: string;
        url?: string;
        channel_title?: string;
        message?: string;
      }>(`/jobs/${job.id}/clips/${clip.id}/publish`, "POST", {
        platform,
        account,
        title,
        caption,
        hashtags: tagArray,
        privacy,
        publish_now: publishNow,
      });

      refresh();

      if (res.state === "published" && res.url) {
        setPublishedResult({
          url: res.url,
          media_id: res.media_id || "",
          channel_title: res.channel_title || account,
        });
        notify(res.message || "Published to YouTube Shorts successfully!");
      } else {
        notify(res.message || "Clip queued for publishing.");
        setOpen(false);
      }
    } catch (err) {
      notify((err as Error).message, true);
    } finally {
      setSubmitting(false);
    }
  }

  function copyLink() {
    if (publishedResult?.url) {
      void navigator.clipboard.writeText(publishedResult.url);
      setCopied(true);
      notify("Shorts link copied to clipboard!");
      setTimeout(() => setCopied(false), 2500);
    }
  }

  return (
    <Modal
      open={open}
      onOpenChange={(v: boolean) => {
        if (!submitting) setOpen(v);
      }}
      title={`Publish Clip #${clip.id}`}
      description="Choose destination account and review auto-generated metadata before publishing."
    >
      {publishedResult ? (
        <div className="publish-success-card">
          <div className="success-icon-badge">
            <CheckCircle2 size={36} color="#059669" />
          </div>
          <h3>Published to YouTube Shorts!</h3>
          <p className="success-channel">
            Channel: <strong>{publishedResult.channel_title}</strong>
          </p>
          <div className="success-link-box">
            <span>{publishedResult.url}</span>
            <button type="button" className="copy-btn" onClick={copyLink}>
              {copied ? <Check size={14} /> : <Copy size={14} />}
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <div className="success-actions">
            <a
              href={publishedResult.url}
              target="_blank"
              rel="noreferrer"
              className="button button-primary"
            >
              <ExternalLink size={14} /> Watch on YouTube
            </a>
            <Button onClick={() => setOpen(false)}>Close</Button>
          </div>
        </div>
      ) : (
        <div className="publish-modal-body">
          <div className="publish-platform-picker">
            <button
              type="button"
              className={`platform-pill ${platform === "youtube" ? "active yt" : ""}`}
              onClick={() => setPlatform("youtube")}
            >
              <Youtube size={16} />
              <span>YouTube Shorts</span>
              {selectedYtAccount?.authorized && (
                <span className="auth-dot" title="Authorized" />
              )}
            </button>
            <button
              type="button"
              className={`platform-pill ${platform === "instagram" ? "active ig" : ""}`}
              onClick={() => setPlatform("instagram")}
            >
              <Globe size={16} />
              <span>Instagram Reels</span>
            </button>
          </div>

          {platform === "youtube" ? (
            <div className="destination-account-card">
              <Field
                label="YouTube Channel Destination"
                hint={
                  selectedYtAccount?.authorized
                    ? `Connected: ${selectedYtAccount.title} (${selectedYtAccount.channel_id || "Active"})`
                    : "Channel needs authorization in Settings."
                }
              >
                <select
                  value={account}
                  onChange={(e) => {
                    setAccount(e.target.value);
                    const acc = ytAccounts.find(
                      (a) => a.key === e.target.value,
                    );
                    if (acc?.privacy) setPrivacy(acc.privacy);
                  }}
                >
                  {ytAccounts.map((a) => (
                    <option key={a.key} value={a.key}>
                      {a.title} ({a.key}){" "}
                      {a.authorized ? "✓ Connected" : "⚠ Not connected"}
                    </option>
                  ))}
                </select>
              </Field>

              {selectedYtAccount?.authorized ? (
                <div className="channel-connected-banner">
                  {selectedYtAccount.thumbnail ? (
                    <img
                      src={selectedYtAccount.thumbnail}
                      alt={selectedYtAccount.title}
                      className="channel-avatar"
                    />
                  ) : (
                    <div className="channel-avatar-placeholder">
                      <Youtube size={16} />
                    </div>
                  )}
                  <div>
                    <strong>{selectedYtAccount.title}</strong>
                    <span>
                      Direct API upload · Ready for instant publishing
                    </span>
                  </div>
                </div>
              ) : (
                <div className="channel-warning-banner">
                  <span>
                    Channel '{account}' requires authorization. Please authorize
                    it in Settings.
                  </span>
                  <Link
                    to="/settings"
                    className="text-link"
                    onClick={() => setOpen(false)}
                  >
                    Go to Settings →
                  </Link>
                </div>
              )}
            </div>
          ) : (
            <div className="destination-account-card">
              <Field
                label="Instagram Account"
                hint="From config/instagram.json"
              >
                <input
                  value={account}
                  onChange={(e) => setAccount(e.target.value)}
                  placeholder="e.g. clips, main"
                />
              </Field>
            </div>
          )}

          <div className="publish-meta-fields">
            <Field
              label={
                platform === "youtube"
                  ? "Shorts Title (#Shorts added automatically)"
                  : "Post Title"
              }
              hint="Optimized from the clip's hook for maximum engagement"
            >
              <input
                value={title}
                maxLength={90}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Clip title"
              />
            </Field>

            <Field
              label="Description / Caption"
              hint="Pre-filled with AI summary and excerpt"
            >
              <textarea
                rows={4}
                value={caption}
                onChange={(e) => setCaption(e.target.value)}
                placeholder="Description / caption"
              />
            </Field>

            <div className="form-grid">
              <Field
                label="Hashtags & Tags"
                hint="Separated by space (e.g. shorts clips viral)"
              >
                <input
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  placeholder="shorts clips viral"
                />
              </Field>

              {platform === "youtube" && (
                <Field label="Privacy Visibility">
                  <select
                    value={privacy}
                    onChange={(e) => setPrivacy(e.target.value)}
                  >
                    <option value="public">Public (Immediate reach)</option>
                    <option value="unlisted">Unlisted (Shareable link)</option>
                    <option value="private">Private (Draft)</option>
                  </select>
                </Field>
              )}
            </div>
          </div>

          <div className="modal-footer">
            <Button
              variant="ghost"
              onClick={() => setOpen(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button
              variant="secondary"
              onClick={() => void handlePublish(false)}
              disabled={
                submitting ||
                (platform === "youtube" && !selectedYtAccount?.authorized)
              }
            >
              Queue for later
            </Button>
            <Button
              variant="primary"
              icon={Send}
              busy={submitting}
              disabled={
                submitting ||
                (platform === "youtube" && !selectedYtAccount?.authorized)
              }
              onClick={() => void handlePublish(true)}
            >
              {submitting
                ? "Publishing to YouTube..."
                : `Publish Now to ${platform === "youtube" ? "YouTube Shorts" : "Instagram"}`}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
import ProjectRules from "./ProjectRules";
