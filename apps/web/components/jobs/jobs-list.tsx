'use client';

import { AnimatePresence } from 'framer-motion';
import { Inbox } from 'lucide-react';

import { JobCard } from '@/components/jobs/job-card';
import { useJobs } from '@/lib/hooks/use-jobs';

export function JobsList() {
  const { data: jobs, isLoading, isError, error } = useJobs(10);

  return (
    <section aria-labelledby="jobs-heading">
      <div className="mb-4 flex items-baseline justify-between">
        <h2 id="jobs-heading" className="font-display text-xl">
          Conversions récentes
        </h2>
        <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--muted-foreground)]/70">
          {jobs?.length ?? 0}/10
        </span>
      </div>

      {isError && (
        <Empty
          title="Impossible de joindre l’API"
          body={error?.detail ?? 'Le backend ne répond pas.'}
        />
      )}

      {!isError && isLoading && <SkeletonList />}

      {!isError && !isLoading && (jobs?.length ?? 0) === 0 && (
        <Empty
          title="Aucune conversion pour le moment"
          body="Glisse un livre dans la zone d’upload pour commencer."
        />
      )}

      {!isError && jobs && jobs.length > 0 && (
        <ul className="space-y-3">
          <AnimatePresence initial={false}>
            {jobs.map((job) => (
              <li key={job.id}>
                <JobCard job={job} />
              </li>
            ))}
          </AnimatePresence>
        </ul>
      )}
    </section>
  );
}

function SkeletonList() {
  return (
    <ul className="space-y-3" aria-hidden>
      {[0, 1, 2].map((i) => (
        <li
          key={i}
          className="h-[120px] animate-pulse rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--card)]"
        />
      ))}
    </ul>
  );
}

function Empty({ title, body }: { title: string; body: string }) {
  return (
    <div className="grid place-items-center rounded-[var(--radius-md)] border border-dashed border-[var(--border)] bg-[var(--card)] px-6 py-12 text-center">
      <Inbox
        aria-hidden
        className="h-8 w-8 text-[var(--muted-foreground)]/60"
      />
      <p className="font-display mt-3 text-base">{title}</p>
      <p className="mt-1 max-w-xs text-xs text-[var(--muted-foreground)]">{body}</p>
    </div>
  );
}
