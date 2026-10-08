import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  CalendarDays,
  Search,
  Settings2,
  Upload,
} from "lucide-react";
import { api, dateTime } from "./api";
import {
  Button,
  ErrorBox,
  Field,
  Loading,
  Modal,
  PageHeading,
  SectionTitle,
  Switch,
  useStudio,
} from "./ui";

type Settings = {
  handle: string;
  enabled: boolean;
  auto_publish: boolean;
  browser_risk_accepted: boolean;
  daily_limit: number;
  gap_minutes: number;
  freshness_hours: number;
};
type Request = {
  category: string;
  keywords: string;
  angle: string;
  hours: number;
};
type Media = {
  sha256: string;
  kind: string;
  alt: string;
  license: string;
  source_url: string;
  creator: string;
  reviewed: boolean;
};
type Job = {
  id: string;
  state: string;
  request: Request;
  error: string;
  created: number;
  due: number;
  target: string;
  post_url: string;
  result: {
    text?: string;
    flags?: string[];
    researched_at?: number;
    human_reviewed?: boolean;
    media?: Media;
    draft?: {
      reasoning: string;
      hook_score: number;
      clarity_score: number;
      source_score: number;
    };
    research?: {
      topic: string;
      audience_value: string;
      claims: string[];
      sources: {
        url: string;
        title: string;
        publisher: string;
        published_at: string;
        primary: boolean;
        evidence: string;
      }[];
    };
  };
};
type Overview = {
  categories: Record<string, { name: string; brief: string }>;
  settings: Settings;
  jobs: Job[];
  schedules: {
    category: string;
    request: Request;
    hours: number;
    enabled: boolean;
    next_run: number;
  }[];
  library: { id: string; category: string; metadata: Media }[];
};
const stateNames: Record<string, string> = {
  queued: "Research queued",
  researching: "Researching",
  review: "Review draft",
  queued_publish: "Scheduled",
  preparing: "Preparing",
  publishing: "Submitting",
  published: "Published",
  failed: "Needs attention",
  uncertain: "Check X first",
  rejected: "Discarded",
};

