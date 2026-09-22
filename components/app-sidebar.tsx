"use client";

import {
  Boxes, Calculator, Database, FileText, Inbox, LayoutDashboard, Mail,
  MessagesSquare, PackageSearch, ScrollText, Settings2, Ship, TrendingUp,
  Upload, Users, Zap,
} from "lucide-react";

import { NavPengguna } from "@/components/nav-pengguna";
import { NavUtama, type Butir } from "@/components/nav-utama";
import { StatusSambungan, type Sambungan } from "@/components/status-sambungan";
import {
  Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarRail,
} from "@/components/ui/sidebar";

const KERJA: Butir[] = [
  { judul: "Dasbor", href: "/dasbor", icon: LayoutDashboard },
  { judul: "Antrean keputusan", href: "/", icon: Inbox },
  { judul: "Percakapan", href: "/chat", icon: MessagesSquare },
];

const DATA: Butir[] = [
  {
    judul: "Data pasokan",
    href: "/data",
    icon: Database,
    anak: [
      { judul: "Permintaan", href: "/data/permintaan", oleh: "Dara" },
      { judul: "Stok", href: "/data/stok", oleh: "Iris" },
      { judul: "Sumber pasokan", href: "/data/sumber", oleh: "Clint" },
      { judul: "Logistik", href: "/data/logistik", oleh: "Milo" },
      { judul: "Perhitungan", href: "/data/perhitungan", oleh: "Tara" },
      { judul: "Eksekusi", href: "/data/eksekusi", oleh: "Bram" },
    ],
  },
  { judul: "Tim agent", href: "/agent", icon: Users },
];

const CATATAN: Butir[] = [
  { judul: "Log", href: "/log", icon: ScrollText },
  { judul: "Laporan", href: "/laporan", icon: FileText },
];

const ATUR: Butir[] = [
  {
    judul: "Pengaturan",
    href: "/atur",
    icon: Settings2,
    anak: [
      { judul: "Unggah data", href: "/unggah" },
      { judul: "Kontak", href: "/kontak" },
    ],
  },
];

export function AppSidebar({
  pengguna, sambungan, ...props
}: {
  pengguna?: { nama: string; peran: string; email: string };
  sambungan?: Sambungan;
} & React.ComponentProps<typeof Sidebar>) {
  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <StatusSambungan s={sambungan} />
      </SidebarHeader>

      <SidebarContent>
        <NavUtama butir={KERJA} />
        <NavUtama label="Data" butir={DATA} />
        <NavUtama label="Catatan" butir={CATATAN} />
        <NavUtama butir={ATUR} />
      </SidebarContent>

      <SidebarFooter>
        <NavPengguna pengguna={pengguna} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
