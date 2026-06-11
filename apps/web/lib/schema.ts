import { sql } from 'drizzle-orm';
import {
  bigint,
  check,
  index,
  integer,
  jsonb,
  pgTable,
  real,
  text,
  timestamp,
  uuid,
} from 'drizzle-orm/pg-core';

export const JOB_STATUSES = [
  'pending',
  'processing',
  'done',
  'failed',
  'partial_success',
] as const;
export type JobStatus = (typeof JOB_STATUSES)[number];

export const FILE_STATUSES = [
  'pending',
  'processing',
  'done',
  'failed',
] as const;
export type FileStatus = (typeof FILE_STATUSES)[number];

export const QUALITY_LEVELS = ['high', 'medium', 'low'] as const;
export type QualityLevel = (typeof QUALITY_LEVELS)[number];

export const jobs = pgTable(
  'jobs',
  {
    id: uuid().primaryKey().defaultRandom(),
    status: text().notNull().default('pending').$type<JobStatus>(),
    createdAt: timestamp({ withTimezone: true }).defaultNow(),
    completedAt: timestamp({ withTimezone: true }),
    errorMessage: text(),
    totalFiles: integer().default(0),
    processedFiles: integer().default(0),
  },
  (table) => [
    check(
      'jobs_status_valid',
      sql`${table.status} in ('pending', 'processing', 'done', 'failed', 'partial_success')`,
    ),
    index('jobs_status_idx').on(table.status),
    index('jobs_created_at_idx').on(table.createdAt.desc()),
  ],
);

export const files = pgTable(
  'files',
  {
    id: uuid().primaryKey().defaultRandom(),
    jobId: uuid()
      .notNull()
      .references(() => jobs.id, { onDelete: 'cascade' }),
    originalFilename: text().notNull(),
    storedFilename: text().notNull(),
    originalFormat: text().notNull(),
    storagePath: text().notNull(),
    outputPath: text(),
    converterUsed: text(),
    sizeBytes: bigint({ mode: 'number' }),
    pages: integer(),
    // Per-file lifecycle + failure reason (enables partial-success jobs).
    status: text().notNull().default('pending').$type<FileStatus>(),
    errorMessage: text(),
    // Conversion-quality signals surfaced to the user.
    warnings: jsonb().$type<string[]>(),
    qualityScore: real(),
    qualityLevel: text().$type<QualityLevel>(),
    createdAt: timestamp({ withTimezone: true }).defaultNow(),
  },
  (table) => [
    check(
      'files_status_valid',
      sql`${table.status} in ('pending', 'processing', 'done', 'failed')`,
    ),
    index('files_job_id_idx').on(table.jobId),
  ],
);

export type Job = typeof jobs.$inferSelect;
export type NewJob = typeof jobs.$inferInsert;
export type FileRow = typeof files.$inferSelect;
export type NewFileRow = typeof files.$inferInsert;
