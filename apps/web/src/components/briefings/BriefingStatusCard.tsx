"use client";

import { Loader2 } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useCancelBriefing } from "@/lib/queries";
import type { BriefManifest } from "@arxiv-insight-briefs/shared";

import { StatusBadge } from "./StatusBadge";

const IN_FLIGHT = new Set([
  "queued",
  "routing",
  "searching",
  "ranking",
  "fetching_pdfs",
  "synthesizing",
]);

export function BriefingStatusCard({ manifest }: { manifest: BriefManifest }) {
  const cancel = useCancelBriefing(manifest.brief_id);
  const inFlight = IN_FLIGHT.has(manifest.status);

  return (
    <Card>
      <CardContent className="p-5 flex flex-wrap items-start gap-4 justify-between">
        <div className="space-y-2 min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <StatusBadge status={manifest.status} />
            {inFlight && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
            {manifest.resolved_query?.fallback_used && (
              <span className="text-xs text-muted-foreground">
                router fallback used
              </span>
            )}
          </div>
          <p className="text-sm font-medium leading-snug">{manifest.question}</p>
          {manifest.error && (
            <p className="text-xs text-destructive">{manifest.error}</p>
          )}
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span>cache hits: {manifest.papers_cache_hits}</span>
            <span>misses: {manifest.papers_cache_misses}</span>
            <span>papers: {manifest.ranked_papers.length}</span>
          </div>
        </div>
        {inFlight && !manifest.cancel_requested && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => cancel.mutate()}
            disabled={cancel.isPending}
          >
            Cancel
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
