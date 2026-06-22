import { useEffect, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api, getApiError } from "@/lib/http";

// PF-F1/PF-F2 placeholder. Beyond proving the toolchain renders, it now makes a
// real smoke call to GET /health through the generated client + http wrapper, so
// we can see end-to-end (browser -> Vite -> CORS -> FastAPI) actually working.
// PF-F3 replaces this with the real AppShell (sidebar + routing + global filters).
function App() {
  const [health, setHealth] = useState<string>("checking…");

  // useEffect with an empty dependency array runs once after the first render —
  // the React equivalent of an init/@PostConstruct hook. We fire the health call
  // here and stash the result in component state.
  useEffect(() => {
    api
      .health()
      .then((res) => setHealth(JSON.stringify(res)))
      .catch((err) => setHealth(`error: ${getApiError(err).detail}`));
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>AI Personal Finance</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Frontend scaffold is live. Vite + React 18 + TypeScript + Tailwind +
            shadcn/ui are wired up, and the typed API client is generated. The
            real app shell lands in PF-F3.
          </p>
          <p className="text-sm">
            API base:{" "}
            <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
              {import.meta.env.VITE_API_URL}
            </code>
          </p>
          <p className="text-sm">
            <span className="text-muted-foreground">/health says:</span>{" "}
            <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
              {health}
            </code>
          </p>
          <Button>It works</Button>
        </CardContent>
      </Card>
    </div>
  );
}

export default App;
