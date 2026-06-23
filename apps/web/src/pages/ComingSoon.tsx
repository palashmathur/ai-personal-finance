import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// Placeholder for routes whose backend endpoints don't exist yet (Insights,
// Chat, Settings). Per the build brief we don't fake features that have no API —
// we show an honest "not built" note pointing at the backend ticket instead.
export function ComingSoon({
  title,
  backendTicket,
}: {
  title: string;
  backendTicket: string;
}) {
  return (
    <div className="mx-auto max-w-lg">
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>
            This screen isn't built yet — its backend endpoints don't exist in
            the current API.
          </p>
          <p>
            Tracked by backend ticket{" "}
            <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
              {backendTicket}
            </code>
            . The UI will be added once that ships.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
