import { Outlet } from "react-router-dom";

import { Sidebar } from "@/components/shell/Sidebar";
import { GlobalFilters } from "@/components/shell/GlobalFilters";

// The overall layout frame: fixed sidebar on the left, a sticky global-filter
// header, and the routed page below it. <Outlet/> is React Router's slot where
// the matched child route renders — like a layout template with a content
// placeholder that each page fills in.
export function AppShell() {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <GlobalFilters />
        <main className="flex-1 overflow-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
