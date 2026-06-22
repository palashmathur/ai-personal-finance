import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// Shared frame for every dashboard chart: a titled card with a fixed-height body.
// Keeps all four charts visually consistent and handles the empty state in one
// place so each chart component only worries about drawing its data.
export function ChartCard({
  title,
  isEmpty,
  emptyHint,
  children,
}: {
  title: string;
  isEmpty?: boolean;
  emptyHint?: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {isEmpty ? (
          <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
            {emptyHint ?? "No data for this range."}
          </div>
        ) : (
          <div className="h-64">{children}</div>
        )}
      </CardContent>
    </Card>
  );
}
