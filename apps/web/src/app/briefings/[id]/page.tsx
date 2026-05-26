"use client";

import { use } from "react";

import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { BriefingStatusCard } from "@/components/briefings/BriefingStatusCard";
import { BriefingViewer } from "@/components/briefings/BriefingViewer";
import { PaperCard } from "@/components/briefings/PaperCard";
import { useBriefing } from "@/lib/queries";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function BriefingDetailPage({ params }: PageProps) {
  const { id } = use(params);
  const { data, isLoading, isError, error, refetch } = useBriefing(id);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-24" />
        <Skeleton className="h-64" />
      </div>
    );
  }
  if (isError) {
    return (
      <ErrorState
        error={error}
        title="Couldn't load briefing"
        onRetry={() => refetch()}
      />
    );
  }
  if (!data) return null;

  const { manifest, markdown } = data;
  const cats = manifest.resolved_query.categories.join(", ");

  return (
    <div className="space-y-6">
      <div className="animate-fade-in space-y-2 border-b border-border pb-5">
        <p className="text-xs text-muted-foreground font-mono">
          {manifest.brief_id}
        </p>
        <h1 className="page-title">{manifest.question}</h1>
        {cats && (
          <p className="text-xs text-muted-foreground">
            categories: {cats} · window:{" "}
            {manifest.resolved_query.time_window_months}mo
          </p>
        )}
      </div>

      <BriefingStatusCard manifest={manifest} />

      {markdown && <BriefingViewer markdown={markdown} />}

      {manifest.ranked_papers.length > 0 && (
        <div className="space-y-3">
          <h2 className="card-title">Source papers</h2>
          <div className="grid gap-3 md:grid-cols-2">
            {manifest.ranked_papers.map((p) => (
              <PaperCard key={p.arxiv_id} paper={p} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
