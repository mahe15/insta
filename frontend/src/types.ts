export type Preferences = {
  project_rules: string;
  description_suffix: string;
  overlay_text: string;
  editorial_profile: string;
  text_mode: string;
  sound_effects: boolean;
  sfx_gain: number;
  reaction_zoom: boolean;
  scan_minutes: number;
  focus_times: number[];
  music_gain: number;
  music_normalize: boolean;
  clipping_mode: string;
  gemini_verify_captions: boolean;
  ai_provider: string | null;
  ai_model: string | null;
  clips: number;
  min_seconds: number;
  max_seconds: number;
  style: string;
  captions: boolean;
  reframe: string;
  language: string;
  width: number;
  fps: number;
  color_grade: string;
  export_quality: string;
  auto_render: boolean;
  layout: string;
  fast_cut?: boolean;
  fast_cut_duration?: number;
  fast_cut_skip_intro?: boolean;
  music: boolean;
  music_ducking: boolean;
  music_override?: string | null;
  music_folder?: string | null;
  music_track?: string | null;
  smart_crop: boolean;
  preserve_wide_groups: boolean;
  trim_edges: boolean;
  hook_style: string;
  auto_publish: boolean;
  instagram_account: string;
  youtube_auto_publish?: boolean;
  youtube_account?: string;
  f1_enabled: boolean;
  f2_enabled: boolean;
  active_feature: string;
  f2_auto_publish: boolean;
  selected_niche: string;
  enabled_niches: string[];
};
export type Coverage = {
  fraction?: number;
  partial?: boolean;
  analyzed_seconds?: number;
  source_seconds?: number;
  ranges?: { start: number; end: number; reason: string }[];
};
export type ClipPublication = {
  id: string;
  origin: string;
  platform: string;
  account: string;
  state: string;
  media_id?: string | null;
  error?: string;
  published_at?: number | null;
  due?: number | null;
  gap?: number | null;
  created?: number;
};
export type ScheduleAllResult = {
  ok: boolean;
  count: number;
  skipped_live_count?: number;
  skipped_clip_ids?: number[];
  gap_hours: number;
  platform: string;
  account: string;
  channel_title: string;
  items: {
    clip_id: number;
    title: string;
    publication_id: string;
    due: number;
    gap_seconds: number;
    platform: string;
    state: string;
    media_id?: string | null;
    url?: string | null;
    scheduled_on_youtube?: boolean;
  }[];
  message: string;
};
export type Clip = {
  moment_type: string;
  payoff_time: number | null;
  id: number;
  title: string;
  start: number;
  end: number;
  score: number;
  reason: string;
  text: string;
  hook_text: string;
  hook_variants: string[];
  music_category: string;
  caption: string;
  hashtags: string[];
  ratings: Record<string, number>;
  editorial: Record<string, unknown>;
  video: string | null;
  cover: string | null;
  qa: Record<string, unknown> | null;
  publications?: ClipPublication[];
};
export type Job = {
  editorial_profile: string;
  id: string;
  title: string;
  source: string;
  state: string;
  stage: string;
  error: string;
  created: number;
  updated: number;
  owner: number;
  chat: number;
  clip_count: number;
  rendered: number;
  cover: string | null;
  duration: number | null;
  coverage: Coverage;
  provider: string;
  analysis?: { title: string; clips: Clip[]; coverage: Coverage };
  preferences?: Preferences;
  selected?: number[];
};
export type System = {
  engine: { mode: string; healthy: boolean; scope: string };
  device: string;
  encoder: string;
  whisper_model: string;
  compute_type: string;
  free_gb: number;
  total_gb: number;
  face_model: boolean;
  max_source_minutes: number;
  long_source_minutes: number;
  max_active_jobs: number;
  max_download_mb: number;
  scan_download_workers: number;
  retention_days: number;
  browser_profile: string;
};
export type Bootstrap = {
  csrf: string;
  owner: number;
  default_provider: string;
  preferences: Preferences;
  platforms: Record<string, string[]>;
  niches: Record<string, string>;
  providers: { id: string; model: string; configured: boolean }[];
  system: System;
};
export type Carousel = {
  id: string;
  niche: string;
  count: number;
  prompt?: string;
  state: string;
  stage: string;
  error: string;
  created: number;
  items: {
    name: string;
    plan: {
      topic?: string;
      hook?: string;
      caption?: string;
      slides?: { text: string }[];
    };
    images: string[];
    cover: string | null;
  }[];
};
export type Niche = {
  key: string;
  label: string;
  reference_ready: boolean;
  config: {
    name?: string;
    brand?: string;
    character_path?: string;
    instagram_account?: string;
    threshold?: number;
    pillars?: string[];
    banned_topics?: string[];
    research_feeds?: string[];
  };
};
export type Publication = {
  id: string;
  origin: string;
  feature: string;
  account: string;
  state: string;
  due: number;
  created: number;
  error: string;
  published_at: number | null;
  media_id: string | null;
  predecessor: string | null;
  gap: number;
  caption: string;
  automatic: boolean;
  review_note: string;
  platform?: "instagram" | "youtube";
  media: { url: string; video: boolean }[];
};
export type Music = {
  id: string;
  name: string;
  tracks: { name: string; bytes: number; url: string }[];
};
export type Connections = {
  telegram_configured: boolean;
  media_host_configured: boolean;
  accounts: {
    key: string;
    ig_user_id: string;
    login: string;
    token_configured: boolean;
    owner_allowed: boolean;
  }[];
};

