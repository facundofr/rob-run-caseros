import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // Cada prueba levanta un PostgreSQL embebido (PGlite); la primera inicialización es lenta.
    testTimeout: 30_000,
    hookTimeout: 30_000,
  },
});
