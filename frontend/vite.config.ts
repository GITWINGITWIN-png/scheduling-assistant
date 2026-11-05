// The web page's build tool. `npm run dev` serves it on :5173 with hot reload and forwards
// /api to the secretary on :8000. `npm run build` writes dist/, which the backend then serves.
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { "/api": "http://localhost:8000" } },
});
