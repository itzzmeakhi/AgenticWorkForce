import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server proxies API calls to the FastAPI backend (uvicorn on :8000),
// so the React app can always just call same-origin paths like "/chat" --
// no VITE_API_BASE_URL / CORS juggling needed between dev and the built
// production bundle (which FastAPI serves directly, also same-origin).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/chat': 'http://localhost:8000', // also covers /chat/stream
      '/health': 'http://localhost:8000',
      '/admin': 'http://localhost:8000',
      '/voice': 'http://localhost:8000',
    },
  },
  build: {
    outDir: 'dist',
  },
})
