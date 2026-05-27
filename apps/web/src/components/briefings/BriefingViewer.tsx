"use client";

import type { ComponentPropsWithoutRef } from "react";
import ReactMarkdown from "react-markdown";

import { Card, CardContent } from "@/components/ui/card";

/**
 * Markdown renderer for a generated brief.
 *
 * Uses `react-markdown` so ordered lists, nested formatting, and fenced
 * code blocks all render correctly. The server has already rewritten
 * citation placeholders `[arxiv:ID]` to anchor tags pointing at presigned
 * GETs in B2; we only need to style the resulting `<a>` so an arxiv
 * citation reads as a chip and every other link reads as a regular link.
 */

interface BriefingViewerProps {
  markdown: string;
}

// Citation links are emitted as `[arxiv:ID](url)` by the API. Detect them
// by inspecting the href instead of the label: `react-markdown` v9 passes
// link children as React elements (e.g. an array of text nodes from an
// inline `<code>`), so a `typeof === "string"` check on `children` misses
// the chip case. The href is server-controlled — the synthesis citation
// rewriter presigns `papers/{arxiv_id}.pdf` in B2 — so matching on the
// `/papers/` path component and the `.pdf` extension is the stable signal.
const ARXIV_CITATION_HREF = /\/papers\/[A-Za-z0-9._-]+\.pdf(?:\?|$)/;

function MarkdownLink({
  href,
  children,
  ...rest
}: ComponentPropsWithoutRef<"a">) {
  const isCitation = typeof href === "string" && ARXIV_CITATION_HREF.test(href);
  const className = isCitation
    ? "inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-mono bg-muted hover:bg-accent transition-colors no-underline"
    : "underline text-primary";
  return (
    <a
      {...rest}
      href={href}
      className={className}
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
    </a>
  );
}

export function BriefingViewer({ markdown }: BriefingViewerProps) {
  return (
    <Card>
      <CardContent
        className="p-6 prose-like"
        data-testid="briefing-viewer-content"
      >
        <ReactMarkdown
          components={{
            a: MarkdownLink,
          }}
        >
          {markdown}
        </ReactMarkdown>
      </CardContent>
    </Card>
  );
}
