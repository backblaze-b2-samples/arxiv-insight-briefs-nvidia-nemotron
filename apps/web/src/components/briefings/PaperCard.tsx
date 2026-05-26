"use client";

import { ExternalLink } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { RankedPaper } from "@arxiv-insight-briefs/shared";

export function PaperCard({ paper }: { paper: RankedPaper }) {
  const authorLabel =
    paper.authors.length > 3
      ? `${paper.authors.slice(0, 3).join(", ")} +${paper.authors.length - 3}`
      : paper.authors.join(", ");

  return (
    <Card>
      <CardContent className="p-5 space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1 space-y-1">
            <h3 className="font-semibold text-sm leading-snug">{paper.title}</h3>
            <p className="text-xs text-muted-foreground">{authorLabel}</p>
          </div>
          <div className="flex flex-col items-end gap-1 shrink-0">
            <Badge variant="outline" className="font-mono text-[10px]">
              {paper.primary_category}
            </Badge>
            {paper.cached && (
              <Badge variant="secondary" className="text-[10px]">
                served from cache
              </Badge>
            )}
            {paper.relevance_score !== null && paper.relevance_score !== undefined && (
              <Badge className="text-[10px] bg-blue-600 text-white">
                score {paper.relevance_score.toFixed(1)}
              </Badge>
            )}
          </div>
        </div>
        {paper.rank_reason && (
          <p className="text-xs text-muted-foreground italic line-clamp-2">
            {paper.rank_reason}
          </p>
        )}
        <p className="text-xs leading-relaxed line-clamp-4">{paper.abstract}</p>
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <a
            href={paper.pdf_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 underline text-primary"
          >
            <ExternalLink className="h-3 w-3" />
            Open PDF
          </a>
          <span className="font-mono text-muted-foreground">
            arxiv:{paper.arxiv_id}
          </span>
          {paper.extraction_status !== "ok" && paper.extraction_status !== "pending" && (
            <span className="text-destructive">
              {paper.extraction_status.replace("_", " ")}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