export type YouTubeAccount = {
  key: string;
  title: string;
  channel_id: string;
  privacy: "public" | "unlisted" | "private";
  default_tags: string[];
  thumbnail: string;
  auto_publish: boolean;
  owner_allowed: boolean;
  authorized: boolean;
};

export type YouTubeConnections = {
  configured: boolean;
  client_id: string;
  has_secret: boolean;
  accounts: YouTubeAccount[];
};

export type PromptInfo = {
  key: string;
  title: string;
  category: "carousels" | "clips" | "speed" | "x" | "display";
  description: string;
  default: string;
  value: string;
  is_custom: boolean;
  variables: string[];
  updated_at?: number;
};

export type HookProperties = {
  SPECIFICITY: number;
  ADDRESS: number;
  STAKES: number;
  CURIOSITY: number;
  BREVITY: number;
};

export type HookFormula = {
  id: string;
  name: string;
  shape: string;
  example: string;
  fails_when: string;
  match?: string[];
};

export type HookScoreResult = {
  hook: string;
  properties: HookProperties;
  verdict: number;
  band: "STRONG" | "WORKABLE" | "WEAK";
  formula: string;
  formula_hits: number;
  formula_info?: HookFormula | null;
  weakest: keyof HookProperties;
  fix: string;
  word_count: number;
};

export type PackageLintIssue = {
  kind: string;
  message: string;
};

export type PackageLintResult = {
  title: string;
  thumb?: string | null;
  chars: number;
  score: number;
  status: "PASS" | "WARN" | "FAIL";
  desktop_preview: string;
  mobile_preview: string;
  issues: PackageLintIssue[];
  good: string[];
};

export type DeadAirCut = {
  kind: "DEAD" | "FILLER" | "REPEAT";
  start: number;
  end: number;
  duration: number;
  why: string;
};

export type DeadAirResult = {
  duration: number;
  cuts: DeadAirCut[];
  removed_seconds: number;
  out_seconds: number;
  percent_saved: number;
  cues_count: number;
};

export type Chapter = {
  start: number;
  end: number;
  label: string;
  draft_title: string;
  duration: number;
};

export type ChaptersResult = {
  valid: boolean;
  rules?: {
    first_is_00_00: boolean;
    at_least_3_chapters: boolean;
    all_min_10_seconds: boolean;
  };
  chapters: Chapter[];
  formatted_text: string;
};

export type RetentionCliff = {
  from: number;
  to: number;
  lost: number;
  at_seconds?: number | null;
  label: string;
  spoken?: string;
};

export type RetentionResult = {
  points: number;
  start: number;
  end: number;
  hook_leak: number;
  hook_verdict: "healthy" | "leaking" | "severe";
  cliffs: RetentionCliff[];
  slide_rate: number;
  advice: string;
};

export type SwipeOutlier = {
  channel: string;
  title: string;
  views: number;
  median: number;
  multiple: number;
  formula: string;
  url?: string;
  duration?: number;
};

export type SwipeResult = {
  total_analyzed: number;
  channel_count: number;
  min_multiple: number;
  outliers: SwipeOutlier[];
  skipped_thin_channels: { channel: string; count: number }[];
  top_formulas: { formula: string; count: number }[];
};

