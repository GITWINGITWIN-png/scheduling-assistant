import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
// Anuphan, the mockups' Thai font, bundled with the page so it works offline (no Google Fonts call)
import "@fontsource/anuphan/400.css";
import "@fontsource/anuphan/500.css";
import "@fontsource/anuphan/600.css";
import "./index.css";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
