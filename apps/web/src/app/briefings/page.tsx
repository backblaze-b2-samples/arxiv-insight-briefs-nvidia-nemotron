import { ArchiveList } from "@/components/briefings/ArchiveList";

export default function BriefingsPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5">
        <h1 className="page-title">Archive</h1>
        <p className="text-sm text-muted-foreground mt-1.5 max-w-2xl">
          Every briefing you&apos;ve generated, sourced live from B2. The bucket
          is the archive — there is no database.
        </p>
      </div>
      <div className="animate-fade-in-up stagger-2 max-w-3xl">
        <ArchiveList />
      </div>
    </div>
  );
}
