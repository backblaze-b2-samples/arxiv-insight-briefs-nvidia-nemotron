"use client";

import Link from "next/link";

import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useBriefings } from "@/lib/queries";

import { StatusBadge } from "./StatusBadge";

export function ArchiveList() {
  const { data, isLoading, isError, error, refetch } = useBriefings();

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-20" />
        ))}
      </div>
    );
  }
  if (isError) {
    return (
      <ErrorState
        title="Couldn't load briefings"
        description={error?.message ?? "Unknown error"}
        onRetry={() => refetch()}
      />
    );
  }
  if (!data || data.length === 0) {
    return (
      <EmptyState
        title="No briefings yet"
        description="Submit your first research question on the New brief page."
      />
    );
  }

  return (
    <div className="space-y-3">
      {data.map((b) => (
        <Link key={b.brief_id} href={`/briefings/${b.brief_id}`}>
          <Card className="hover:bg-accent/30 transition-colors cursor-pointer">
            <CardContent className="p-4 flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1 space-y-1">
                <p className="text-sm font-medium line-clamp-2">{b.question}</p>
                <p className="text-xs text-muted-foreground font-mono">
                  {b.brief_id.slice(0, 8)} ·{" "}
                  {new Date(b.created_at).toLocaleString()} · {b.paper_count}{" "}
                  papers
                </p>
              </div>
              <StatusBadge status={b.status} />
            </CardContent>
          </Card>
        </Link>
      ))}
    </div>
  );
}
