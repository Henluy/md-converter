import { drizzle } from 'drizzle-orm/postgres-js';
import postgres from 'postgres';

import * as schema from './schema';

const databaseUrl = process.env['DATABASE_URL'];

if (!databaseUrl) {
  throw new Error(
    'DATABASE_URL is not set. Copy .env.example to .env at the repo root.',
  );
}

const isProd = process.env['NODE_ENV'] === 'production';

const queryClient = postgres(databaseUrl, {
  max: isProd ? 10 : 5,
  idle_timeout: 20,
  connect_timeout: 10,
  prepare: false,
});

export const db = drizzle(queryClient, { schema, casing: 'snake_case' });
export { schema };
export type Database = typeof db;
