import { Routes, Route, Navigate } from "react-router-dom";

import { AppShell } from "@/components/shell/AppShell";
import { Dashboard } from "@/pages/Dashboard";
import { Transactions } from "@/pages/Transactions";
import { Investments } from "@/pages/Investments";
import { Accounts } from "@/pages/Accounts";
import { ComingSoon } from "@/pages/ComingSoon";

// Route table. The parent route renders <AppShell/> (sidebar + filters + Outlet);
// each child route renders into the Outlet. Routes whose backend isn't built yet
// point at <ComingSoon/> with the tracking ticket. Unknown paths bounce to "/".
function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/transactions" element={<Transactions />} />
        <Route path="/investments" element={<Investments />} />
        <Route path="/accounts" element={<Accounts />} />
        <Route
          path="/insights"
          element={<ComingSoon title="Insights" backendTicket="PF-24 / PF-33" />}
        />
        <Route
          path="/chat"
          element={<ComingSoon title="Chat" backendTicket="PF-36" />}
        />
        <Route
          path="/settings"
          element={<ComingSoon title="Settings" backendTicket="PF-29" />}
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
