"use client";

import { useRouter } from "next/navigation";
import {
  FileText,
  Archive,
  Settings,
  Sparkles,
  Moon,
  Sun,
} from "lucide-react";
import { useTheme } from "next-themes";

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command";
import { useBriefings } from "@/lib/queries";

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const routes = [
  { label: "New brief", href: "/", icon: FileText, hint: "N" },
  { label: "Archive", href: "/briefings", icon: Archive, hint: "A" },
  { label: "Settings", href: "/settings", icon: Settings },
  { label: "Design system", href: "/design", icon: Sparkles },
];

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const router = useRouter();
  const { setTheme } = useTheme();
  // Briefings cache is shared with the archive page, so this is free.
  const { data: briefings } = useBriefings();

  const runThen = (fn: () => void) => () => {
    onOpenChange(false);
    fn();
  };

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput placeholder="Jump to a brief or page..." />
      <CommandList>
        <CommandEmpty>No matches found.</CommandEmpty>
        <CommandGroup heading="Navigate">
          {routes.map((r) => (
            <CommandItem
              key={r.href}
              onSelect={runThen(() => router.push(r.href))}
              value={`nav ${r.label}`}
            >
              <r.icon />
              {r.label}
              {r.hint && <CommandShortcut>{r.hint}</CommandShortcut>}
            </CommandItem>
          ))}
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading="Theme">
          <CommandItem onSelect={runThen(() => setTheme("light"))} value="theme light">
            <Sun />
            Light mode
          </CommandItem>
          <CommandItem onSelect={runThen(() => setTheme("dark"))} value="theme dark">
            <Moon />
            Dark mode
          </CommandItem>
          <CommandItem onSelect={runThen(() => setTheme("system"))} value="theme system">
            <Sparkles />
            System theme
          </CommandItem>
        </CommandGroup>
        {briefings && briefings.length > 0 && (
          <>
            <CommandSeparator />
            <CommandGroup heading="Recent briefings">
              {briefings.slice(0, 20).map((b) => (
                <CommandItem
                  key={b.brief_id}
                  value={`brief ${b.question} ${b.brief_id}`}
                  onSelect={runThen(() => router.push(`/briefings/${b.brief_id}`))}
                >
                  <FileText />
                  <span className="truncate">{b.question}</span>
                  <CommandShortcut>{b.status}</CommandShortcut>
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        )}
      </CommandList>
    </CommandDialog>
  );
}