export default function XStudio() {
  const { refresh, notify } = useStudio();
  const query = useQuery({
    queryKey: ["x-studio"],
    queryFn: () => api<Overview>("/x"),
    refetchInterval: 5000,
  });
  const [request, setRequest] = useState<Request>({
    category: "football",
    keywords: "",
    angle: "explainer",
    hours: 24,
  });
  const [busy, setBusy] = useState(false),
    [selected, setSelected] = useState<Job | null>(null),
    [settingsOpen, setSettingsOpen] = useState(false),
    [libraryOpen, setLibraryOpen] = useState(false),
    [cadence, setCadence] = useState(12);
  const [filter, setFilter] = useState("all");
  async function action(fn: () => Promise<unknown>, message: string) {
    setBusy(true);
    try {
      await fn();
      refresh();
      notify(message);
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  if (query.isLoading) return <Loading />;
  if (query.error) return <ErrorBox error={query.error} />;
  const data = query.data!;
  const current = selected
    ? data.jobs.find((j) => j.id === selected.id) || selected
    : null;
  const jobs = data.jobs.filter((j) => filter === "all" || j.state === filter);
  return (
    <div className="page x-page">
      <PageHeading
        eyebrow="X STUDIO"
        title="A sharper take. A stronger source."
        description="Live research, original writing and real media. Built around the conversations you care about."
      />
      <div className="x-toolbar">
        <span className="badge">
          {data.settings.handle
            ? `@${data.settings.handle}`
            : "Account not connected"}
        </span>
        <span className="muted">
          {data.settings.auto_publish
            ? "Automatic publishing"
            : "Review before publishing"}
        </span>
        <Button icon={Settings2} onClick={() => setSettingsOpen(true)}>
          Account & automation
        </Button>
      </div>
      <div className="speed-layout">
        <section className="settings-section">
          <SectionTitle
            title="Find a story worth sharing"
            note="ChatGPT searches the web in your existing browser session, then writes from the evidence."
          />
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void action(
                () => api("/x/research", "POST", request),
                "Research queued. Follow its progress below.",
              );
            }}
          >
            <div className="form-grid">
              <Field label="Category">
                <select
                  value={request.category}
                  onChange={(e) =>
                    setRequest({ ...request, category: e.target.value })
                  }
                >
                  {Object.entries(data.categories).map(([key, c]) => (
                    <option key={key} value={key}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Post style">
                <select
                  value={request.angle}
                  onChange={(e) =>
                    setRequest({ ...request, angle: e.target.value })
                  }
                >
                  <option value="explainer">Why it matters</option>
                  <option value="news">Concise update</option>
                  <option value="analysis">Evidence-backed analysis</option>
                </select>
              </Field>
            </div>
            <p className="info-note">
              {data.categories[request.category].brief}
            </p>
            <Field
              label="Keywords or topic"
              hint="Optional. Use a team, player, product, release or question. Leave blank to discover a fresh story."
            >
              <input
                placeholder="e.g. Arsenal tactics, Champions League"
                value={request.keywords}
                maxLength={500}
                onChange={(e) =>
                  setRequest({ ...request, keywords: e.target.value })
                }
              />
            </Field>
            <Field
              label="Research freshness · hours"
              hint="Older or superseded stories are held. Sources and event dates stay visible."
            >
              <input
                type="number"
                min={1}
                max={72}
                value={request.hours}
                onChange={(e) =>
                  setRequest({ ...request, hours: +e.target.value })
                }
              />
            </Field>
            <Button variant="primary" icon={Search} busy={busy}>
              Research a post
            </Button>
          </form>
        </section>
        <aside>
          <section className="settings-section">
            <SectionTitle
              title="Keep the desk running"
              note="Schedule research for the selected category and keywords. Each cycle creates one post."
            />
            <Field label="Research every · hours">
              <input
                type="number"
                min={3}
                max={168}
                value={cadence}
                onChange={(e) => setCadence(+e.target.value)}
              />
            </Field>
            <Button
              icon={CalendarDays}
              busy={busy}
              onClick={() =>
                action(
                  () =>
                    api("/x/schedule", "PUT", {
                      request,
                      hours: cadence,
                      enabled: true,
                    }),
                  "Research schedule saved.",
                )
              }
            >
              Schedule this topic
            </Button>
            <p className="info-note">
              Automatic publishing needs a confirmed account, fresh corroborated
              sources and approved category media. Other posts stay in review.
            </p>
            {data.schedules.map((s) => (
              <div className="x-schedule" key={s.category}>
                <div>
                  <strong>{data.categories[s.category].name}</strong>
                  <small>
                    {s.enabled
                      ? `Every ${s.hours}h · next ${dateTime(s.next_run)}`
                      : "Paused"}
                  </small>
                </div>
                <Button
                  busy={busy}
                  onClick={() =>
                    action(
                      () =>
                        api("/x/schedule", "PUT", {
                          request: s.request,
                          hours: s.hours,
                          enabled: !s.enabled,
                        }),
                      "Schedule updated.",
                    )
                  }
                >
                  {s.enabled ? "Pause" : "Resume"}
                </Button>
              </div>
            ))}
          </section>
          <section className="settings-section">
            <SectionTitle
              title="Real media, ready to use"
              note={`${data.library.length} reusable images / videos. No AI-generated artwork.`}
            />
            <Button icon={Upload} onClick={() => setLibraryOpen(true)}>
              Manage category media
            </Button>
            <p className="muted">
              Use owned or licensed media with an accurate description.
              Automatic photos from Wikimedia remain in review until you verify
              relevance.
            </p>
          </section>
        </aside>
      </div>
      <section className="x-desk">
        <div className="x-toolbar">
          <h2>Your publishing desk</h2>
          <Field label="Filter posts">
            <select value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="all">All posts</option>
              {[
                "review",
                "queued",
                "queued_publish",
                "published",
                "failed",
                "uncertain",
              ].map((s) => (
                <option value={s} key={s}>
                  {stateNames[s]}
                </option>
              ))}
            </select>
          </Field>
        </div>
        {!jobs.length && (
          <div className="x-empty">
            <Search size={24} />
            <h3>Start with a subject you know.</h3>
            <p>
              Research a category or a keyword. Your sources, draft and media
              will appear here for review.
            </p>
          </div>
        )}
        <div className="x-post-grid">
          {jobs.map((job) => (
            <button
              className="x-post-card"
              key={job.id}
              onClick={() => setSelected(job)}
            >
              <div className="x-toolbar">
                <span className="eyebrow">
                  {data.categories[job.request.category].name}
                </span>
                <span
                  className={`badge ${["failed", "uncertain"].includes(job.state) ? "warning" : ""}`}
                >
                  {stateNames[job.state]}
                </span>
              </div>
              <h3>
                {job.result.research?.topic ||
                  job.request.keywords ||
                  "Finding the next story"}
              </h3>
              <p className="x-post-text">
                {job.result.text ||
                  job.error ||
                  "Waiting for the research engine. Start it in Settings → System if paused."}
              </p>
              <div className="x-card-meta">
                <span>
                  {job.result.research?.sources.length || 0} sources ·{" "}
                  {job.result.media ? "Media attached" : "Media needed"}
                </span>
                <ArrowUpRight size={16} />
              </div>
            </button>
          ))}
        </div>
      </section>
      {current && (
        <Review
          key={`${current.id}:${current.state}`}
          job={current}
          close={() => setSelected(null)}
          action={action}
          busy={busy}
        />
      )}
      {settingsOpen && (
        <Account
          initial={data.settings}
          close={() => setSettingsOpen(false)}
          action={action}
          busy={busy}
        />
      )}
      {libraryOpen && (
        <Library
          data={data}
          close={() => setLibraryOpen(false)}
          action={action}
          busy={busy}
        />
      )}
    </div>
  );
}

type Action = (fn: () => Promise<unknown>, message: string) => Promise<void>;
function MediaUpload({
  path,
  category,
  done,
}: {
  path: string;
  category?: string;
  done: () => void;
}) {
  const { notify } = useStudio();
  const [file, setFile] = useState<File | null>(null),
    [alt, setAlt] = useState(""),
    [rights, setRights] = useState(false),
    [busy, setBusy] = useState(false);
  return (
    <form
      className="x-upload"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!file) return;
        setBusy(true);
        try {
          const form = new FormData();
          form.append("file", file);
          form.append("alt", alt);
          form.append("rights", String(rights));
          if (category) form.append("category", category);
          await api(path, "POST", form);
          done();
          notify("Real media uploaded and validated.");
        } catch (error) {
          notify((error as Error).message, true);
        } finally {
          setBusy(false);
        }
      }}
    >
      <Field
        label="Real image or video"
        hint="JPG/PNG up to 5 MB. H.264 MP4 up to 80 MB, 140 seconds and 1920 pixels."
      >
        <input
          type="file"
          accept="image/jpeg,image/png,video/mp4"
          required
          onChange={(e) => setFile(e.target.files?.[0] || null)}
        />
      </Field>
      <Field
        label="Describe this media"
        hint="Describe what is actually shown; reused files are labelled illustrative."
      >
        <input
          value={alt}
          minLength={5}
          maxLength={500}
          required
          onChange={(e) => setAlt(e.target.value)}
        />
      </Field>
      <label className="x-check">
        <input
          type="checkbox"
          checked={rights}
          onChange={(e) => setRights(e.target.checked)}
          required
        />
        I own this media or have permission to publish it. The description is
        accurate.
      </label>
      <Button icon={Upload} busy={busy}>
        Upload media
      </Button>
    </form>
  );
}

