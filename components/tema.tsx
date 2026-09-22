"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { ThemeProvider as NextThemes, useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { TooltipProvider } from "@/components/ui/tooltip";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function PenyediaTema({ children }: { children: React.ReactNode }) {
  return (
    <NextThemes attribute="class" defaultTheme="dark" enableSystem disableTransitionOnChange>
      <TooltipProvider delayDuration={300}>{children}</TooltipProvider>
    </NextThemes>
  );
}

const PILIHAN = [
  { nilai: "light", label: "Terang", icon: Sun },
  { nilai: "dark", label: "Gelap", icon: Moon },
  { nilai: "system", label: "Ikut sistem", icon: Monitor },
] as const;

export function TombolTema() {
  const { theme, setTheme } = useTheme();
  const [siap, setSiap] = useState(false);

  // Tema baru diketahui setelah di browser. Sebelum itu ikonnya ditahan
  // supaya tidak berkedip berganti saat halaman selesai dimuat.
  useEffect(() => setSiap(true), []);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="size-8" aria-label="Ganti tema">
          {siap && theme === "light" ? <Sun className="size-4" /> : <Moon className="size-4" />}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {PILIHAN.map((p) => (
          <DropdownMenuItem
            key={p.nilai}
            onClick={() => setTheme(p.nilai)}
            className={siap && theme === p.nilai ? "bg-accent" : undefined}
          >
            <p.icon />
            {p.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
