import { AppSidebar } from "@/components/app-sidebar";
import { Separator } from "@/components/ui/separator";
import {
  SidebarInset, SidebarProvider, SidebarTrigger,
} from "@/components/ui/sidebar";
import { JudulHalaman } from "@/components/judul-halaman";
import { TombolTema } from "@/components/tema";
import { saya } from "@/app/lib";

export default async function LayoutAplikasi({ children }: { children: React.ReactNode }) {
  const aku = await saya();

  return (
    <SidebarProvider>
      <AppSidebar pengguna={aku ?? undefined} />
      <SidebarInset>
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-2 h-4" />
          <JudulHalaman />

          <div className="ml-auto">
            <TombolTema />
          </div>
        </header>
        {children}
      </SidebarInset>
    </SidebarProvider>
  );
}
