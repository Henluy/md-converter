ALTER TABLE "jobs" DROP CONSTRAINT "jobs_status_valid";--> statement-breakpoint
ALTER TABLE "files" ADD COLUMN "status" text DEFAULT 'pending' NOT NULL;--> statement-breakpoint
ALTER TABLE "files" ADD COLUMN "error_message" text;--> statement-breakpoint
ALTER TABLE "files" ADD COLUMN "warnings" jsonb;--> statement-breakpoint
ALTER TABLE "files" ADD COLUMN "quality_score" real;--> statement-breakpoint
ALTER TABLE "files" ADD COLUMN "quality_level" text;--> statement-breakpoint
ALTER TABLE "files" ADD CONSTRAINT "files_status_valid" CHECK ("files"."status" in ('pending', 'processing', 'done', 'failed'));--> statement-breakpoint
ALTER TABLE "jobs" ADD CONSTRAINT "jobs_status_valid" CHECK ("jobs"."status" in ('pending', 'processing', 'done', 'failed', 'partial_success'));--> statement-breakpoint
-- Backfill: files that already produced output predate per-file status.
UPDATE "files" SET "status" = 'done' WHERE "output_path" IS NOT NULL;