import { FileBrowser } from "@/components/files/file-browser";

// Read-write file explorer over the configured B2 prefix. Lets the user
// inspect what's actually in the bucket — papers/ cache PDFs, brief/manifest
// JSON, generated brief.md files — and delete any of them. There's no guard
// on `papers/` (chosen explicitly: bucket observability over safety rails).
export default function FilesPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5">
        <h1 className="page-title">Files</h1>
        <p className="text-sm text-muted-foreground mt-1.5">
          Browse and manage everything in your B2 prefix. Full CRUD — including
          cached papers and brief archives.
        </p>
      </div>
      <div className="animate-fade-in-up stagger-2">
        <FileBrowser />
      </div>
    </div>
  );
}
