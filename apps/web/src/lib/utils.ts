import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

// `cn` is the shadcn helper used on every component. clsx joins conditional
// class names; twMerge then dedupes conflicting Tailwind utilities so the last
// one wins (e.g. cn("p-2", isBig && "p-4") -> "p-4", not "p-2 p-4"). It's the
// className equivalent of building a string with a tiny builder that also
// resolves conflicts.
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
