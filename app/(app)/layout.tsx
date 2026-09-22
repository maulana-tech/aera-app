import { AppSidebar } from "@/components/app-sidebar";
import { Remah } from "@/components/remah";
import { TombolTema } from "@/components/tema";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { ambil, saya } from "@/app/lib";

export default async function LayoutAplikasi({ children }: { children: React.ReactNode }) {
  const [aku, sehat] = await Promise.all([
    saya(),
    ambil<{ lingkungan: string; sap_siap: boolean; model_siap: boolean }>("sehat"),
  ]);

  return (
    <SidebarProvider>
      <AppSidebar pengguna={aku ?? undefined} sambungan={sehat ?? undefined} />
      <SidebarInset>
        <header className="bg-background/80 sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b px-4 backdrop-blur">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-2 h-4" />
          <Remah />
          <div className="ml-auto">
            <TombolTema />
          </div>
        </header>
        {children}
      </SidebarInset>
    </SidebarProvider>
  );
}
