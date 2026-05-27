"use client";

import { useState } from "react";
import { useTheme } from "next-themes";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";

import { useClearAllBriefings, useHealth } from "@/lib/queries";

export function SettingsForm() {
  const { theme, setTheme } = useTheme();
  const { data: health } = useHealth({ refetchIntervalMs: 30_000 });
  const clearAll = useClearAllBriefings();
  const [confirmOpen, setConfirmOpen] = useState(false);

  // Wrap the bulk-clear so the dialog dismisses on success/failure and
  // the user gets unambiguous feedback either way.
  const handleConfirmClear = () => {
    clearAll.mutate(undefined, {
      onSuccess: ({ deleted }) => {
        toast.success(
          deleted === 0
            ? "No cached briefings to remove."
            : `Cleared ${deleted} cached briefing object${deleted === 1 ? "" : "s"}.`,
        );
        setConfirmOpen(false);
      },
      onError: (err) => {
        toast.error(err.message || "Failed to clear briefings.");
        setConfirmOpen(false);
      },
    });
  };

  return (
    <div className="space-y-6">
      {/* Status panel — surfaces the same info the health banner relies on. */}
      <Card>
        <CardHeader className="border-b border-border py-4 px-5">
          <CardTitle className="card-title">Upstream status</CardTitle>
        </CardHeader>
        <CardContent className="p-5 space-y-3 text-sm">
          <StatusRow
            label="Backblaze B2"
            ok={!!health?.b2_connected}
            okText="Connected"
            failText="Not connected — check .env credentials and bucket region"
          />
          <StatusRow
            label="NVIDIA Build (Nemotron)"
            ok={!!health?.nvidia_configured}
            okText="Configured"
            failText="No API key — pipeline will skip LLM stages and produce a 'no analysis' brief"
          />
        </CardContent>
      </Card>

      {/* Preferences */}
      <Card>
        <CardHeader className="border-b border-border py-4 px-5">
          <CardTitle className="card-title">Preferences</CardTitle>
        </CardHeader>
        <CardContent className="p-5 space-y-4">
          <div className="space-y-2">
            <p className="text-sm font-medium">Theme</p>
            <RadioGroup
              onValueChange={setTheme}
              value={theme ?? "system"}
              className="flex gap-6"
            >
              {(["light", "dark", "system"] as const).map((t) => (
                <label
                  key={t}
                  className="flex items-center gap-2 text-sm capitalize cursor-pointer"
                >
                  <RadioGroupItem value={t} />
                  {t}
                </label>
              ))}
            </RadioGroup>
          </div>
        </CardContent>
      </Card>

      {/* Danger zone — only `briefs/` is removed; the shared `papers/` PDF
          cache is preserved (server-side invariant in delete_prefix). */}
      <Card className="border-[color-mix(in_oklab,var(--destructive)_30%,var(--border))]">
        <CardHeader className="border-b border-border py-4 px-5">
          <CardTitle className="card-title text-destructive">
            Danger zone
          </CardTitle>
        </CardHeader>
        <CardContent className="p-5 space-y-4">
          <div className="space-y-1">
            <p className="text-sm font-medium">Clear cached briefings</p>
            <p className="text-xs text-muted-foreground">
              Permanently deletes every brief manifest and rendered markdown
              under the <code className="font-mono text-[11px]">briefs/</code>{" "}
              prefix in B2. The cached PDFs under{" "}
              <code className="font-mono text-[11px]">papers/</code> are{" "}
              <strong>kept</strong> so future briefs can reuse them.
            </p>
          </div>
          <Button
            variant="destructive"
            size="sm"
            onClick={() => setConfirmOpen(true)}
            disabled={clearAll.isPending}
          >
            {clearAll.isPending ? "Clearing…" : "Clear cached briefings"}
          </Button>
        </CardContent>
      </Card>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Clear all cached briefings?</AlertDialogTitle>
            <AlertDialogDescription>
              This removes every brief in B2 under the{" "}
              <code className="font-mono text-[11px]">briefs/</code> prefix.
              Cached PDFs (
              <code className="font-mono text-[11px]">papers/</code>) are
              preserved. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={clearAll.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                // AlertDialogAction closes the dialog by default; defer the
                // close to the mutation's settled callbacks so the spinner
                // stays visible while the request is in flight.
                e.preventDefault();
                handleConfirmClear();
              }}
              disabled={clearAll.isPending}
            >
              {clearAll.isPending ? "Clearing…" : "Clear briefings"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function StatusRow({
  label,
  ok,
  okText,
  failText,
}: {
  label: string;
  ok: boolean;
  okText: string;
  failText: string;
}) {
  return (
    <div className="flex items-start justify-between gap-3">
      <p className="text-sm font-medium">{label}</p>
      <p
        className={`text-xs ${ok ? "text-emerald-600" : "text-[var(--attention)]"}`}
      >
        {ok ? okText : failText}
      </p>
    </div>
  );
}
