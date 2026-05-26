"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSubmitBriefing } from "@/lib/queries";

const EXAMPLES = [
  "Latest research on sending files over the internet",
  "State of vector quantization for retrieval (2024-2025)",
  "What's new in low-latency video streaming for live sports?",
];

export function SubmitForm() {
  const router = useRouter();
  const submit = useSubmitBriefing();
  const [question, setQuestion] = useState("");
  const [months, setMonths] = useState<number | "">(12);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;
    const result = await submit.mutateAsync({
      question: question.trim(),
      time_window_months: typeof months === "number" ? months : null,
    });
    router.push(`/briefings/${result.brief_id}`);
  };

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <div className="space-y-2">
        <Label htmlFor="question" className="text-sm font-medium">
          What do you want a brief on?
        </Label>
        <Textarea
          id="question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. latest research on sending files over the internet"
          rows={4}
          className="resize-none"
          autoFocus
          maxLength={500}
        />
        <p className="text-xs text-muted-foreground">
          Ask like you would ask a colleague — your phrasing anchors the synthesis.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-md">
        <div className="space-y-2">
          <Label htmlFor="months" className="text-sm font-medium">
            Time window (months)
          </Label>
          <Input
            id="months"
            type="number"
            min={1}
            max={120}
            value={months}
            onChange={(e) => {
              const v = e.target.value;
              setMonths(v === "" ? "" : Math.max(1, Math.min(120, Number(v))));
            }}
            className="w-32 font-mono tabular-nums"
          />
        </div>
      </div>

      <div className="flex flex-wrap gap-2 items-center">
        <Button type="submit" disabled={submit.isPending || !question.trim()}>
          {submit.isPending ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Submitting...
            </>
          ) : (
            "Run brief"
          )}
        </Button>
        {submit.isError && (
          <span className="text-xs text-destructive">
            {submit.error?.message ?? "Failed to submit"}
          </span>
        )}
      </div>

      <div className="pt-4 border-t border-border">
        <p className="text-xs uppercase tracking-wider text-muted-foreground mb-2">
          Try an example
        </p>
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => setQuestion(q)}
              className="text-xs px-2.5 py-1.5 rounded-md border border-border hover:bg-muted transition-colors"
            >
              {q}
            </button>
          ))}
        </div>
      </div>
    </form>
  );
}
