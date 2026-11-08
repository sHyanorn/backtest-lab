import react from '@vitejs/plugin-react'
import { searchForWorkspaceRoot } from 'vite'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  // GitHub Pages serves the site under /<repository>/.
  base: process.env.BASE_PATH ?? '/',
  plugins: [react()],
  server: {
    // The committed reports live outside web/.
    fs: { allow: [searchForWorkspaceRoot(process.cwd()), '../results'] },
    // The local API (D016); same origin, so no CORS round trip.
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  test: {
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
