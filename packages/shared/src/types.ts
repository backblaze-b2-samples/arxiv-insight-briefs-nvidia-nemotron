// TypeScript mirror of services/api/app/types/briefings.py. Keep these in
// lockstep — when you add a field on one side, add it on the other in the
// same PR.

export type BriefStatus =
  | "queued"
  | "routing"
  | "searching"
  | "ranking"
  | "fetching_pdfs"
  | "synthesizing"
  | "done"
  | "done_no_results"
  | "done_no_analysis"
  | "failed"
  | "failed_llm"
  | "cancelled";

export interface BriefRequest {
  question: string;
  time_window_months?: number | null;
}

export interface ResolvedQuery {
  question: string;
  categories: string[];
  keywords: string[];
  time_window_months: number;
  fallback_used: boolean;
  warnings: string[];
}

export interface RankedPaper {
  arxiv_id: string;
  title: string;
  authors: string[];
  abstract: string;
  primary_category: string;
  published: string; // ISO datetime
  pdf_url: string;
  relevance_score: number | null;
  rank_reason: string | null;
  cached: boolean;
  extraction_status: "pending" | "ok" | "fetch_failed" | "extract_failed";
  extraction_error: string | null;
}

export interface Citation {
  arxiv_id: string;
  presigned_url: string | null;
}

export interface InsightSection {
  text: string;
  citations: Citation[];
}

export interface BriefManifest {
  schema_version: number;
  brief_id: string;
  status: BriefStatus;
  created_at: string;
  updated_at: string;
  question: string;
  resolved_query: ResolvedQuery;
  ranked_papers: RankedPaper[];
  brief_markdown_key: string | null;
  papers_cache_hits: number;
  papers_cache_misses: number;
  nemotron_tokens: Record<string, number>;
  error: string | null;
  cancel_requested: boolean;
}

export interface BriefSummary {
  brief_id: string;
  question: string;
  status: BriefStatus;
  created_at: string;
  paper_count: number;
}

export interface BriefDetail {
  manifest: BriefManifest;
  markdown: string | null;
}

export interface PresignedLink {
  key: string;
  url: string;
  expires_in: number;
}

export interface HealthStatus {
  status: "healthy" | "degraded";
  b2_connected: boolean;
  nvidia_configured: boolean;
}
