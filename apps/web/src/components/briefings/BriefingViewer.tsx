"use client";

import { useMemo } from "react";

import { Card, CardContent } from "@/components/ui/card";

/**
 * Very small inline markdown renderer.
 *
 * We deliberately avoid pulling in `react-markdown` for v1 — the brief is
 * server-rendered text we control, and we only need:
 *   - `# H1`, `## H2`, `### H3`
 *   - `**bold**`
 *   - `*italic*` / `_italic_`
 *   - `- bullet` lists
 *   - `> blockquote`
 *   - Hyperlinks `[label](url)` (the server rewrites `[arxiv:ID]` to these)
 *
 * Citations show up as `[arxiv:ID](https://...presigned...)` and render as
 * clickable badges — that's the whole UX point.
 */

interface BriefingViewerProps {
  markdown: string;
}

export function BriefingViewer({ markdown }: BriefingViewerProps) {
  const html = useMemo(() => renderMarkdown(markdown), [markdown]);
  return (
    <Card>
      <CardContent className="p-6 prose-like" dangerouslySetInnerHTML={{ __html: html }} />
    </Card>
  );
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderInline(text: string): string {
  let out = escapeHtml(text);
  // Links: [label](url) — must run before bold/italic so anchor labels can be styled.
  out = out.replace(
    /\[arxiv:([A-Za-z0-9._-]+)\]\(([^)]+)\)/g,
    (_, id, url) =>
      `<a href="${url}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-mono bg-muted hover:bg-accent transition-colors">arxiv:${id}</a>`,
  );
  out = out.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    (_, label, url) =>
      `<a href="${url}" target="_blank" rel="noopener noreferrer" class="underline text-primary">${label}</a>`,
  );
  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/(^|\s)_([^_]+)_/g, "$1<em>$2</em>");
  out = out.replace(/(^|\s)\*([^*]+)\*/g, "$1<em>$2</em>");
  out = out.replace(/`([^`]+)`/g, "<code class=\"font-mono text-[12px] bg-muted px-1 py-0.5 rounded\">$1</code>");
  return out;
}

function renderMarkdown(md: string): string {
  const lines = md.split(/\r?\n/);
  const blocks: string[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i += 1;
      continue;
    }
    if (line.startsWith("### ")) {
      blocks.push(`<h3>${renderInline(line.slice(4))}</h3>`);
      i += 1;
    } else if (line.startsWith("## ")) {
      blocks.push(`<h2>${renderInline(line.slice(3))}</h2>`);
      i += 1;
    } else if (line.startsWith("# ")) {
      blocks.push(`<h1>${renderInline(line.slice(2))}</h1>`);
      i += 1;
    } else if (line.startsWith("> ")) {
      const buf: string[] = [];
      while (i < lines.length && lines[i].startsWith("> ")) {
        buf.push(lines[i].slice(2));
        i += 1;
      }
      blocks.push(`<blockquote>${renderInline(buf.join(" "))}</blockquote>`);
    } else if (line.startsWith("- ") || line.startsWith("* ")) {
      const buf: string[] = [];
      while (i < lines.length && (lines[i].startsWith("- ") || lines[i].startsWith("* "))) {
        buf.push(`<li>${renderInline(lines[i].slice(2))}</li>`);
        i += 1;
      }
      blocks.push(`<ul>${buf.join("")}</ul>`);
    } else {
      // Plain paragraph: consume until blank line.
      const buf: string[] = [];
      while (i < lines.length && lines[i].trim() && !lines[i].startsWith("#") && !lines[i].startsWith(">") && !lines[i].startsWith("- ")) {
        buf.push(lines[i]);
        i += 1;
      }
      blocks.push(`<p>${renderInline(buf.join(" "))}</p>`);
    }
  }
  return blocks.join("\n");
}
