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
  if (status === "cancelled") {
    return <Badge variant="outline">{label}</Badge>;
  }
  if (TERMINAL.has(status)) {
    return <Badge variant="secondary">{label}</Badge>;
  }
  return <Badge className="bg-blue-600 text-white animate-pulse">{label}</Badge>;
}
