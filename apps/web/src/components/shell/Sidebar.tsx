import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  ArrowLeftRight,
  TrendingUp,
  Landmark,
  Lightbulb,
  MessageSquare,
  Settings,
  Wallet,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

// Each nav entry. `soon: true` marks routes whose backend doesn't exist yet
// (Insights/Chat/Settings) — they render as disabled with a "soon" pill so the
// shell matches PF-F3's AC without pretending to have features it can't serve.
type NavItem = {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  soon?: boolean;
};

const NAV: NavItem[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/transactions", label: "Transactions", icon: ArrowLeftRight },
  { to: "/investments", label: "Investments", icon: TrendingUp },
  { to: "/accounts", label: "Accounts", icon: Landmark },
  // No backend endpoints for these yet (see build brief). Shown but disabled.
  { to: "/insights", label: "Insights", icon: Lightbulb, soon: true },
  { to: "/chat", label: "Chat", icon: MessageSquare, soon: true },
  { to: "/settings", label: "Settings", icon: Settings, soon: true },
];

export function Sidebar() {
  return (
    <aside className="hidden md:flex w-60 shrink-0 flex-col border-r bg-card">
      <div className="flex h-16 items-center gap-2 border-b px-6">
        <Wallet className="h-5 w-5 text-primary" />
        <span className="font-semibold tracking-tight">Personal Finance</span>
      </div>

      <nav className="flex-1 space-y-1 p-3">
        {NAV.map((item) => {
          const Icon = item.icon;

          // "Coming soon" items are not links — render a muted, non-clickable row.
          if (item.soon) {
            return (
              <div
                key={item.to}
                className="flex items-center justify-between rounded-md px-3 py-2 text-sm text-muted-foreground/60 cursor-not-allowed"
                title="Backend not built yet"
              >
                <span className="flex items-center gap-3">
                  <Icon className="h-4 w-4" />
                  {item.label}
                </span>
                <Badge variant="muted" className="text-[10px] px-1.5 py-0">
                  soon
                </Badge>
              </div>
            );
          }

          return (
            // NavLink is React Router's <a> that knows whether it's the active
            // route — the className callback receives { isActive } so we can
            // highlight the current page.
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                )
              }
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
}
