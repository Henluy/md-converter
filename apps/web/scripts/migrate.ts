import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { drizzle } from 'drizzle-orm/postgres-js';
import { migrate } from 'drizzle-orm/postgres-js/migrator';
import postgres from 'postgres';

// Next.js auto-loads the repo-root .env for the app, but a standalone tsx
// script doesn't — load it here so `pnpm --filter @md/web db:migrate` works
// straight from a fresh checkout.
const rootEnv = resolve(dirname(fileURLToPath(import.meta.url)), '../../../.env');
if (!process.env['DATABASE_URL'] && existsSync(rootEnv)) {
  process.loadEnvFile(rootEnv);
}

const databaseUrl = process.env['DATABASE_URL'];

if (!databaseUrl) {
  throw new Error(
    'DATABASE_URL is not set. Copy .env.example to .env at the repo root.',
  );
}

async function run(): Promise<void> {
  const client = postgres(databaseUrl!, { max: 1, prepare: false });
  const db = drizzle(client);

  console.log('Applying Drizzle migrations…');
  await migrate(db, { migrationsFolder: './drizzle/migrations' });
  console.log('✔ Migrations applied.');

  await client.end();
}

run().catch((error: unknown) => {
  console.error('Migration failed:', error);
  process.exit(1);
});