function Review({
  job,
  close,
  action,
  busy,
}: {
  job: Job;
  close: () => void;
  action: Action;
  busy: boolean;
}) {
  const { refresh } = useStudio();
  const [text, setText] = useState(job.result.text || ""),
    [reviewed, setReviewed] = useState(false),
    [due, setDue] = useState(""),
    [url, setUrl] = useState("");
  const editable = job.state === "review";
  return (
    <Modal
      open
      onOpenChange={close}
      wide
      title={job.result.research?.topic || "X research project"}
      description={stateNames[job.state]}
    >
      <div className="x-review">
        <div>
          <Field
            label="Post text"
            hint="280 weighted characters maximum. URLs count as 23; the server checks the final text."
          >
            <textarea
              rows={7}
              value={text}
              disabled={!editable}
              onChange={(e) => {
                setText(e.target.value);
                setReviewed(false);
              }}
            />
          </Field>
          {job.result.media &&
            (job.result.media.kind === "video" ? (
              <video
                className="x-media"
                controls
                src={`/api/x/jobs/${job.id}/media?v=${job.result.media.sha256}`}
              />
            ) : (
              <img
                className="x-media"
                src={`/api/x/jobs/${job.id}/media?v=${job.result.media.sha256}`}
                alt={job.result.media.alt}
              />
            ))}
          {job.result.media && (
            <p className="muted">
              {job.result.media.license} · {job.result.media.creator}{" "}
              {job.result.media.source_url && (
                <a
                  href={job.result.media.source_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Media source ↗
                </a>
              )}
            </p>
          )}
          {editable && (
            <details>
              <summary>Attach or replace real media</summary>
              <MediaUpload
                path={`/x/jobs/${job.id}/media`}
                done={() => {
                  setReviewed(false);
                  setText((value) =>
                    value.replace(
                      /^Illustrative file photo$/m,
                      "Illustrative media",
                    ),
                  );
                  refresh();
                }}
              />
            </details>
          )}
          {editable && (
            <>
              <label className="x-check">
                <input
                  type="checkbox"
                  checked={reviewed}
                  onChange={(e) => setReviewed(e.target.checked)}
                />
                I checked the sources, facts, media rights and context for this
                exact post.
              </label>
              <Field
                label="Publish time"
                hint="Leave empty to queue now. Posting gaps, daily limits and freshness checks still apply."
              >
                <input
                  type="datetime-local"
                  value={due}
                  onChange={(e) => setDue(e.target.value)}
                />
              </Field>
              <div className="x-toolbar">
                <Button
                  busy={busy}
                  onClick={() =>
                    action(
                      () => api(`/x/jobs/${job.id}`, "PUT", { text, reviewed }),
                      "Draft saved.",
                    )
                  }
                >
                  Save draft
                </Button>
                <Button
                  variant="primary"
                  busy={busy}
                  disabled={!reviewed || !job.result.media}
                  onClick={() =>
                    action(async () => {
                      await api(`/x/jobs/${job.id}`, "PUT", { text, reviewed });
                      await api(`/x/jobs/${job.id}/approve`, "POST", {
                        due: due ? new Date(due).getTime() / 1000 : null,
                      });
                      close();
                    }, "Approved post queued for X.")
                  }
                >
                  Approve & queue
                </Button>
              </div>
            </>
          )}
          {job.post_url && (
            <a
              className="button primary"
              href={job.post_url}
              target="_blank"
              rel="noreferrer"
            >
              Open published post ↗
            </a>
          )}
          {job.state === "uncertain" && (
            <>
              <p className="info-note">
                Submission may have succeeded. Check @{job.target} on X. This
                post will never be retried automatically.
              </p>
              <Field label="Existing X post URL">
                <input
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder={`https://x.com/${job.target}/status/…`}
                />
              </Field>
              <Button
                busy={busy}
                onClick={() =>
                  action(
                    () =>
                      api(`/x/jobs/${job.id}/resolve`, "POST", {
                        post_url: url,
                      }),
                    "Existing post recorded.",
                  )
                }
              >
                Record existing post
              </Button>
            </>
          )}
        </div>
        <aside>
          <h3>Evidence before reach</h3>
          {job.error && <p className="info-note">{job.error}</p>}
          {job.result.flags?.map((f, i) => (
            <p key={i} className="info-note">
              {f}
            </p>
          ))}
          <p>{job.result.research?.audience_value}</p>
          {job.result.researched_at && (
            <p className="muted">
              Researched {dateTime(job.result.researched_at)}
            </p>
          )}
          {job.result.research?.sources.map((s, i) => (
            <div className="x-source" key={i}>
              <span className="eyebrow">
                {s.primary ? "Primary source" : "Cross-check"} · {s.publisher}
              </span>
              <a href={s.url} target="_blank" rel="noreferrer">
                {s.title} ↗
              </a>
              <small>
                {s.published_at
                  ? new Date(s.published_at).toLocaleString()
                  : "Publication date unverified"}
              </small>
              <p>{s.evidence}</p>
            </div>
          ))}
          {job.result.draft && (
            <>
              <h4>Editorial assessment</h4>
              <p className="muted">
                Hook {job.result.draft.hook_score} · Clarity{" "}
                {job.result.draft.clarity_score} · Sources{" "}
                {job.result.draft.source_score}. These are editorial scores, not
                predicted views.
              </p>
              <p>{job.result.draft.reasoning}</p>
            </>
          )}
          {["failed", "rejected"].includes(job.state) && (
            <Button
              busy={busy}
              onClick={() =>
                action(
                  () => api("/x/research", "POST", job.request),
                  "Fresh research queued.",
                )
              }
            >
              Research again
            </Button>
          )}
          {["queued", "review", "queued_publish", "failed"].includes(
            job.state,
          ) && (
            <Button
              busy={busy}
              onClick={() =>
                action(async () => {
                  await api(`/x/jobs/${job.id}/reject`, "POST");
                  close();
                }, "Post discarded.")
              }
            >
              Discard post
            </Button>
          )}
        </aside>
      </div>
    </Modal>
  );
}

function Account({
  initial,
  close,
  action,
  busy,
}: {
  initial: Settings;
  close: () => void;
  action: Action;
  busy: boolean;
}) {
  const [value, setValue] = useState(initial);
  const update = (part: Partial<Settings>) => setValue({ ...value, ...part });
  return (
    <Modal open onOpenChange={close} title="X account & automation">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void action(
            () => api("/x/settings", "PUT", value),
            "X settings saved.",
          );
        }}
      >
        <Field
          label="X username"
          hint="The browser verifies this exact account before each post."
        >
          <input
            value={value.handle}
            placeholder="your_handle"
            maxLength={16}
            onChange={(e) => update({ handle: e.target.value })}
          />
        </Field>
        <p className="info-note">
          Sign in using <code>scripts/x-login.ps1</code>. X shares CLIPER’s
          existing Chromium profile and lock with ChatGPT/Gemini. Close the
          login window before running jobs.
        </p>
        <Switch
          label="Enable X engine"
          checked={value.enabled}
          onChange={(enabled) => update({ enabled })}
          description="Pause X research and queued posts independently of clipping."
        />
        <Switch
          label="Publish automatically"
          checked={value.auto_publish}
          onChange={(auto_publish) => update({ auto_publish })}
          description="Only fresh, corroborated drafts with preapproved category media. Other drafts wait for review."
        />
        <div className="form-grid">
          <Field label="Posts per rolling 24 hours">
            <input
              type="number"
              min={1}
              max={12}
              value={value.daily_limit}
              onChange={(e) => update({ daily_limit: +e.target.value })}
            />
          </Field>
          <Field label="Minimum gap · minutes">
            <input
              type="number"
              min={30}
              max={1440}
              value={value.gap_minutes}
              onChange={(e) => update({ gap_minutes: +e.target.value })}
            />
          </Field>
        </div>
        <Field label="Maximum research age · hours">
          <input
            type="number"
            min={1}
            max={72}
            value={value.freshness_hours}
            onChange={(e) => update({ freshness_hours: +e.target.value })}
          />
        </Field>
        <p className="info-note">
          X’s rules prohibit non-API website automation and warn of possible
          suspension. This browser integration is experimental.{" "}
          <a
            href="https://help.x.com/en/rules-and-policies/x-automation"
            target="_blank"
            rel="noreferrer"
          >
            Read X’s rules ↗
          </a>
        </p>
        <label className="x-check">
          <input
            type="checkbox"
            checked={value.browser_risk_accepted}
            onChange={(e) =>
              update({ browser_risk_accepted: e.target.checked })
            }
          />
          I understand this risk and choose browser publishing for my account.
        </label>
        <Button variant="primary" busy={busy}>
          Save X settings
        </Button>
      </form>
    </Modal>
  );
}

