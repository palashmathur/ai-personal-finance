import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

// PF-F1 placeholder. This proves the toolchain end-to-end: Vite serves it,
// Tailwind classes apply, and the shadcn Card/Button render. PF-F3 replaces
// this with the real AppShell (sidebar + routing + global filters).
function App() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>AI Personal Finance</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Frontend scaffold is live. Vite + React 18 + TypeScript + Tailwind +
            shadcn/ui are wired up. The real app shell lands in PF-F3.
          </p>
          <p className="text-sm">
            API base:{" "}
            <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
              {import.meta.env.VITE_API_URL}
            </code>
          </p>
          <Button>It works</Button>
        </CardContent>
      </Card>
    </div>
  );
}

export default App;
