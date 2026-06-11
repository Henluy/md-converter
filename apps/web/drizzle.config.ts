import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { defineConfig } from 'drizzle-kit';

// Load the repo-root .env so drizzle-kit (generate/check/studio) sees
// DATABASE_URL without it being exported in the shell.
const rootEnv = resolve(dirname(fileURLToPath(import.meta.url)), '../../.env');
if (!process.env['DATABASE_URL'] && existsSync(rootEnv)) {
  process.loadEnvFile(rootEnv);
}

const databaseUrl = process.env['DATABASE_URL'];

if (!databaseUrl) {
  throw new Error(
    'DATABASE_URL is not set. Copy .env.example to .env at the repo root.',
  );
}

export default defineConfig({
  schema: './lib/schema.ts',
  out: './drizzle/migrations',
  dialect: 'postgresql',
  dbCredentials: { url: databaseUrl },
  strict: true,
  verbose: true,
  casing: 'snake_case',
});
