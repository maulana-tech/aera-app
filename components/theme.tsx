"use client";

import { ThemeProvider as NextThemes } from "next-themes";

import { TooltipProvider } from "@/components/ui/tooltip";

/** Light only: the blue canvas is the brand (see app/globals.css). */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemes attribute="class" forcedTheme="light" defaultTheme="light" enableSystem={false} disableTransitionOnChange>
      <TooltipProvider delayDuration={300}>{children}</TooltipProvider>
    </NextThemes>
  );
}
