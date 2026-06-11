'use client';

import { motion } from 'framer-motion';
import { Check, FileText, Loader2, AlertTriangle } from 'lucide-react';
import Link from 'next/link';

import { DeleteJobDialog } from '@/components/jobs/delete-job-dialog';
import { Badge } from '@/components/ui/badge';
import type { JobRead, JobStatus } from '@/lib/api-client';
import { formatBytes } from '@/lib/format';
import { JOB_STATUS_COPY } from '@/lib/quality';
import { cn } from '@/lib/utils';

function StatusIcon({ status }: { status: JobStatus }) {
  if (status === 'processing') {
    return <Loader2 className="h-3 w-3 animate-spin" aria-hidden />;
  }
  if (status === 'done') {
    return (
      <motion.span
        initial={{ scale: 0.6, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
      >
        <Check className="h-3 w-3" aria-hidden />
      </motion.span>
    );
  }
  if (status === 'failed' || status === 'partial_success') {
    return <AlertTriangle className="h-3 w-3" aria-hidden />;
  }
  return null;
}

function relativeTime(iso: string | null): string {
  if (!iso) return '';
  const ms = Date.now() - new Date(iso).getTime();
  if (ms < 60_000) return 'à l’instant';
  if (ms < 3_600_000) return `il y a ${Math.floor(ms / 60_000)} min`;
  if (ms < 86_400_000) return `il y a ${Math.floor(ms / 3_600_000)} h`;
  return new Date(iso).toLocaleDateString('fr-FR');
}

export interface JobCardProps {
  job: JobRead;
}

export function JobCard({ job }: JobCardProps) {
  const status = JOB_STATUS_COPY[job.status];
  const titleFile = job.files[0];
  const extra = Math.max(0, job.files.length - 1);
  const totalBytes = job.files.reduce((sum, f) => sum + (f.size_bytes ?? 0), 0);
  const totalPages = job.files.reduce((sum, f) => sum + (f.pages ?? 0), 0);
  const converters = Array.from(
    new Set(job.files.map((f) => f.converter_used).filter(Boolean)),
  );

  return (
    <motion.article
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
      whileHover={{ y: -1 }}
      className={cn(
        'group relative rounded-[var(--radius-md)] border border-[var(--border)]',
        'bg-[var(--card)] p-5 transition-shadow duration-150',
        'hover:border-[color-mix(in_oklch,var(--accent)_30%,var(--border))]',
        'hover:shadow-[0_1px_3px_color-mix(in_oklch,var(--accent)_18%,transparent)]',
      )}
    >
      <Link
        href={`/jobs/${job.id}`}
        className="absolute inset-0 z-0 rounded-[var(--radius-md)]"
        aria-label={`Voir le job ${titleFile?.original_filename ?? job.id}`}
      ><span className="sr-only">Voir</span></Link>
      {job.status === 'processing' && (
        <span
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 z-10 h-px overflow-hidden rounded-t-[var(--radius-md)]"
        >
          <span className="block h-full w-1/3 animate-pulse bg-[var(--accent)]/60" />
        </span>
      )}

      <header className="relative z-10 flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <span
            aria-hidden
            className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-[var(--radius-sm)] bg-[var(--muted)] text-[var(--muted-foreground)]"
          >
            <FileText className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <h3 className="truncate text-sm font-medium">
              {titleFile?.original_filename ?? 'Sans titre'}
              {extra > 0 && (
                <span className="ml-1 text-[var(--muted-foreground)]">+{extra}</span>
              )}
            </h3>
            <p className="font-mono mt-0.5 text-[11px] uppercase tracking-wider text-[var(--muted-foreground)]/80">
              {relativeTime(job.created_at)}
            </p>
          </div>
        </div>

        <div className="relative z-20 flex items-center gap-1.5">
          <Badge variant={status.variant} className="shrink-0">
            <StatusIcon status={job.status} />
            {status.label}
          </Badge>
          <DeleteJobDialog
            jobId={job.id}
            jobLabel={titleFile?.original_filename ?? job.id}
          />
        </div>
      </header>

      <dl className="relative z-10 mt-4 grid grid-cols-2 gap-x-6 gap-y-2 text-xs md:grid-cols-4">
        <Metric label="Fichiers" value={`${job.processed_files}/${job.total_files}`} />
        <Metric label="Taille" value={totalBytes > 0 ? formatBytes(totalBytes) : '—'} />
        <Metric label="Pages" value={totalPages > 0 ? String(totalPages) : '—'} />
        <Metric
          label="Convertisseur"
          value={converters.length > 0 ? converters.join(', ') : '—'}
          mono
        />
      </dl>

      {(job.status === 'failed' || job.status === 'partial_success') &&
        job.error_message && (
          <p className="relative z-10 mt-4 truncate rounded-[var(--radius-sm)] bg-[color-mix(in_oklch,var(--destructive)_10%,transparent)] px-3 py-2 text-xs text-[var(--destructive)]">
            {job.error_message}
          </p>
        )}
    </motion.article>
  );
}

function Metric({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-widest text-[var(--muted-foreground)]/70">
        {label}
      </dt>
      <dd className={cn('mt-0.5 truncate text-sm text-[var(--foreground)]', mono && 'font-mono')}>
        {value}
      </dd>
    </div>
  );
}
