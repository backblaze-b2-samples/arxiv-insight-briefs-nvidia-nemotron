"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  ApiError,
  cancelBriefing,
  clearAllBriefings,
  clearBriefing,
  deleteFile,
  getBriefing,
  getFileMetadata,
  getHealth,
  listBriefings,
  listFiles,
  submitBriefing,
} from "@/lib/api-client";
import type {
  BriefDetail,
  BriefRequest,
  BriefSummary,
  FileMetadata,
  FileMetadataDetail,
  HealthStatus,
} from "@arxiv-insight-briefs/shared";

// Single source of truth for query keys. Keep them tightly scoped so
// invalidating "briefings" doesn't blow away unrelated caches.
export const qk = {
  all: ["b2"] as const,
  health: () => [...qk.all, "health"] as const,
  briefings: () => [...qk.all, "briefings"] as const,
  briefing: (id: string) => [...qk.briefings(), id] as const,
  files: (prefix?: string, limit?: number) =>
    [...qk.all, "files", prefix ?? "", limit ?? 200] as const,
  fileMetadata: (key: string) => [...qk.all, "files", "metadata", key] as const,
};

// Active statuses that warrant polling — finished briefs are static.
const ACTIVE_STATUSES = new Set([
  "queued",
  "routing",
  "searching",
  "ranking",
  "fetching_pdfs",
  "synthesizing",
]);

/**
 * Polls `/health` every 60s (and on window focus). `refetchInterval` keeps
 * the banner reactive when B2 credentials are rotated mid-session;
 * `retry: false` keeps a flapping API from spamming the toast queue.
 *
 * Pass an `enabled: false` override if you want to suppress polling for a
 * route that owns its own health surface.
 */
export function useHealth(options?: { refetchIntervalMs?: number }) {
  return useQuery<HealthStatus | null, ApiError>({
    queryKey: qk.health(),
    // Swallow failures into `null` so consumers branch on `data?` rather than
    // forcing every component to handle the error state explicitly.
    queryFn: () => getHealth().catch(() => null),
    refetchInterval: options?.refetchIntervalMs ?? 60_000,
    staleTime: 30_000,
    retry: false,
  });
}

export function useBriefings() {
  return useQuery<BriefSummary[], ApiError>({
    queryKey: qk.briefings(),
    queryFn: () => listBriefings(),
  });
}

export function useBriefing(id: string | undefined) {
  return useQuery<BriefDetail, ApiError>({
    queryKey: qk.briefing(id ?? ""),
    queryFn: () => getBriefing(id as string),
    enabled: !!id,
    // Poll active briefs every 2s; stop polling once we reach a terminal state.
    refetchInterval: (query) => {
      const status = query.state.data?.manifest.status;
      return status && ACTIVE_STATUSES.has(status) ? 2_000 : false;
    },
  });
}

export function useSubmitBriefing() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: BriefRequest) => submitBriefing(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.briefings() });
    },
  });
}

export function useCancelBriefing(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => cancelBriefing(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.briefing(id) });
    },
  });
}

export function useClearBriefing() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => clearBriefing(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.briefings() });
    },
  });
}

/**
 * Bulk-clear every brief in B2. Used by Settings → danger zone.
 *
 * The server enforces that only the `briefs/` prefix is touched — the
 * shared PDF cache (`papers/`) is preserved across this action.
 */
export function useClearAllBriefings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => clearAllBriefings(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.briefings() });
    },
  });
}

/* ---------- File browser ---------- */
// Restored from the starter; unguarded by design. See
// `docs/features/file-browser.md` for the contract.

export function useFiles({ prefix = "", limit = 200 }: { prefix?: string; limit?: number } = {}) {
  return useQuery<FileMetadata[], ApiError>({
    queryKey: qk.files(prefix, limit),
    queryFn: () => listFiles(prefix, limit),
  });
}

export function useFileMetadata(key: string | undefined) {
  return useQuery<FileMetadataDetail, ApiError>({
    queryKey: qk.fileMetadata(key ?? ""),
    queryFn: () => getFileMetadata(key as string),
    enabled: !!key,
    staleTime: 60_000,
  });
}

export function useDeleteFile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (key: string) => deleteFile(key),
    // After a delete the file list AND any briefing that referenced the
    // object are stale — easiest correct move is to blow away every
    // `b2` query so dependent surfaces refetch lazily.
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.all });
    },
  });
}
