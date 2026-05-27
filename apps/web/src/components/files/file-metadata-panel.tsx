"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { useFileMetadata } from "@/lib/queries";
import type { FileMetadata } from "@arxiv-insight-briefs/shared";

interface FileMetadataPanelProps {
  file: FileMetadata | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function MetaRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex justify-between text-sm gap-4">
      <span className="text-muted-foreground shrink-0">{label}</span>
      <span className="font-mono text-right max-w-[60%] truncate">{value}</span>
    </div>
  );
}

export function FileMetadataPanel({ file, open, onOpenChange }: FileMetadataPanelProps) {
  // Detail call is gated on the dialog being open AND a file selected — the
  // hook handles both via `enabled`.
  const { data, isLoading } = useFileMetadata(open && file ? file.key : undefined);

  if (!file) return null;

  const isImage = file.content_type.startsWith("image/");
  const isPdf = file.content_type === "application/pdf";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="truncate">{file.filename}</DialogTitle>
          <DialogDescription className="font-mono text-xs truncate">
            {file.key}
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-5 w-full" />
            ))}
          </div>
        ) : data ? (
          <div className="space-y-3">
            <MetaRow label="Size" value={data.size_human} />
            <MetaRow label="Type" value={data.mime_type} />
            <MetaRow label="Extension" value={data.extension || "none"} />
            {data.etag && <MetaRow label="ETag" value={data.etag} />}
            <MetaRow
              label="Uploaded"
              value={new Date(data.uploaded_at).toLocaleString()}
            />
            {/* This sample drops Pillow + PyPDF2 from the starter to keep the
                deps focused on the briefing pipeline. The detail view
                degrades gracefully for image/PDF objects rather than
                showing partial information. */}
            {(isImage || isPdf) && (
              <>
                <Separator />
                <p className="text-xs text-muted-foreground italic">
                  No detailed metadata available for {isImage ? "images" : "PDFs"}
                  &nbsp;— this sample omits Pillow / PyPDF2 to keep dependencies
                  scoped to the briefing pipeline.
                </p>
              </>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            No details available for this object.
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}
