import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronRight,
  Clapperboard,
  Clock3,
  Film,
  FolderOpen,
  Grid2X2,
  Layers2,
  Link2,
  ListFilter,
  ListVideo,
  Plus,
  Search,
  SlidersHorizontal,
  Sparkles,
  Video,
} from "lucide-react";
import { api, providerName, seconds, when } from "./api";
import type { Job } from "./types";
import {
  Badge,
  Button,
  Empty,
  ErrorBox,
  IconButton,
  Loading,
  PageHeading,
  Switch,
  useStudio,
} from "./ui";

const activeStates = [
  "queued_analysis",
  "analyzing",
  "queued_render",
  "rendering",
  "uploading",
];
function sourceName(source: string) {
  try {
    return new URL(source).hostname
      .replace("www.", "")
      .replace(".com", "")
      .replace(".tv", "");
  } catch {
    return "Local video";
  }
}
export default function Studio() {
  const { boot, notify, refresh, create } = useStudio(),
    navigate = useNavigate();
  const query = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api<Job[]>("/jobs"),
    refetchInterval: 5000,
  });
  const jobs = query.data || [],
    [filter, setFilter] = useState("all"),
    [search, setSearch] = useState(""),
    [view, setView] = useState("grid"),
    [url, setUrl] = useState(""),
    [sort, setSort] = useState("newest"),
    [switching, setSwitching] = useState(false);
  const active = jobs.filter((j) => activeStates.includes(j.state)),
    review = jobs.filter((j) => j.state === "awaiting_selection"),
    finished = jobs.filter((j) => j.state === "complete");
  const filtered = useMemo(
    () =>
      jobs
        .filter(
          (j) =>
            (filter === "all" ||
              (filter === "active" && activeStates.includes(j.state)) ||
              (filter === "review" && j.state === "awaiting_selection") ||
              (filter === "complete" && j.state === "complete") ||
              (filter === "failed" && j.state === "failed")) &&
            (j.title + j.source + j.id)
              .toLowerCase()
              .includes(search.toLowerCase()),
        )
        .sort((a, b) =>
          sort === "newest" ? b.created - a.created : a.created - b.created,
        ),
    [jobs, filter, search, sort],
  );
  async function toggle(key: string, value: boolean) {
    setSwitching(true);
    try {
      await api("/preferences", "PUT", { [key]: value });
      refresh();
      notify(
        value
          ? "Clipping enabled."
          : "Clipping paused. Jobs stay in your queue.",
      );
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setSwitching(false);
    }
  }
  return (
    <div className="page studio-page">
      <PageHeading
        eyebrow="THE PRODUCTION WORKSPACE"
        title="Make something worth watching."
        description="Find the moment. Shape the story. Make it yours."
      >
        <Button icon={Plus} variant="primary" onClick={() => create()}>
          New project
        </Button>
      </PageHeading>
      <section
        className="source-launcher"
        aria-label="Create a clipping project"
      >
        <div className="source-launcher-main">
          <div className="source-title">
            <span className="line-icon">
              <Link2 size={18} />
            </span>
            <h2>One link. Your next great clip.</h2>
          </div>
          <p>
            Bring a video or a long stream. Let the interesting parts rise to
            the top.
          </p>
          <form
            className="source-input"
            onSubmit={(e) => {
              e.preventDefault();
              create(url);
            }}
          >
            <Link2 size={19} />
            <input
              type="url"
              required
              aria-label="Video link"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="Paste a YouTube, Twitch, Kick or video link…"
            />
            <button type="submit" aria-label="Configure this source">
              <ArrowRight size={21} />
            </button>
          </form>
          <div className="supported-sources">
            <span>YOUTUBE</span>
            <i />
            <span>TWITCH</span>
            <i />
            <span>KICK</span>
            <span
              className="more-sources"
              title={Object.keys(boot.platforms).join(", ")}
            >
              +9 platforms
            </span>
            <Link to="/settings?tab=clipping">
              Configure workflow <ArrowUpRight size={12} />
            </Link>
          </div>
        </div>
        <div className="source-launcher-aside">
          <span className="eyebrow">BUILT FOR THE LONG RUN</span>
          <div className="scan-illustration" aria-hidden="true">
            <div className="scan-track">
              {Array.from({ length: 32 }, (_, i) => (
                <i
                  key={i}
                  className={
                    [3, 4, 11, 12, 20, 21, 28, 29].includes(i) ? "selected" : ""
                  }
                />
              ))}
            </div>
            <div>
              <span>00:00</span>
              <span>20:00:00</span>
            </div>
          </div>
          <h3>
            Less waiting.
            <br />
            More worthwhile moments.
          </h3>
          <p>
            Scan the story, not every second.
            <br />
            <strong>{boot.preferences.scan_minutes} min</strong> discovery
            budget <span>·</span>{" "}
            <button onClick={() => navigate("/settings?tab=clipping")}>
              Adjust
            </button>
          </p>
        </div>
      </section>
      <div className="studio-content">
        <div className="project-library">
          <div className="library-heading">
            <div>
              <h2>
                Your projects <span className="count">{jobs.length}</span>
              </h2>
              <p>From first pass to final cut.</p>
            </div>
            <div className="view-toggle" aria-label="Project view">
              <IconButton
                label="Grid view"
                icon={Grid2X2}
                className={view === "grid" ? "selected" : ""}
                onClick={() => setView("grid")}
              />
              <IconButton
                label="List view"
                icon={ListVideo}
                className={view === "list" ? "selected" : ""}
                onClick={() => setView("list")}
              />
            </div>
          </div>
          <div
            className="library-tabs"
            role="tablist"
            aria-label="Project status"
          >
            {[
              ["all", "All projects", jobs.length],
              ["active", "In progress", active.length],
              ["review", "To review", review.length],
              ["complete", "Completed", finished.length],
              [
                "failed",
                "Attention",
                jobs.filter((j) => j.state === "failed").length,
              ],
            ].map(([key, label, count]) => (
              <button
                key={key}
                role="tab"
                aria-selected={filter === key}
                onClick={() => setFilter(String(key))}
              >
                {label}
                {Number(count) > 0 && <span>{count}</span>}
              </button>
            ))}
          </div>
          <div className="library-toolbar">
            <label className="search-field">
              <Search size={16} />
              <input
                aria-label="Search projects"
                placeholder="Search your projects…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </label>
            <label className="sort-select">
              <ArrowDown size={14} />
              <select
                aria-label="Sort projects"
                value={sort}
                onChange={(e) => setSort(e.target.value)}
              >
                <option value="newest">Newest first</option>
                <option value="oldest">Oldest first</option>
              </select>
            </label>
          </div>
          {query.error ? (
            <ErrorBox error={query.error} retry={() => void query.refetch()} />
          ) : query.isPending ? (
            <Loading />
          ) : !filtered.length ? (
            <Empty
              icon={FolderOpen}
              title={
                jobs.length
                  ? "No projects match this view."
                  : "Your best work starts here."
              }
              description={
                jobs.length
                  ? "Try another status or a different search."
                  : "Add your first video and build a shortlist of moments worth sharing."
              }
              action={
                <Button
                  icon={Plus}
                  onClick={() =>
                    jobs.length ? (setFilter("all"), setSearch("")) : create()
                  }
                >
                  {jobs.length ? "Clear filters" : "Create a project"}
                </Button>
              }
            />
          ) : (
            <div className={view === "grid" ? "project-grid" : "project-list"}>
              {filtered.map((job) => (
                <Link
                  to={`/project/${job.id}`}
                  key={job.id}
                  className="project-card"
                >
                  <div className="project-poster">
                    {job.cover ? (
                      <img src={job.cover} alt="" loading="lazy" />
                    ) : (
                      <div className="poster-placeholder">
                        <span className="poster-grid" />
                        <Clapperboard size={36} strokeWidth={1} />
                        <span>{sourceName(job.source)}</span>
                      </div>
                    )}
                    <span className="poster-platform">
                      {sourceName(job.source)}
                    </span>
                    {job.duration && (
                      <span className="poster-duration">
                        {seconds(job.duration)}
                      </span>
                    )}
                    <span className="poster-open">
                      <ArrowUpRight size={20} />
                    </span>
                  </div>
                  <div className="project-card-content">
                    <div className="card-kicker">
                      <span>
                        {job.preferences?.clipping_mode === "gemini_browser"
                          ? "GEMINI CLIP"
                          : "VIDEO PROJECT"}
                      </span>
                      <span>{when(job.created)}</span>
                    </div>
                    <h3 title={job.title}>{job.title}</h3>
                    <div className="project-meta">
                      <span>
                        <Film size={12} />
                        {job.clip_count
                          ? `${job.clip_count} clips`
                          : ["failed", "cancelled"].includes(job.state)
                            ? "Not analyzed"
                            : "Awaiting analysis"}
                      </span>
                      <span>{job.rendered} exported</span>
                    </div>
                    <div className="card-bottom">
                      <Badge state={job.state} />
                      <ChevronRight size={15} />
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
          {jobs.length > 0 && (
            <div className="library-count">
              Showing {filtered.length} of {jobs.length} projects{" "}
              <span>Updates automatically</span>
            </div>
          )}
        </div>
        <aside className="studio-rail">
          <section className="rail-card">
            <div className="rail-heading">
              <h3>At a glance</h3>
              <span className="live-label">
                <span className="status-dot" />
                Live
              </span>
            </div>
            <div className="metric">
              <span>
                <Clock3 size={15} />
                In production
              </span>
              <strong>{active.length.toString().padStart(2, "0")}</strong>
            </div>
            <div className="metric">
              <span>
                <Layers2 size={15} />
                Ready to review
              </span>
              <strong>{review.length.toString().padStart(2, "0")}</strong>
            </div>
            <div className="metric">
              <span>
                <Check size={15} />
                Clips exported
              </span>
              <strong>
                {jobs
                  .reduce((n, j) => n + j.rendered, 0)
                  .toString()
                  .padStart(2, "0")}
              </strong>
            </div>
            <div className="rail-divider" />
            <Switch
              label="Clipping enabled"
              checked={boot.preferences.f1_enabled}
              onChange={(v) => void toggle("f1_enabled", v)}
              disabled={switching}
            />
            <p className="rail-caption">
              Pause new processing without losing your queue.
            </p>
          </section>
          <section className="rail-card current-workflow">
            <div className="rail-heading">
              <h3>Your workflow</h3>
              <SlidersHorizontal size={15} />
            </div>
            <div className="workflow-item">
              <span>Discovery</span>
              <strong>
                {providerName(
                  boot.preferences.ai_provider || boot.default_provider,
                )}
              </strong>
            </div>
            <div className="workflow-item">
              <span>Format</span>
              <strong>
                {boot.preferences.layout === "square_hook"
                  ? "Square + hook"
                  : "Full vertical"}{" "}
                <small>{boot.preferences.width}p</small>
              </strong>
            </div>
            <div className="workflow-item">
              <span>Clip length</span>
              <strong>
                {boot.preferences.min_seconds}–{boot.preferences.max_seconds}{" "}
                seconds
              </strong>
            </div>
            <div className="workflow-item">
              <span>Publishing</span>
              <strong>
                {boot.preferences.auto_publish ? "Automatic" : "Review first"}
              </strong>
            </div>
            <Link className="rail-link" to="/settings">
              Fine-tune your settings <ArrowRight size={14} />
            </Link>
          </section>
          <section className="carousel-promo">
            <div className="mini-stack" aria-hidden="true">
              <div />
              <div />
              <div>
                <span>01</span>
                <i />
                <i />
                <i />
              </div>
            </div>
            <span className="eyebrow">MORE THAN A MOMENT</span>
            <h3>
              Give your ideas
              <br />a little more room.
            </h3>
            <p>
              Create considered carousels with a consistent character and a
              story worth swiping.
            </p>
            <Link to="/carousels">
              Open carousel studio <ArrowUpRight size={15} />
            </Link>
          </section>
        </aside>
      </div>
    </div>
  );
}
