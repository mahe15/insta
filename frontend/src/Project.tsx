import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Calendar,
  CalendarClock,
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
  ListOrdered,
  Play,
  RefreshCw,
  Scissors,
  Search,
  Send,
  Settings2,
  Share2,
  Sparkles,
  Square,
  TriangleAlert,
  X,
  Youtube,
} from "lucide-react";
import { api, dateTime, providerName, seconds } from "./api";
import type { Clip, Job, YouTubeConnections, ScheduleAllResult } from "./types";
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
import ProjectRules from "./ProjectRules";

const categories = {
  cinematic_epic: "Cinematic / Epic",
  emotional_sad: "Emotional / Sad",
  suspense_thriller: "Suspense / Thriller",
  energetic_hype: "Energetic / Hype",
  chill_ambient: "Chill / Ambient",
  phonk: "Phonk",
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
    [publishClip, setPublishClip] = useState<Clip | null>(null),
    [scheduleAllOpen, setScheduleAllOpen] = useState(false);
  const job = query.data,
    clips = job?.analysis?.clips || [],
    renderedClips = clips.filter((c) => Boolean(c.video)),
    clip = clips.find((c) => c.id === current) || clips[0];
  const isClipLiveOnYt = (c: Clip) =>
    Boolean(
      c.publications?.some(
        (p) => (p.platform === "youtube" || !p.platform) && p.state === "published",
      ),
    );
  const liveYtClips = renderedClips.filter(isClipLiveOnYt);
  const schedulableClips = renderedClips.filter((c) => !isClipLiveOnYt(c));
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
          {renderedClips.length > 0 &&
            (schedulableClips.length > 0 ? (
              <Button
                icon={CalendarClock}
                variant="primary"
                className="btn-schedule-all-hero"
                onClick={() => setScheduleAllOpen(true)}
              >
                Schedule all ({schedulableClips.length})
              </Button>
            ) : (
              <Button
                icon={CheckCheck}
                variant="ghost"
                disabled
                className="btn-all-live-hero"
                title="All rendered clips are already live on YouTube"
              >
                All clips live ({liveYtClips.length})
              </Button>
            ))}
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
            <div className="shortlist-heading-btns">
              {renderedClips.length > 0 &&
                (schedulableClips.length > 0 ? (
                  <button
                    type="button"
                    className="shortlist-schedule-all-btn"
                    title={`Schedule ${schedulableClips.length} remaining clips with custom interval`}
                    onClick={() => setScheduleAllOpen(true)}
                  >
                    <CalendarClock size={13} />
                    <span>Schedule all ({schedulableClips.length})</span>
                  </button>
                ) : (
                  <span
                    className="shortlist-all-live-badge"
                    title="All rendered clips are already published on YouTube"
                  >
                    <CheckCheck size={12} /> All live
                  </span>
                ))}
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
                      {c.publications?.some((p) => p.state === "queued") ? (
                        <span
                          className="shortlist-scheduled-badge"
                          title={(() => {
                            const qp = c.publications.find((p) => p.state === "queued");
                            return qp?.due
                              ? `Scheduled for ${new Date(qp.due * 1000).toLocaleString()}`
                              : "Scheduled in queue";
                          })()}
                        >
                          <Clock3 size={11} /> Scheduled
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
      <ScheduleAllModal
        job={job}
        renderedClips={renderedClips}
        open={scheduleAllOpen}
        setOpen={setScheduleAllOpen}
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
            {clip.publications
              ?.filter((p) => p.state === "queued")
              .map((pub) => (
                <div key={pub.id} className="clip-scheduled-banner">
                  <div className="scheduled-banner-left">
                    <Clock3 size={13} className="scheduled-clock-icon" />
                    <strong>Scheduled for release:</strong>
                    <span>
                      {pub.due
                        ? new Date(pub.due * 1000).toLocaleString([], {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : "Queued"}
                    </span>
                  </div>
                  <span className="scheduled-platform-pill">
                    {pub.platform === "youtube" ? "YouTube Shorts" : "Instagram"}
                  </span>
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
          max="1"
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

function ScheduleAllModal({
  job,
  renderedClips,
  open,
  setOpen,
}: {
  job: Job;
  renderedClips: Clip[];
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
  const [privacy, setPrivacy] = useState("public");
  const [gapHours, setGapHours] = useState(2.0);
  const [startMode, setStartMode] = useState<"now" | "custom">("now");
  const [customStartTime, setCustomStartTime] = useState(() => {
    const d = new Date(Date.now() + 3600 * 1000);
    d.setMinutes(Math.ceil(d.getMinutes() / 15) * 15, 0, 0);
    const tzOffset = d.getTimezoneOffset() * 60000;
    return new Date(d.getTime() - tzOffset).toISOString().slice(0, 16);
  });
  const [submitting, setSubmitting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [scheduleResult, setScheduleResult] = useState<ScheduleAllResult | null>(null);

  const GAP_PRESETS = [1, 2, 3, 4, 6, 12, 24];

  useEffect(() => {
    if (open) {
      setScheduleResult(null);
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
  }, [open, connectionsQuery.data]);

  const ytAccounts = connectionsQuery.data?.accounts || [];
  const selectedYtAccount = ytAccounts.find((a) => a.key === account);

  const nowSec = Math.floor(Date.now() / 1000);
  const isClipLive = (c: Clip) => {
    return Boolean(
      c.publications?.some((p) => {
        const plat = (p.platform || "youtube").toLowerCase();
        const targetPlat = platform.toLowerCase();
        const isMatch =
          (targetPlat === "youtube" && (plat === "youtube" || plat === "yt")) ||
          (targetPlat === "instagram" && (plat === "instagram" || plat === "ig")) ||
          plat === targetPlat;
        return isMatch && p.state === "published";
      }),
    );
  };

  const skippedLiveClips = renderedClips.filter(isClipLive);
  const schedulableClips = renderedClips.filter((c) => !isClipLive(c));

  const baseSec =
    startMode === "now"
      ? nowSec
      : customStartTime
        ? Math.floor(new Date(customStartTime).getTime() / 1000)
        : nowSec;
  const safeGap = Math.max(0.1, Number(gapHours) || 2.0);
  const gapSec = Math.round(safeGap * 3600);

  const timelineItems = schedulableClips.map((c, idx) => {
    const dueSec = baseSec + idx * gapSec;
    const dateObj = new Date(dueSec * 1000);
    const timeFormatted = dateObj.toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
    });
    const dateFormatted = dateObj.toLocaleDateString([], {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
    const offsetLabel =
      idx === 0
        ? startMode === "now"
          ? `Immediate (Clip #${c.id})`
          : `Start (Clip #${c.id})`
        : `+${(idx * safeGap).toFixed(1).replace(/\.0$/, "")}h`;
    return {
      clip: c,
      dueSec,
      timeFormatted,
      dateFormatted,
      offsetLabel,
    };
  });

  const totalSpanHours =
    schedulableClips.length > 1
      ? ((schedulableClips.length - 1) * safeGap).toFixed(1).replace(/\.0$/, "")
      : "0";
  const finalClip =
    timelineItems.length > 0 ? timelineItems[timelineItems.length - 1] : null;

  const hasQueuedClips = schedulableClips.some((c) =>
    c.publications?.some((p) => p.state === "queued"),
  );

  async function handleScheduleAll() {
    if (!schedulableClips.length) {
      notify("No remaining clips to schedule. All rendered clips are already live.", true);
      return;
    }
    setSubmitting(true);
    try {
      let start_time: number | undefined = undefined;
      if (startMode === "custom" && customStartTime) {
        start_time = Math.floor(new Date(customStartTime).getTime() / 1000);
      }
      const res = await api<ScheduleAllResult>(
        `/jobs/${job.id}/schedule-all`,
        "POST",
        {
          platform,
          account,
          gap_hours: safeGap,
          publish_first_now: startMode === "now",
          start_time,
          privacy,
        },
      );
      refresh();
      setScheduleResult(res);
      notify(res.message || `Scheduled ${res.count} clips successfully!`);
    } catch (err) {
      notify((err as Error).message, true);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCancelAll() {
    if (
      !confirm(
        "Are you sure you want to cancel all currently scheduled clips for this project?",
      )
    )
      return;
    setCancelling(true);
    try {
      const res = await api<{ ok: boolean; cancelled: number; message: string }>(
        `/jobs/${job.id}/schedule/cancel-all`,
        "POST",
      );
      refresh();
      notify(res.message || "Scheduled campaign cancelled.");
      setOpen(false);
    } catch (err) {
      notify((err as Error).message, true);
    } finally {
      setCancelling(false);
    }
  }

  return (
    <Modal
      open={open}
      onOpenChange={(v: boolean) => {
        if (!submitting && !cancelling) setOpen(v);
      }}
      title="Schedule All Clips"
      description={
        skippedLiveClips.length > 0
          ? `Queue ${schedulableClips.length} remaining clips for automated staggered publishing (${skippedLiveClips.length} already live on ${platform === "youtube" ? "YouTube" : "Instagram"} skipped).`
          : `Queue all ${renderedClips.length} rendered moments for automated staggered publishing.`
      }
    >
      {scheduleResult ? (
        <div className="schedule-success-card">
          <div className="schedule-success-icon-badge">
            <CheckCircle2 size={40} color="#059669" />
          </div>
          <h3>Campaign Scheduled!</h3>
          <p className="schedule-success-sub">
            All <strong>{scheduleResult.count} clips</strong> have been queued
            for release on{" "}
            <strong>
              {scheduleResult.channel_title || scheduleResult.account}
            </strong>{" "}
            with a <strong>{scheduleResult.gap_hours} hour interval</strong>.
          </p>

          {scheduleResult.platform === "youtube" && (
            <div className="schedule-cloud-notice">
              <Sparkles size={16} color="#0284c7" />
              <span>
                <strong>Uploaded &amp; Scheduled on YouTube Cloud:</strong> Clips are already uploaded to YouTube Studio with <code>publishAt</code> timestamps. YouTube will publish each Short automatically at its scheduled interval. You can close Cliper and turn off your PC safely.
              </span>
            </div>
          )}

          {scheduleResult.skipped_live_count && scheduleResult.skipped_live_count > 0 ? (
            <div className="schedule-success-skipped-banner">
              <CheckCheck size={14} color="#059669" />
              <span>
                {scheduleResult.skipped_live_count} live clip{scheduleResult.skipped_live_count > 1 ? "s were" : " was"} already live on {scheduleResult.platform === "youtube" ? "YouTube" : "Instagram"} and omitted.
              </span>
            </div>
          ) : null}

          <div className="schedule-success-timeline">
            {scheduleResult.items.map((item, idx) => {
              const d = new Date(item.due * 1000);
              return (
                <div key={item.publication_id} className="schedule-success-row">
                  <span className="success-clip-idx">Clip #{item.clip_id}</span>
                  <strong className="success-clip-title">{item.title}</strong>
                  <span className="success-clip-due">
                    {d.toLocaleDateString([], {
                      month: "short",
                      day: "numeric",
                    })}{" "}
                    at{" "}
                    {d.toLocaleTimeString([], {
                      hour: "numeric",
                      minute: "2-digit",
                    })}
                  </span>
                  {item.url && (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noreferrer"
                      className="schedule-item-yt-link"
                      title="Open on YouTube"
                    >
                      <ExternalLink size={11} />
                      Shorts
                    </a>
                  )}
                  <span className="success-clip-badge">
                    {idx === 0
                      ? "First"
                      : `+${(idx * scheduleResult.gap_hours).toFixed(1).replace(/\.0$/, "")}h`}
                  </span>
                </div>
              );
            })}
          </div>

          <div className="success-actions">
            <Button variant="primary" onClick={() => setOpen(false)}>
              Done
            </Button>
          </div>
        </div>
      ) : (
        <div className="schedule-modal-body">
          {/* Platform Picker */}
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

          {/* Destination channel */}
          {platform === "youtube" ? (
            <div className="destination-account-card">
              <Field
                label="Target YouTube Channel"
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
                <>
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
                        Direct YouTube-Side Scheduling (publishAt) · YouTube Cloud Releases
                      </span>
                    </div>
                  </div>
                  <div className="youtube-schedule-info-box">
                    <Sparkles size={16} className="info-box-icon" />
                    <div>
                      <strong>YouTube-Side Cloud Scheduling (Not Local PC)</strong>
                      <p>
                        All {schedulableClips.length} rendered videos are uploaded directly to YouTube now with YouTube's native <code>publishAt</code> timer. YouTube's cloud servers publish each Short automatically at your {safeGap}h interval. You do NOT need to keep your PC on or keep Cliper open!
                      </p>
                    </div>
                  </div>
                </>
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

          {/* Gap Configuration */}
          <div className="schedule-section-card">
            <div className="schedule-section-header">
              <div className="section-title-wrap">
                <Clock3 size={16} className="section-icon" />
                <div>
                  <strong>Interval Between Clips (Gap)</strong>
                  <span className="section-sub">
                    Default is 2 hours. If 5 clips, every clip will be scheduled
                    with a 2-hour spacing.
                  </span>
                </div>
              </div>
              <span className="gap-current-badge">{safeGap}h Gap</span>
            </div>

            <div className="gap-presets-bar">
              {GAP_PRESETS.map((hrs) => (
                <button
                  key={hrs}
                  type="button"
                  className={`gap-preset-pill ${safeGap === hrs ? "active" : ""}`}
                  onClick={() => setGapHours(hrs)}
                >
                  {hrs}h {hrs === 2 ? "(Default)" : ""}
                </button>
              ))}
            </div>

            <div className="gap-custom-input-row">
              <label htmlFor="custom-gap-input">Custom interval (hours):</label>
              <div className="gap-input-wrap">
                <input
                  id="custom-gap-input"
                  type="number"
                  min="0.1"
                  max="168"
                  step="0.5"
                  value={gapHours}
                  onChange={(e) =>
                    setGapHours(Math.max(0.1, Number(e.target.value) || 2.0))
                  }
                />
                <span className="gap-unit">hours</span>
              </div>
            </div>
          </div>

          {/* Start Timing Options */}
          <div className="schedule-section-card">
            <div className="schedule-section-header">
              <div className="section-title-wrap">
                <Calendar size={16} className="section-icon" />
                <div>
                  <strong>Start Timing</strong>
                  <span className="section-sub">
                    Choose when the first clip should be published.
                  </span>
                </div>
              </div>
            </div>

            <div className="timing-options-grid">
              <label
                className={`timing-option-card ${startMode === "now" ? "selected" : ""}`}
              >
                <input
                  type="radio"
                  name="startMode"
                  value="now"
                  checked={startMode === "now"}
                  onChange={() => setStartMode("now")}
                />
                <div>
                  <strong>Publish 1st clip now</strong>
                  <span>
                    Clip #1 goes live immediately, subsequent clips every{" "}
                    {safeGap}h
                  </span>
                </div>
              </label>

              <label
                className={`timing-option-card ${startMode === "custom" ? "selected" : ""}`}
              >
                <input
                  type="radio"
                  name="startMode"
                  value="custom"
                  checked={startMode === "custom"}
                  onChange={() => setStartMode("custom")}
                />
                <div>
                  <strong>Schedule start date & time</strong>
                  <span>
                    First clip starts at chosen time, following clips every{" "}
                    {safeGap}h
                  </span>
                </div>
              </label>
            </div>

            {startMode === "custom" && (
              <div className="custom-datetime-wrap">
                <Field
                  label="Campaign Start Date & Time"
                  hint="Local system time"
                >
                  <input
                    type="datetime-local"
                    value={customStartTime}
                    onChange={(e) => setCustomStartTime(e.target.value)}
                  />
                </Field>
              </div>
            )}
          </div>

          {/* Privacy Visibility for YouTube */}
          {platform === "youtube" && (
            <Field label="YouTube Privacy Visibility">
              <select
                value={privacy}
                onChange={(e) => setPrivacy(e.target.value)}
              >
                <option value="public">Public (Immediate subscriber reach)</option>
                <option value="unlisted">Unlisted (Shareable link only)</option>
                <option value="private">Private (Draft)</option>
              </select>
            </Field>
          )}

          {/* Skip banner for already live clips */}
          {skippedLiveClips.length > 0 && schedulableClips.length > 0 && (
            <div className="schedule-live-skip-banner">
              <div className="skip-banner-header">
                <CheckCheck size={16} className="skip-banner-icon" />
                <div>
                  <strong>
                    {skippedLiveClips.length} clip{skippedLiveClips.length > 1 ? "s" : ""} already live on {platform === "youtube" ? "YouTube" : "Instagram"} will be skipped
                  </strong>
                  <p className="skip-banner-sub">
                    Already published clips are automatically omitted from scheduling to prevent duplicate posts.
                  </p>
                </div>
              </div>
              <div className="skip-clips-tags">
                {skippedLiveClips.map((c) => (
                  <span
                    key={c.id}
                    className="skip-clip-pill"
                    title={`Clip #${c.id} is already live`}
                  >
                    <span className="live-dot" /> Clip #{c.id}: {c.title || `Moment ${c.id}`}
                  </span>
                ))}
              </div>
            </div>
          )}

          {schedulableClips.length === 0 ? (
            <div className="all-live-notice-card">
              <div className="all-live-icon-wrap">
                <CheckCircle2 size={36} color="#059669" />
              </div>
              <h3>All {renderedClips.length} clips are already live!</h3>
              <p>
                Every rendered clip in this project has already been published to{" "}
                <strong>{platform === "youtube" ? "YouTube Shorts" : "Instagram Reels"}</strong>.
                There are no remaining clips to schedule.
              </p>
              <div className="all-live-clips-list">
                {skippedLiveClips.map((c) => (
                  <div key={c.id} className="all-live-clip-row">
                    <span className="live-dot" />
                    <strong>Clip #{c.id}</strong>
                    <span>{c.title || `Moment ${c.id}`}</span>
                    <span className="live-status-pill">Live</span>
                  </div>
                ))}
              </div>
              <div className="modal-footer schedule-footer">
                <Button variant="primary" onClick={() => setOpen(false)}>
                  Done
                </Button>
              </div>
            </div>
          ) : (
            <>
              {/* Live Campaign Timeline Preview Matrix */}
              <div className="schedule-timeline-preview">
                <div className="timeline-preview-header">
                  <div className="timeline-title">
                    <ListOrdered size={15} />
                    <strong>
                      Campaign Timeline Preview ({schedulableClips.length} Clips)
                    </strong>
                  </div>
                  <span className="timeline-gap-pill">
                    Gap: {safeGap}h between clips
                  </span>
                </div>

                <div className="timeline-items-list">
                  {timelineItems.map((item, idx) => (
                    <div key={item.clip.id} className="timeline-item-card">
                      <div className="timeline-item-left">
                        <span className="timeline-step-num">#{idx + 1}</span>
                        <div className="timeline-item-info">
                          <span className="timeline-item-title">
                            {item.clip.title || `Clip #${item.clip.id}`}
                          </span>
                          <small className="timeline-item-dur">
                            {Math.round(item.clip.end - item.clip.start)}s · Score{" "}
                            {item.clip.score}/100
                          </small>
                        </div>
                      </div>
                      <div className="timeline-item-right">
                        <span className="timeline-offset-pill">
                          {item.offsetLabel}
                        </span>
                        <div className="timeline-time-info">
                          <strong>{item.timeFormatted}</strong>
                          <small>{item.dateFormatted}</small>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="schedule-summary-banner">
                  <Sparkles size={16} />
                  <span>
                    Total <strong>{schedulableClips.length} clips</strong> scheduled
                    across <strong>{totalSpanHours} hours</strong>, finishing on{" "}
                    <strong>
                      {finalClip?.dateFormatted} at {finalClip?.timeFormatted}
                    </strong>
                    .
                  </span>
                </div>
              </div>

              {/* Footer Actions */}
              <div className="modal-footer schedule-footer">
                {hasQueuedClips && (
                  <Button
                    variant="danger"
                    busy={cancelling}
                    disabled={submitting}
                    onClick={() => void handleCancelAll()}
                  >
                    Cancel existing schedule
                  </Button>
                )}
                <div className="footer-right-actions">
                  <Button
                    variant="ghost"
                    onClick={() => setOpen(false)}
                    disabled={submitting || cancelling}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="primary"
                    icon={CalendarClock}
                    busy={submitting}
                    disabled={
                      submitting ||
                      cancelling ||
                      !schedulableClips.length ||
                      (platform === "youtube" && !selectedYtAccount?.authorized)
                    }
                    onClick={() => void handleScheduleAll()}
                  >
                    {submitting
                      ? "Scheduling Clips..."
                      : `Schedule All (${schedulableClips.length} Clips)`}
                  </Button>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </Modal>
  );
}
