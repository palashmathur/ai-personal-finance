import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import "./index.css";

// Entry point — the React equivalent of `public static void main`. It finds the
// <div id="root"> in index.html and tells React to render <App> into it.
// StrictMode is a dev-only wrapper that surfaces unsafe patterns (it double-
// invokes some functions in dev to flush out side effects); it's a no-op in prod.
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
