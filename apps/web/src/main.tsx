import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { NavProvider } from "./nav";
import { SessionProvider } from "./session";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <NavProvider>
      <SessionProvider>
        <App />
      </SessionProvider>
    </NavProvider>
  </StrictMode>,
);
