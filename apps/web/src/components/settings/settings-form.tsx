"use client";

import { useTheme } from "next-themes";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { useQuery } from "@tanstack/react-query";

import { getHealth } from "@/lib/api-client";

export function SettingsForm() {
  const { theme, setTheme } = useTheme();
  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 30_000,
  });

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
