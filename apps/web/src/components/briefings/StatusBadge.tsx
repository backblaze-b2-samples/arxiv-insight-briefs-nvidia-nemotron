import { Badge } from "@/components/ui/badge";
import type { BriefStatus } from "@arxiv-insight-briefs/shared";

const LABELS: Record<BriefStatus, string> = {
  queued: "Queued",
  routing: "Routing",
  searching: "Searching arxiv",
  ranking: "Ranking abstracts",
  fetching_pdfs: "Fetching PDFs",
  synthesizing: "Synthesizing",
  done: "Done",
  done_no_results: "No results",
  done_no_analysis: "Done (no analysis)",
  failed: "Failed",
  failed_llm: "LLM failed",
  failed_arxiv_rate_limit: "arxiv rate limited",
  cancelled: "Cancelled",
};

// Map status -> badge variant + colour intent. shadcn `Badge` only ships a
// couple of variants; we extend via tailwind classes for the in-flight states.
const TERMINAL = new Set<BriefStatus>([
  "done",
  "done_no_results",
  "done_no_analysis",
  "failed",
  "failed_llm",
  "failed_arxiv_rate_limit",
  "cancelled",
]);

export function StatusBadge({ status }: { status: BriefStatus }) {
  const label = LABELS[status] ?? status;
  if (status === "done") {
    return <Badge className="bg-emerald-600 text-white">{label}</Badge>;
  }
  if (status === "failed" || status === "failed_llm") {
    return <Badge variant="destructive">{label}</Badge>;
  }
  // Rate-limit is recoverable (just wait): muted amber, not destructive.
  if (status === "failed_arxiv_rate_limit") {
    return <Badge className="bg-amber-500/80 text-white">{label}</Badge>;
  }
  if (status === "cancelled") {
    return <Badge variant="outline">{label}</Badge>;
  }
  if (TERMINAL.has(status)) {
    return <Badge variant="secondary">{label}</Badge>;
  }
  return <Badge className="bg-blue-600 text-white animate-pulse">{label}</Badge>;
}
