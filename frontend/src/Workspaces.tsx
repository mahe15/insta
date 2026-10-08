import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  AudioLines,
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Download,
  FileImage,
  ImagePlus,
  Images,
  Info,
  Layers2,
  Music2,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Search,
  Send,
  Settings2,
  Upload,
  X,
  Youtube,
  ExternalLink,
  MessageSquareQuote,
  RotateCcw,
  SlidersHorizontal,
  Sparkles,
} from "lucide-react";
import { api, dateTime, humanState, upload, when } from "./api";
import type { Carousel, Music, Niche, Publication, PromptInfo } from "./types";
import {
  Badge,
  Button,
  Empty,
  ErrorBox,
  Field,
  IconButton,
  Loading,
  Modal,
  PageHeading,
  SectionTitle,
  Switch,
  useStudio,
} from "./ui";

export function Carousels() {
  const { boot, notify, refresh } = useStudio(),
    [niche, setNiche] = useState(boot.preferences.selected_niche),
    [count, setCount] = useState(1),
    [inputPrompt, setInputPrompt] = useState(""),
    [promptsModalOpen, setPromptsModalOpen] = useState(false),
    [edit, setEdit] = useState(false),
    [scheduleOpen, setScheduleOpen] = useState(false),
    [view, setView] = useState<Carousel["items"][0] | null>(null),
    [slide, setSlide] = useState(0),
    [busy, setBusy] = useState(false);
  const jobs = useQuery({
      queryKey: ["carousels"],
      queryFn: () => api<Carousel[]>("/carousels"),
      refetchInterval: 6000,
    }),
    niches = useQuery({
      queryKey: ["niches"],
      queryFn: () => api<Niche[]>("/niches"),
    });
  const current = niches.data?.find((n) => n.key === niche),
    filtered = (jobs.data || []).filter((j) => j.niche === niche);
  async function generate() {
    setBusy(true);
    try {
      await api("/carousels", "POST", {
        niche,
        count,
        prompt: inputPrompt.trim(),
      });
      setInputPrompt("");
      refresh();
      notify(`${count} carousel${count > 1 ? "s" : ""} queued for production.`);
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  async function toggle(on: boolean) {
    setBusy(true);
    try {
      await api("/preferences", "PUT", { f2_enabled: on });
      refresh();
      notify(
        on ? "Carousel production enabled." : "Carousel production paused.",
      );
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  async function action(id: string, name: string) {
    try {
      await api(`/carousels/${id}/${name}`, "POST");
      refresh();
      notify(
        name === "retry"
          ? "Generation queued again."
          : "Carousel job cancelled.",
      );
    } catch (e) {
      notify((e as Error).message, true);
    }
  }
  return (
    <div className="page carousel-page">
      <PageHeading
        eyebrow="THE CAROUSEL STUDIO"
        title="An idea worth swiping for."
        description="Original stories. A familiar character. A little more depth."
      >
        <Button icon={SlidersHorizontal} onClick={() => setPromptsModalOpen(true)}>
          AI Prompts & Rules
        </Button>
        <Button icon={CalendarDays} onClick={() => setScheduleOpen(true)}>
          Production schedule
        </Button>
      </PageHeading>
      <div className="niche-tabs" role="tablist" aria-label="Carousel niche">
        {Object.entries(boot.niches).map(([key, name], i) => (
          <button
            role="tab"
            aria-selected={key === niche}
            onClick={() => setNiche(key)}
            key={key}
          >
            <span>{String(i + 1).padStart(2, "0")}</span>
            {name}
          </button>
        ))}
      </div>
      <section className="carousel-brief">
        <div className="brief-visual">
          <div className="brief-card back" />
          <div className="brief-card middle" />
          <div className="brief-card front">
            <span>THE {niche.toUpperCase()} SERIES</span>
            <div>
              <i />
              <i />
              <b>
                {current?.config.name?.split(" ").slice(0, 3).join(" ") ||
                  boot.niches[niche]}
              </b>
            </div>
            <small>
              01 / 05 <ArrowRight size={15} />
            </small>
          </div>
        </div>
        <div className="brief-content">
          <span className="eyebrow">YOUR CREATIVE DIRECTION</span>
          <h2>{current?.config.name || boot.niches[niche]}</h2>
          <p>
            {current?.config.brand ||
              "Give this series a point of view. Set the character, visual direction and topics before generating."}
          </p>
          <div className="pillar-chips">
            {current?.config.pillars?.slice(0, 5).map((p) => (
              <span key={p}>{p}</span>
            ))}
          </div>
          <div className="brief-meta">
            <span>
              <FileImage size={14} />
              {current?.reference_ready
                ? "Character reference ready"
                : "Character reference needed"}
            </span>
            <span>
              <Check size={14} />
              QA threshold {current?.config.threshold || 90}
            </span>
          </div>
          <Button icon={Settings2} onClick={() => setEdit(true)}>
            Edit creative brief
          </Button>
        </div>
        <div className="generation-card">
          <span className="eyebrow">NEXT IN YOUR SERIES</span>
          <h3>Make a new carousel.</h3>
          <p>
            Three ideas compete for each output. The strongest stories become
            4–7 slides.
          </p>
          <Field label="Carousels to create">
            <select value={count} onChange={(e) => setCount(+e.target.value)}>
              {[1, 2, 3, 5, 10, 20].map((n) => (
                <option key={n} value={n}>
                  {n} carousel{n > 1 ? "s" : ""}
                </option>
              ))}
            </select>
          </Field>
          <Field
            label="AI Prompt & Creative Guidance"
            hint="Optional. Provide a specific hook, calculation, contrarian angle, or story prompt for the AI to develop into a carousel."
          >
            <div className="prompt-input-container">
              <textarea
                value={inputPrompt}
                onChange={(e) => setInputPrompt(e.target.value)}
                placeholder="e.g. Compare saving $10/day vs investing $10/day over 30 years with visual contrast and compound interest breakdown..."
                rows={3}
                className="prompt-textarea-input"
              />
              <div className="prompt-input-footer">
                <div className="prompt-chips">
                  <span className="chip-label">Quick angles:</span>
                  {[
                    "Daily vs 10 Years",
                    "The Compound Effect",
                    "Common Costly Mistake",
                    "Step-by-step Rule",
                    "Myth vs Reality",
                  ].map((idea) => (
                    <button
                      key={idea}
                      type="button"
                      className="chip-btn"
                      onClick={() =>
                        setInputPrompt((prev) =>
                          prev ? `${prev} · Angle: ${idea}` : `Angle: ${idea}`
                        )
                      }
                    >
                      +{idea}
                    </button>
                  ))}
                  {inputPrompt && (
                    <button
                      type="button"
                      className="chip-btn clear"
                      onClick={() => setInputPrompt("")}
                    >
                      Clear
                    </button>
                  )}
                </div>
              </div>
            </div>
          </Field>
          <Button
            icon={Plus}
            variant="primary full"
            busy={busy}
            disabled={!boot.preferences.f2_enabled || !current?.reference_ready}
            onClick={() => void generate()}
          >
            Create carousels
          </Button>
          <button
            type="button"
            className="customize-prompts-link"
            onClick={() => setPromptsModalOpen(true)}
          >
            <Sparkles size={13} />
            Edit Carousel AI Prompts & Style Rules
          </button>
          <Switch
            label="Production enabled"
            checked={boot.preferences.f2_enabled}
            onChange={(v) => void toggle(v)}
            disabled={busy}
          />
          <small>
            Image generation uses your existing Gemini browser session.
          </small>
        </div>
      </section>
      <SectionTitle
        title="Your series, in progress"
        note={`${filtered.length} production jobs in this niche.`}
      />
      {jobs.error ? (
        <ErrorBox error={jobs.error} />
      ) : jobs.isPending ? (
        <Loading />
      ) : !filtered.length ? (
        <Empty
          icon={Images}
          title="The first chapter is yours."
          description="Configure your reference character and create the first carousel in this series."
          action={
            <Button onClick={() => setEdit(true)} icon={Settings2}>
              Set creative direction
            </Button>
          }
        />
      ) : (
        <div className="carousel-jobs">
          {filtered.map((job) => (
            <article key={job.id} className="carousel-job">
              <header>
                <div>
                  <span className="eyebrow">
                    SERIES RUN · {job.id.slice(0, 6).toUpperCase()}
                  </span>
                  <h3>
                    {job.count} carousel{job.count > 1 ? "s" : ""}{" "}
                    <span>· {when(job.created)}</span>
                  </h3>
                </div>
                <Badge state={job.state} />
              </header>
              {job.prompt && (
                <div className="job-prompt-badge">
                  <MessageSquareQuote size={13} />
                  <span>Prompt: &ldquo;{job.prompt}&rdquo;</span>
                </div>
              )}
              <p className="muted">{job.stage}</p>
              {job.error && <p className="inline-error">{job.error}</p>}
              {job.items.some((i) => i.images.length) ? (
                <div className="carousel-output-grid">
                  {job.items
                    .filter((i) => i.images.length)
                    .map((item) => (
                      <button
                        className="carousel-output"
                        key={item.name}
                        onClick={() => {
                          setView(item);
                          setSlide(0);
                        }}
                      >
                        <div>
                          <img
                            src={item.images[0]}
                            loading="lazy"
                            alt={item.plan.hook || "Carousel cover"}
                          />
                          <span>
                            <Layers2 size={13} />
                            {item.images.length} slides
                          </span>
                        </div>
                        <h4>
                          {item.plan.hook || item.plan.topic || "Carousel"}
                        </h4>
                        <p>
                          Review the complete story <ArrowUpRight size={13} />
                        </p>
                      </button>
                    ))}
                </div>
              ) : (
                <div className="carousel-progress">
                  <Layers2 size={20} />
                  <span>
                    Finished slides will appear here as the story takes shape.
                  </span>
                </div>
              )}
              <div className="job-actions">
                {job.state === "failed" && (
                  <Button
                    icon={RefreshCw}
                    onClick={() => void action(job.id, "retry")}
                  >
                    Retry generation
                  </Button>
                )}
                {["queued", "running", "failed"].includes(job.state) && (
                  <Button
                    variant="ghost"
                    onClick={() => void action(job.id, "cancel")}
                  >
                    Cancel generation
                  </Button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
      {current && (
        <NicheEditor
          key={niche}
          niche={current}
          open={edit}
          setOpen={setEdit}
        />
      )}
      <ScheduleEditor
        niche={niche}
        open={scheduleOpen}
        setOpen={setScheduleOpen}
      />
      <Modal
        open={!!view}
        onOpenChange={(v) => {
          if (!v) setView(null);
        }}
        title={view?.plan.hook || "Carousel review"}
        description="Review every slide before approving it in Publishing."
        wide
      >
        {view && (
          <div className="carousel-review">
            <div className="slide-stage">
              <img
                src={view.images[slide]}
                alt={view.plan.slides?.[slide]?.text || `Slide ${slide + 1}`}
              />
            </div>
            <div className="slide-pagination">
              <IconButton
                icon={ChevronLeft}
                label="Previous slide"
                disabled={slide === 0}
                onClick={() => setSlide(slide - 1)}
              />
              <span>
                {slide + 1} / {view.images.length}
              </span>
              <IconButton
                icon={ChevronRight}
                label="Next slide"
                disabled={slide === view.images.length - 1}
                onClick={() => setSlide(slide + 1)}
              />
              <a className="button" href={view.images[slide]} download>
                <Download size={14} />
                Download slide
              </a>
            </div>
            {view.plan.topic && (
              <div className="review-meta-item">
                <span className="eyebrow">AI TOPIC / ANGLE</span>
                <p>{view.plan.topic}</p>
              </div>
            )}
            <p>{view.plan.caption}</p>
          </div>
        )}
      </Modal>
      <CarouselPromptsModal
        open={promptsModalOpen}
        setOpen={setPromptsModalOpen}
      />
    </div>
  );
}

function CarouselPromptsModal({
  open,
  setOpen,
}: {
  open: boolean;
  setOpen: (v: boolean) => void;
}) {
  const { notify } = useStudio();
  const promptsQuery = useQuery({
    queryKey: ["prompts"],
    queryFn: () => api<PromptInfo[]>("/prompts"),
    enabled: open,
  });
  const [selectedKey, setSelectedKey] = useState<string>("carousel_editor");
  const [draftContent, setDraftContent] = useState<string>("");
  const [busy, setBusy] = useState(false);

  const carouselPrompts = (promptsQuery.data || []).filter(
    (p) => p.category === "carousels"
  );
  const activePrompt =
    carouselPrompts.find((p) => p.key === selectedKey) || carouselPrompts[0];

  useEffect(() => {
    if (activePrompt) {
      setDraftContent(activePrompt.value);
      if (selectedKey !== activePrompt.key) {
        setSelectedKey(activePrompt.key);
      }
    }
  }, [activePrompt?.key, activePrompt?.value]);

  async function handleSave() {
    if (!activePrompt) return;
    setBusy(true);
    try {
      await api(`/prompts/${activePrompt.key}`, "PUT", {
        value: draftContent,
      });
      await promptsQuery.refetch();
      notify(`Saved "${activePrompt.title}" prompt successfully.`);
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  async function handleReset() {
    if (!activePrompt) return;
    setBusy(true);
    try {
      await api(`/prompts/${activePrompt.key}/reset`, "POST");
      await promptsQuery.refetch();
      notify(`Reset "${activePrompt.title}" to factory default.`);
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
      title="Carousel AI Prompts & Style Rules"
      description="Fine-tune how Gemini brainstorms angles, crafts storyline scripts, and prompts slide illustrations."
      wide
    >
      {promptsQuery.isLoading ? (
        <Loading />
      ) : (
        <div className="carousel-prompts-modal-content">
          <div className="prompt-selector-tabs">
            {carouselPrompts.map((p) => (
              <button
                key={p.key}
                type="button"
                className={`prompt-tab-btn ${
                  (activePrompt?.key || selectedKey) === p.key ? "active" : ""
                }`}
                onClick={() => {
                  setSelectedKey(p.key);
                  setDraftContent(p.value);
                }}
              >
                <span>{p.title}</span>
                {p.is_custom && (
                  <span className="mod-dot" title="Customized" />
                )}
              </button>
            ))}
          </div>

          {activePrompt && (
            <div className="prompt-modal-editor-body">
              <div className="prompt-meta-header">
                <div>
                  <h4>{activePrompt.title}</h4>
                  <p className="muted">{activePrompt.description}</p>
                </div>
                {activePrompt.is_custom ? (
                  <span className="badge-modified">Customized</span>
                ) : (
                  <span className="badge-default">Factory Default</span>
                )}
              </div>

              {activePrompt.variables.length > 0 && (
                <div className="prompt-variables-bar">
                  <span className="var-label">Available variables (click to insert):</span>
                  <div className="var-tags">
                    {activePrompt.variables.map((v) => (
                      <button
                        key={v}
                        type="button"
                        className="var-tag"
                        title={`Insert {${v}}`}
                        onClick={() => {
                          setDraftContent((prev) => `${prev}{${v}}`);
                        }}
                      >
                        <code>{`{${v}}`}</code>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <Field label="System Prompt Template">
                <textarea
                  className="prompt-textarea mono"
                  rows={14}
                  value={draftContent}
                  onChange={(e) => setDraftContent(e.target.value)}
                  placeholder="Enter prompt template..."
                />
              </Field>

              <div className="prompt-modal-actions">
                <div className="left-actions">
                  {activePrompt.is_custom && (
                    <Button
                      variant="ghost"
                      icon={RotateCcw}
                      disabled={busy}
                      onClick={() => void handleReset()}
                    >
                      Reset to Default
                    </Button>
                  )}
                </div>
                <div className="right-actions">
                  <Button variant="ghost" onClick={() => setOpen(false)}>
                    Close
                  </Button>
                  <Button
                    variant="primary"
                    busy={busy}
                    disabled={draftContent === activePrompt.value}
                    onClick={() => void handleSave()}
                  >
                    Save Prompt
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

function NicheEditor({
  niche,
  open,
  setOpen,
}: {
  niche: Niche;
  open: boolean;
  setOpen: (v: boolean) => void;
}) {
  const { notify, refresh } = useStudio(),
    [draft, setDraft] = useState(niche.config),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    if (open) setDraft(niche.config);
  }, [open]);
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api(`/niches/${niche.key}`, "PUT", draft);
      refresh();
      setOpen(false);
      notify("Creative direction saved for new carousel jobs.");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  async function reference(file: File) {
    setBusy(true);
    try {
      const result = await upload(`/niches/${niche.key}/upload`, file);
      setDraft((d) => ({
        ...d,
        character_path: result.character_path as string,
      }));
      refresh();
      notify("Character reference uploaded.");
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
      title="Give your series a point of view."
      description={niche.label}
      wide
    >
      <form onSubmit={save}>
        <div className="form-grid">
          <Field label="Series name">
            <input
              required
              value={draft.name || ""}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            />
          </Field>
          <Field label="Instagram account key">
            <input
              value={draft.instagram_account || niche.key}
              onChange={(e) =>
                setDraft({ ...draft, instagram_account: e.target.value })
              }
            />
          </Field>
        </div>
        <Field label="Visual & editorial direction">
          <textarea
            rows={4}
            value={draft.brand || ""}
            onChange={(e) => setDraft({ ...draft, brand: e.target.value })}
          />
        </Field>
        <div className="form-grid">
          <Field label="Content pillars" hint="One topic per line.">
            <textarea
              rows={5}
              value={(draft.pillars || []).join("\n")}
              onChange={(e) =>
                setDraft({ ...draft, pillars: e.target.value.split("\n") })
              }
            />
          </Field>
          <Field label="Topics to avoid" hint="One exclusion per line.">
            <textarea
              rows={5}
              value={(draft.banned_topics || []).join("\n")}
              onChange={(e) =>
                setDraft({
                  ...draft,
                  banned_topics: e.target.value.split("\n"),
                })
              }
            />
          </Field>
        </div>
        <div className="reference-upload">
          <FileImage size={22} />
          <div>
            <strong>Reference character</strong>
            <small>
              {draft.character_path
                ? "A local image is configured. Upload to replace it."
                : "Upload an original character image for this niche."}
            </small>
          </div>
          <label className="button">
            <Upload size={14} />
            Upload image
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp"
              disabled={busy}
              onChange={(e) => {
                if (e.target.files?.[0]) void reference(e.target.files[0]);
              }}
            />
          </label>
        </div>
        <Field
          label="Character image path"
          hint="Alternatively, use a full path to your local reference image."
        >
          <input
            value={draft.character_path || ""}
            onChange={(e) =>
              setDraft({ ...draft, character_path: e.target.value })
            }
          />
        </Field>
        <div className="form-grid">
          <Field label="Quality threshold">
            <input
              type="number"
              min={70}
              max={100}
              value={draft.threshold || 90}
              onChange={(e) =>
                setDraft({ ...draft, threshold: +e.target.value })
              }
            />
          </Field>
          <Field
            label="Research feeds"
            hint="HTTPS RSS feeds, one per line. Leave blank for evergreen topics."
          >
            <textarea
              rows={2}
              value={(draft.research_feeds || []).join("\n")}
              onChange={(e) =>
                setDraft({
                  ...draft,
                  research_feeds: e.target.value.split("\n").filter(Boolean),
                })
              }
            />
          </Field>
        </div>
        <div className="modal-footer">
          <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button variant="primary" icon={Check} busy={busy}>
            Save creative brief
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function ScheduleEditor({
  niche,
  open,
  setOpen,
}: {
  niche: string;
  open: boolean;
  setOpen: (v: boolean) => void;
}) {
  const { boot, notify, refresh } = useStudio(),
    [enabled, setEnabled] = useState(false),
    [mode, setMode] = useState("daily"),
    [clock, setClock] = useState("20:00"),
    [zone, setZone] = useState("Asia/Kolkata"),
    [hours, setHours] = useState(24),
    [days, setDays] = useState<number[]>([]),
    [busy, setBusy] = useState(false);
  const query = useQuery({
    queryKey: ["schedules"],
    queryFn: () =>
      api<
        {
          niche: string;
          enabled: number;
          daily_time: string | null;
          timezone: string;
          interval_hours: number;
          weekdays: string;
          next_due: number;
        }[]
      >("/schedules"),
    enabled: open,
  });
  useEffect(() => {
    const s = query.data?.find((s) => s.niche === niche);
    if (s) {
      setEnabled(!!s.enabled);
      setClock(s.daily_time || "20:00");
      setZone(s.timezone);
      setHours(s.interval_hours);
      setDays(JSON.parse(s.weekdays));
      setMode(s.daily_time ? "daily" : "interval");
    } else {
      setEnabled(false);
    }
  }, [query.data, niche]);
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api(`/schedules/${niche}`, "PUT", {
        enabled,
        hours,
        daily_time: mode === "daily" ? clock : null,
        zone,
        weekdays: days,
      });
      refresh();
      setOpen(false);
      notify(
        "Production schedule saved. Keep an engine running for scheduled work.",
      );
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
      title="A steady rhythm for your series."
      description={boot.niches[niche]}
    >
      <form onSubmit={save}>
        <Switch
          label="Recurring production"
          description="Prepare one carousel for each scheduled time."
          checked={enabled}
          onChange={setEnabled}
        />
        <div className="form-grid">
          <Field label="Schedule type">
            <select value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="daily">Time of day</option>
              <option value="interval">Every few hours</option>
            </select>
          </Field>
          {mode === "daily" ? (
            <Field label="Local time">
              <input
                type="time"
                required
                value={clock}
                onChange={(e) => setClock(e.target.value)}
              />
            </Field>
          ) : (
            <Field label="Interval">
              <select value={hours} onChange={(e) => setHours(+e.target.value)}>
                {[3, 6, 12, 24, 48, 72].map((n) => (
                  <option key={n} value={n}>
                    Every {n} hours
                  </option>
                ))}
              </select>
            </Field>
          )}
        </div>
        <Field label="Timezone">
          <input
            value={zone}
            onChange={(e) => setZone(e.target.value)}
            placeholder="Asia/Kolkata"
          />
        </Field>
        {mode === "daily" && (
          <div className="weekday-field">
            <span>
              Days <small>None selected means every day.</small>
            </span>
            <div>
              {["M", "T", "W", "T", "F", "S", "S"].map((day, i) => (
                <button
                  type="button"
                  aria-label={
                    [
                      "Monday",
                      "Tuesday",
                      "Wednesday",
                      "Thursday",
                      "Friday",
                      "Saturday",
                      "Sunday",
                    ][i]
                  }
                  aria-pressed={days.includes(i)}
                  className={days.includes(i) ? "selected" : ""}
                  key={i}
                  onClick={() =>
                    setDays(
                      days.includes(i)
                        ? days.filter((d) => d !== i)
                        : [...days, i],
                    )
                  }
                >
                  {day}
                </button>
              ))}
            </div>
          </div>
        )}
        <div className="info-note">
          <Clock3 size={16} />
          <span>
            Production can start one hour before the target time. Auto-publish
            must be enabled separately; otherwise the finished post waits for
            approval.
          </span>
        </div>
        <div className="modal-footer">
          <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button variant="primary" icon={Check} busy={busy}>
            Save schedule
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function Publishing() {
  const { notify, refresh } = useStudio(),
    [filter, setFilter] = useState("approval"),
    [selected, setSelected] = useState<Publication | null>(null),
    [caption, setCaption] = useState(""),
    [due, setDue] = useState(""),
    [busy, setBusy] = useState(false),
    [confirm, setConfirm] = useState<string | null>(null),
    [slide, setSlide] = useState(0);
  const query = useQuery({
      queryKey: ["publications"],
      queryFn: () => api<Publication[]>("/publications"),
      refetchInterval: 5000,
    }),
    posts = query.data || [],
    filtered = posts.filter(
      (p) =>
        filter === "all" ||
        (filter === "approval" &&
          ["approval", "failed", "uncertain"].includes(p.state)) ||
        (filter === "queued" &&
          ["queued", "preparing", "publishing"].includes(p.state)) ||
        (filter === "published" && p.state === "published"),
    );
  function review(post: Publication) {
    setSelected(post);
    setCaption(post.caption);
    const d = new Date(post.due * 1000);
    setDue(
      new Date(d.getTime() - d.getTimezoneOffset() * 60000)
        .toISOString()
        .slice(0, 16),
    );
    setSlide(0);
  }
  async function save() {
    if (!selected) return;
    setBusy(true);
    try {
      await api(`/publications/${selected.id}`, "PUT", {
        caption,
        due: due ? new Date(due).getTime() / 1000 : null,
      });
      refresh();
      setSelected({
        ...selected,
        caption,
        due: new Date(due).getTime() / 1000,
      });
      notify("Publication details saved.");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  async function decide(action: string) {
    if (!selected) return;
    setBusy(true);
    try {
      await api(`/publications/${selected.id}/${action}`, "POST");
      refresh();
      setSelected(null);
      notify(
        action === "approve"
          ? "Publication approved and queued to publish now."
          : action === "schedule"
            ? "Post scheduled for the saved time."
            : "Publication rejected.",
      );
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
      setConfirm(null);
    }
  }
  const dirty =
    selected &&
    (caption !== selected.caption ||
      due !==
        (() => {
          const d = new Date(selected.due * 1000);
          return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
            .toISOString()
            .slice(0, 16);
        })());
  return (
    <div className="page publishing-page">
      <PageHeading
        eyebrow="THE FINAL SAY"
        title="Ready when you are."
        description="Review the story, choose the moment, send it out into the world."
      />
      <div className="publication-overview">
        <div>
          <span>NEEDS YOUR EYE</span>
          <strong>
            {posts
              .filter((p) => p.state === "approval")
              .length.toString()
              .padStart(2, "0")}
          </strong>
          <p>Awaiting approval</p>
        </div>
        <div>
          <span>UP NEXT</span>
          <strong>
            {posts
              .filter((p) => p.state === "queued")
              .length.toString()
              .padStart(2, "0")}
          </strong>
          <p>In the publishing queue</p>
        </div>
        <div>
          <span>OUT IN THE WORLD</span>
          <strong>
            {posts
              .filter((p) => p.state === "published")
              .length.toString()
              .padStart(2, "0")}
          </strong>
          <p>Published successfully</p>
        </div>
        <div className="publishing-note">
          <ShieldNote />
        </div>
      </div>
      <div
        className="library-tabs"
        role="tablist"
        aria-label="Publication status"
      >
        {[
          ["approval", "Review inbox"],
          ["queued", "Scheduled"],
          ["published", "Published"],
          ["all", "All posts"],
        ].map(([key, name]) => (
          <button
            role="tab"
            aria-selected={filter === key}
            key={key}
            onClick={() => setFilter(key)}
          >
            {name}
          </button>
        ))}
      </div>
      {query.error ? (
        <ErrorBox error={query.error} />
      ) : query.isPending ? (
        <Loading />
      ) : !filtered.length ? (
        <Empty
          icon={Send}
          title={
            filter === "approval"
              ? "A clear inbox. A little breathing room."
              : "Nothing in this queue yet."
          }
          description="Finished clips and carousels arrive here with their captions, media and publication status."
        />
      ) : (
        <div className="publication-grid">
          {filtered.map((p) => (
            <button
              className="publication-card"
              key={p.id}
              onClick={() => review(p)}
            >
              <div className="publication-media">
                {p.media[0]?.video ? (
                  <video src={p.media[0].url} preload="metadata" muted />
                ) : p.media[0] ? (
                  <img src={p.media[0].url} alt="" loading="lazy" />
                ) : (
                  <Send size={28} />
                )}
                <span
                  className="publication-type"
                  style={
                    p.platform === "youtube"
                      ? { background: "rgba(239, 68, 68, 0.9)", color: "#fff" }
                      : undefined
                  }
                >
                  {p.platform === "youtube" ? (
                    <Youtube size={12} />
                  ) : p.feature === "f1" ? (
                    <Play size={12} />
                  ) : (
                    <Layers2 size={12} />
                  )}{" "}
                  {p.platform === "youtube"
                    ? "SHORTS"
                    : p.feature === "f1"
                      ? "REEL"
                      : `${p.media.length} SLIDES`}
                </span>
              </div>
              <div className="publication-copy">
                <div className="account-small">
                  <span
                    style={
                      p.platform === "youtube"
                        ? {
                            background: "rgba(239, 68, 68, 0.2)",
                            color: "#ef4444",
                          }
                        : undefined
                    }
                  >
                    {p.platform === "youtube"
                      ? "YT"
                      : p.account.slice(0, 1).toUpperCase()}
                  </span>
                  <strong>{p.account}</strong>
                  <span className="small muted">
                    · {p.platform === "youtube" ? "YouTube" : "Instagram"}
                  </span>
                  <ArrowUpRight size={15} />
                </div>
                <p>{p.caption}</p>
                <Badge state={p.state} />
                <div className="publication-date">
                  <Clock3 size={12} />
                  {p.state === "published" && p.published_at
                    ? dateTime(p.published_at)
                    : p.state === "queued"
                      ? dateTime(p.due)
                      : "Ready for your review"}
                  {p.predecessor && p.state === "queued" && (
                    <small>Predecessor spacing applies</small>
                  )}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
      <Modal
        open={!!selected}
        onOpenChange={(v) => {
          if (!v) setSelected(null);
        }}
        title="One last look."
        description={
          selected
            ? `${selected.feature === "f1" ? "Clip" : "Carousel"} → ${selected.account}`
            : ""
        }
        wide
      >
        {selected && (
          <div className="publication-review">
            <div>
              <div className="publication-preview">
                {selected.media[slide]?.video ? (
                  <video controls src={selected.media[slide].url} />
                ) : selected.media[slide] ? (
                  <img
                    src={selected.media[slide].url}
                    alt={`Publication slide ${slide + 1}`}
                  />
                ) : (
                  <Empty
                    icon={FileImage}
                    title="Media unavailable"
                    description="Check the original project files."
                  />
                )}
              </div>
              {selected.media.length > 1 && (
                <div className="slide-pagination">
                  <IconButton
                    icon={ChevronLeft}
                    label="Previous publication slide"
                    disabled={!slide}
                    onClick={() => setSlide(slide - 1)}
                  />
                  <span>
                    {slide + 1} / {selected.media.length}
                  </span>
                  <IconButton
                    icon={ChevronRight}
                    label="Next publication slide"
                    disabled={slide === selected.media.length - 1}
                    onClick={() => setSlide(slide + 1)}
                  />
                </div>
              )}
            </div>
            <div className="publication-edit">
              <Badge state={selected.state} />
              {selected.review_note && (
                <p className="info-note">{selected.review_note}</p>
              )}
              {selected.error && (
                <p className="inline-error">{selected.error}</p>
              )}
              <Field
                label="Caption & hashtags"
                hint="A natural caption and no more than five hashtags."
              >
                <textarea
                  rows={8}
                  maxLength={2200}
                  value={caption}
                  disabled={
                    !["approval", "queued", "failed"].includes(selected.state)
                  }
                  onChange={(e) => setCaption(e.target.value)}
                />
              </Field>
              <Field
                label="Posting time"
                hint="Shown in this browser's timezone. Save the time, then choose Schedule."
              >
                <input
                  type="datetime-local"
                  value={due}
                  disabled={
                    !["approval", "queued", "failed"].includes(selected.state)
                  }
                  onChange={(e) => setDue(e.target.value)}
                />
              </Field>
              {selected.predecessor && (
                <p className="small muted">
                  This post also waits {selected.gap / 3600} hours after its
                  predecessor publishes. Publish now removes that delay.
                </p>
              )}
              {["approval", "queued", "failed"].includes(selected.state) && (
                <>
                  <Button
                    disabled={!dirty}
                    busy={busy}
                    icon={Check}
                    onClick={() => void save()}
                  >
                    Save details
                  </Button>
                  <div className="publication-decisions">
                    <Button
                      variant="primary"
                      icon={Send}
                      disabled={!!dirty}
                      onClick={() => setConfirm("approve")}
                    >
                      Publish now
                    </Button>
                    {selected.state !== "queued" && (
                      <Button
                        icon={CalendarDays}
                        disabled={!!dirty}
                        onClick={() => setConfirm("schedule")}
                      >
                        Schedule
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      onClick={() => setConfirm("reject")}
                    >
                      Reject
                    </Button>
                  </div>
                </>
              )}
              {selected.state === "published" &&
                selected.platform === "youtube" &&
                selected.media_id && (
                  <div
                    className="info-note"
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      background: "rgba(239, 68, 68, 0.1)",
                      borderColor: "rgba(239, 68, 68, 0.3)",
                    }}
                  >
                    <span
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                      }}
                    >
                      <Youtube size={16} color="#ef4444" /> Live on YouTube
                      Shorts
                    </span>
                    <a
                      href={`https://www.youtube.com/shorts/${selected.media_id}`}
                      target="_blank"
                      rel="noreferrer"
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "4px",
                        color: "#ef4444",
                        fontWeight: 600,
                        textDecoration: "underline",
                      }}
                    >
                      Open Short <ExternalLink size={14} />
                    </a>
                  </div>
                )}
              {selected.state === "uncertain" && (
                <div className="info-note">
                  <Info size={16} />
                  <span>
                    The previous publish outcome is unknown. Inspect{" "}
                    {selected.platform === "youtube"
                      ? "YouTube Studio"
                      : "Instagram"}{" "}
                    before resolving it; automatic retries are blocked to
                    prevent duplicates.
                  </span>
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>
      <Modal
        open={!!confirm}
        onOpenChange={(v) => {
          if (!v) setConfirm(null);
        }}
        title={
          confirm === "approve"
            ? "Publish this post now?"
            : confirm === "schedule"
              ? "Schedule this post?"
              : "Reject this publication?"
        }
        description={
          confirm === "approve"
            ? selected?.platform === "youtube"
              ? `This uploads the video and metadata to YouTube channel "${selected?.account}" via the YouTube Data API.`
              : `This sends the reviewed media and caption to ${selected?.account} through the Instagram API.`
            : confirm === "schedule"
              ? `The post will wait until ${due ? new Date(due).toLocaleString() : "its saved time"} and any predecessor spacing.`
              : "The media remains in your project, but this publication leaves the queue."
        }
      >
        <div className="modal-footer">
          <Button onClick={() => setConfirm(null)}>Go back</Button>
          <Button
            variant={confirm === "reject" ? "danger" : "primary"}
            busy={busy}
            onClick={() => void decide(confirm!)}
          >
            {confirm === "approve"
              ? "Publish now"
              : confirm === "schedule"
                ? "Schedule post"
                : "Reject post"}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
function ShieldNote() {
  return (
    <>
      <Check size={21} />
      <strong>You control the release.</strong>
      <p>
        Automatic posts respect your saved spacing. Approval mode keeps the
        final decision here.
      </p>
    </>
  );
}

export function MusicLibrary() {
  const { notify, refresh } = useStudio(),
    [category, setCategory] = useState("cinematic_epic"),
    [search, setSearch] = useState(""),
    [playing, setPlaying] = useState<{ name: string; url: string } | null>(
      null,
    ),
    [busy, setBusy] = useState(false);
  const query = useQuery({
      queryKey: ["music"],
      queryFn: () => api<Music[]>("/music"),
    }),
    data = query.data || [],
    current = data.find((c) => c.id === category),
    tracks =
      current?.tracks.filter((t) =>
        t.name.toLowerCase().includes(search.toLowerCase()),
      ) || [];
  async function add(file: File) {
    setBusy(true);
    try {
      await upload(`/music/${category}/upload`, file);
      refresh();
      notify("Track added to this music category.");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="page music-page">
      <PageHeading
        eyebrow="THE SOUND OF THE STORY"
        title="Set the right tone."
        description="A considered music library. Matched to the moment, mixed beneath the voice."
      >
        <label className={`button primary ${busy ? "disabled" : ""}`}>
          <Upload size={16} />
          {busy ? "Uploading…" : "Add a track"}
          <input
            type="file"
            accept=".mp3,.wav,.m4a,.aac,.flac,.ogg"
            disabled={busy}
            onChange={(e) => {
              if (e.target.files?.[0]) void add(e.target.files[0]);
              e.target.value = "";
            }}
          />
        </label>
      </PageHeading>
      <div className="music-categories">
        {data.map((c, i) => (
          <button
            key={c.id}
            onClick={() => setCategory(c.id)}
            className={category === c.id ? "selected" : ""}
          >
            <span className="music-category-number">0{i + 1}</span>
            <AudioLines size={23} strokeWidth={1.3} />
            <strong>{c.name.replace(" - ", " / ")}</strong>
            <small>{c.tracks.length} tracks</small>
            {category === c.id && (
              <span className="category-check">
                <Check size={12} />
              </span>
            )}
          </button>
        ))}
      </div>
      <div className="music-library-header">
        <div>
          <h2>{current?.name.replace(" - ", " / ") || "Your tracks"}</h2>
          <p>
            {
              (
                {
                  cinematic_epic: "Dramatic, powerful and motivational.",
                  emotional_sad: "Emotional, touching and melancholic.",
                  suspense_thriller: "Tension, mystery and curiosity.",
                  energetic_hype: "Fast, exciting and high-energy.",
                  chill_ambient: "Calm, aesthetic and relaxing.",
                } as Record<string, string>
              )[category]
            }
          </p>
        </div>
        <label className="search-field">
          <Search size={16} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Find a track…"
            aria-label="Find a track"
          />
        </label>
      </div>
      {query.error ? (
        <ErrorBox error={query.error} />
      ) : query.isPending ? (
        <Loading />
      ) : !tracks.length ? (
        <Empty
          icon={Music2}
          title="Leave room for the right sound."
          description="Add tracks to this category. The editor chooses one at random and reuses it on retries."
        />
      ) : (
        <div className="track-table">
          <div className="track-header">
            <span>#</span>
            <span>TRACK NAME</span>
            <span>FORMAT</span>
            <span>SIZE</span>
            <span />
          </div>
          {tracks.map((track, i) => (
            <div
              className={`track-row ${playing?.url === track.url ? "playing" : ""}`}
              key={track.name}
            >
              <button
                aria-label={`Preview ${track.name}`}
                onClick={() => setPlaying(track)}
              >
                {playing?.url === track.url ? (
                  <AudioLines size={17} />
                ) : (
                  <>
                    <span>{String(i + 1).padStart(2, "0")}</span>
                    <Play size={16} />
                  </>
                )}
              </button>
              <button className="track-name" onClick={() => setPlaying(track)}>
                <span className="track-icon">
                  <Music2 size={17} />
                </span>
                <span>{track.name.replace(/\.[^.]+$/, "")}</span>
              </button>
              <span className="track-format">
                {track.name.split(".").pop()?.toUpperCase()}
              </span>
              <span className="muted">
                {(track.bytes / 1024 ** 2).toFixed(1)} MB
              </span>
              <a
                href={track.url}
                download
                aria-label={`Download ${track.name}`}
              >
                <Download size={16} />
              </a>
            </div>
          ))}
        </div>
      )}
      <div className="music-footnote">
        <Info size={14} />
        <span>
          Tracks are normalized, mixed at your saved gain, and ducked beneath
          speech. Empty categories export without music.
        </span>
      </div>
      {playing && (
        <div className="audio-player">
          <span className="audio-player-icon">
            <AudioLines size={22} />
          </span>
          <div>
            <span className="eyebrow">NOW PREVIEWING</span>
            <strong>{playing.name}</strong>
          </div>
          <audio key={playing.url} src={playing.url} controls autoPlay />
          <IconButton
            icon={X}
            label="Close music preview"
            onClick={() => setPlaying(null)}
          />
        </div>
      )}
    </div>
  );
}