function Library({
  data,
  close,
  action,
  busy,
}: {
  data: Overview;
  close: () => void;
  action: Action;
  busy: boolean;
}) {
  const { refresh } = useStudio();
  const [category, setCategory] = useState("football");
  return (
    <Modal
      open
      onOpenChange={close}
      title="Category media library"
      description="Reusable, real media for unattended posts. The newest file in a category is used as illustrative media."
    >
      <Field label="Media category">
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          {Object.entries(data.categories).map(([key, value]) => (
            <option value={key} key={key}>
              {value.name}
            </option>
          ))}
        </select>
      </Field>
      <MediaUpload path="/x/library" category={category} done={refresh} />
      {data.library.map((m) => (
        <div className="x-source" key={m.id}>
          <strong>
            {data.categories[m.category].name} · {m.metadata.kind}
          </strong>
          <p>{m.metadata.alt}</p>
          <a
            href={`/api/x/library/${m.id}/media`}
            target="_blank"
            rel="noreferrer"
          >
            Preview ↗
          </a>
          <Button
            busy={busy}
            onClick={() =>
              action(
                () => api(`/x/library/${m.id}`, "DELETE"),
                "Removed from future media selection.",
              )
            }
          >
            Remove from library
          </Button>
        </div>
      ))}
    </Modal>
  );
}
