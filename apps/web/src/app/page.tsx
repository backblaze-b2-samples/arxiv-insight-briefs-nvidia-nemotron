import Link from "next/link";

import { Card, CardContent } from "@/components/ui/card";
import { SubmitForm } from "@/components/briefings/SubmitForm";
import { ArchiveList } from "@/components/briefings/ArchiveList";

export default function NewBriefPage() {
  return (
    <div className="space-y-10">
      <div className="animate-fade-in border-b border-border pb-5">
        <h1 className="page-title">New brief</h1>
        <p className="text-sm text-muted-foreground mt-1.5 max-w-2xl">
          Ask a research question — we resolve it to arxiv categories, rank
          the most recent abstracts, and synthesize a problem-anchored brief.
          PDFs and the brief itself are archived in your Backblaze B2 bucket.
        </p>
      </div>

      <div className="grid gap-8 lg:grid-cols-[2fr,1fr]">
        <div className="animate-fade-in-up stagger-2 max-w-2xl">
          <Card>
            <CardContent className="p-6">
              <SubmitForm />
            </CardContent>
          </Card>
        </div>
        <div className="animate-fade-in-up stagger-3 space-y-3">
          <div className="flex items-baseline justify-between">
            <h2 className="card-title">Recent briefings</h2>
            <Link
              href="/briefings"
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              View all
            </Link>
          </div>
          <ArchiveList />
        </div>
      </div>
    </div>
  );
}
