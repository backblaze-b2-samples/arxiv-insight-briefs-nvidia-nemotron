"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  ApiError,
  cancelBriefing,
  clearBriefing,
  getBriefing,
  listBriefings,
  submitBriefing,
} from "@/lib/api-client";
import type {
  BriefDetail,
  BriefRequest,
  BriefSummary,
} from "@arxiv-insight-briefs/shared";

// Single source of truth for query keys. Keep them tightly scoped so
// invalidating "briefings" doesn't blow away unrelated caches.
export const qk = {
  all: ["b2"] as const,
  briefings: () => [...qk.all, "briefings"] as const,
  briefing: (id: string) => [...qk.briefings(), id] as const,
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
