CREATE TABLE "files" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"job_id" uuid NOT NULL,
	"original_filename" text NOT NULL,
	"stored_filename" text NOT NULL,
	"original_format" text NOT NULL,
	"storage_path" text NOT NULL,
	"output_path" text,
	"converter_used" text,
	"size_bytes" bigint,
	"pages" integer,
	"created_at" timestamp with time zone DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "jobs" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"status" text DEFAULT 'pending' NOT NULL,
	"created_at" timestamp with time zone DEFAULT now(),
	"completed_at" timestamp with time zone,
	"error_message" text,
	"total_files" integer DEFAULT 0,
	"processed_files" integer DEFAULT 0,
	CONSTRAINT "jobs_status_valid" CHECK ("jobs"."status" in ('pending', 'processing', 'done', 'failed'))
);
--> statement-breakpoint
ALTER TABLE "files" ADD CONSTRAINT "files_job_id_jobs_id_fk" FOREIGN KEY ("job_id") REFERENCES "public"."jobs"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "files_job_id_idx" ON "files" USING btree ("job_id");--> statement-breakpoint
CREATE INDEX "jobs_status_idx" ON "jobs" USING btree ("status");--> statement-breakpoint
CREATE INDEX "jobs_created_at_idx" ON "jobs" USING btree ("created_at" DESC NULLS LAST);