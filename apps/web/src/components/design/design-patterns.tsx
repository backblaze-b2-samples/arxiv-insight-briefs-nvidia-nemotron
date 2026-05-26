"use client";

import { Inbox, FileIcon } from "lucide-react";
import type { ColumnDef } from "@tanstack/react-table";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { DataTable } from "@/components/ui/data-table";
import { ApiError } from "@/lib/api-client";
import { Section } from "./section";

// Demo errors for the ErrorState showcase. These are constructed, not
// thrown — `ErrorState` reads `status` to derive the right copy.
const offlineError = new ApiError("Network error — check your connection", 0);
const serverError = new ApiError("Internal Server Error", 500);

type Row = { arxiv_id: string; title: string; category: string };

const sampleRows: Row[] = [
  { arxiv_id: "2401.12345", title: "Efficient large-block file transfer over QUIC", category: "cs.NI" },
  { arxiv_id: "2403.04567", title: "BBR v3 and the loss recovery problem", category: "cs.NI" },
  { arxiv_id: "2406.99001", title: "Adaptive striping for object-store reads", category: "cs.DC" },
  { arxiv_id: "2408.55512", title: "End-to-end congestion signal sharing", category: "cs.NI" },
];

const columns: ColumnDef<Row>[] = [
  {
    accessorKey: "title",
    header: "Title",
    size: 360,
    cell: ({ row }) => (
      <span className="flex items-center gap-2">
        <FileIcon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        <span className="font-medium truncate">{row.original.title}</span>
      </span>
    ),
  },
  {
    accessorKey: "arxiv_id",
    header: "arXiv id",
    size: 140,
    cell: ({ row }) => (
      <span className="font-mono text-xs text-muted-foreground tabular-nums">
        {row.original.arxiv_id}
      </span>
    ),
  },
  {
    accessorKey: "category",
    header: "Category",
    size: 120,
    cell: ({ row }) => (
      <span className="text-muted-foreground font-mono text-xs">
        {row.original.category}
      </span>
    ),
  },
];

export function DesignPatterns() {
  return (
    <Section
      id="patterns"
      title="Patterns"
      description="Composed building blocks — empty states, sortable tables, page headers."
    >
      <div className="grid gap-4">
        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">Empty state</CardTitle>
          </CardHeader>
          <CardContent className="p-5">
            <EmptyState
              icon={Inbox}
              title="No briefings yet"
              description="Submit your first research question on the New brief page."
              action={
                <Button size="sm" variant="outline">
                  New brief
                </Button>
              }
            />
          </CardContent>
        </Card>

        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader className="border-b border-border py-4 px-5">
              <CardTitle className="card-title">Error state — offline</CardTitle>
            </CardHeader>
            <CardContent className="p-5">
              <ErrorState error={offlineError} onRetry={() => {}} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="border-b border-border py-4 px-5">
              <CardTitle className="card-title">Error state — backend 5xx</CardTitle>
            </CardHeader>
            <CardContent className="p-5">
              <ErrorState error={serverError} onRetry={() => {}} />
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">
              Sortable data table
            </CardTitle>
          </CardHeader>
          <CardContent className="p-5">
            <DataTable
              columns={columns}
              data={sampleRows}
              pageSize={5}
              emptyTitle="No papers"
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">
              Command palette
            </CardTitle>
          </CardHeader>
          <CardContent className="p-5 text-sm text-muted-foreground">
            Press{" "}
            <kbd className="text-[10px] font-mono border border-border rounded px-1 py-0.5">
              ⌘K
            </kbd>{" "}
            or{" "}
            <kbd className="text-[10px] font-mono border border-border rounded px-1 py-0.5">
              /
            </kbd>{" "}
            anywhere to jump between briefings and pages.
          </CardContent>
        </Card>
      </div>
    </Section>
  );
}
