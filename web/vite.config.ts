import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Relative base so the built SPA works regardless of where it's mounted —
  // Docker at `/`, a GitHub Pages project site at `/<repo>/`, a CDN behind
  // a subpath proxy, etc. The `zarrcade-build` CLI may override this via
  // the ZARRCADE_BASE env var when an absolute base is required (e.g. an
  // SPA that ever needs absolute asset URLs); otherwise this default is
  // intentional and should be left alone.
  base: './',
  server: {
    host: '0.0.0.0',
  },
})
