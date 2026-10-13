"use client";

import { Moon, Sun } from "lucide-react";
import { ThemeProvider as NextThemes, useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { TooltipProvider } from "@/components/ui/tooltip";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemes attribute="class" defaultTheme="dark" enableSystem disableTransitionOnChange>
      <TooltipProvider delayDuration={300}>{children}</TooltipProvider>
    </NextThemes>
  );
}

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // The theme is only known once we're in the browser. Until then the icon is
  // held back so it doesn't flicker when the page finishes loading.
  // eslint-disable-next-line react-hooks/set-state-in-effect -- hydration marker for the browser-only theme
  useEffect(() => setMounted(true), []);

  // resolvedTheme, not theme. Someone who has never chosen sits on "system",
  // and comparing that against "dark" sends the first click to the theme they
  // are already looking at, which reads as a button that does nothing.
  const dark = resolvedTheme === "dark";
  const next = dark ? "light" : "dark";

  return (
    <Button
      variant="ghost"
      size="icon"
      className="size-8"
      // The label states what the click does; the icon shows where you are.
      aria-label={mounted ? `Switch to ${next} theme` : "Change theme"}
      onClick={() => setTheme(next)}
    >
      {mounted && !dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </Button>
  );
}
