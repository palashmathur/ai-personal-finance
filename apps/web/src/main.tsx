import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { queryClient } from "@/lib/queryClient";
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import "./index.css";

// Provider stack (outer to inner):
//   QueryClientProvider  -> makes the TanStack Query cache available app-wide
//   ThemeProvider        -> dark/light/system mode via a class on <html>
//   BrowserRouter        -> client-side routing (history API)
// These are React's version of app-wide singletons/filters wrapping the request
// pipeline — every component below can read query cache, theme, and route.
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider defaultTheme="system" storageKey="pf-theme">
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
