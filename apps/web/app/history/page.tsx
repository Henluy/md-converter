'use client';

import { useInfiniteQuery } from '@tanstack/react-query';
import { ArrowLeft, BookOpen, Inbox, Loader2 } from 'lucide-react';
import Link from 'next/link';

import { JobCard } from '@/components/jobs/job-card';
import { ThemeToggle } from '@/components/theme-toggle';
import { Button } from '@/components/ui/button';
import { api, type ApiError, type JobRead } from '@/lib/api-client';

const PAGE_SIZE = 20;

export default function HistoryPage() {
  const query = useInfiniteQuery<
    JobRead[],
    ApiError,
    { pages: JobRead[][]; pageParams: number[] },
    [string],
    number
  >({
    queryKey: ['history'],
    queryFn: ({ pageParam }) =>
      api.listJobs({ limit: PAGE_SIZE, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) =>
      lastPage.length < PAGE_SIZE ? undefined : allPages.length * PAGE_SIZE,
  });

  const allJobs = query.data?.pages.flat() ?? [];

  return (
    <main className="mx-auto flex min-h-dvh max-w-5xl flex-col px-6 py-8 md:px-10">
      <header className="flex items-center justify-between border-b border-[var(--border)] pb-6">
        <Link
          href="/"
          className="flex items-center gap-3 transition-opacity hover:opacity-80"
        >
          <span
            aria-hidden
            className="grid h-9 w-9 place-items-center rounded-[var(--radius-md)] bg-[var(--accent)] text-[var(--accent-foreground)]"
          >
            <BookOpen className="h-5 w-5" />
          </span>
          <div>
            <p className="font-display text-lg leading-none">md-converter</p>
            <p className="text-xs text-[var(--muted-foreground)]">
              Tableau de bord
            </p>
          </div>
        </Link>
        <ThemeToggle />
      </header>

      <div className="mt-6 mb-4">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
        >
          <ArrowLeft className="h-3 w-3" />
          Retour au dashboard
        </Link>
      </div>

      <section aria-labelledby="history-heading" className="py-2">
        <div className="mb-6 flex items-baseline justify-between">
          <h1 id="history-heading" className="font-display text-3xl tracking-tight">
            Historique
          </h1>
          <span className="font-mono text-xs uppercase tracking-widest text-[var(--muted-foreground)]/70">
            {allJobs.length} chargé{allJobs.length > 1 ? 's' : ''}
          </span>
        </div>

        {query.isError && (
          <p className="rounded-[var(--radius-md)] border border-[var(--destructive)] bg-[color-mix(in_oklch,var(--destructive)_5%,var(--card))] p-4 text-sm text-[var(--destructive)]">
            {query.error?.detail ?? 'Erreur inconnue'}
          </p>
        )}

        {query.isLoading && <Skeletons />}

        {!query.isLoading && allJobs.length === 0 && (
          <div className="grid place-items-center rounded-[var(--radius-md)] border border-dashed border-[var(--border)] bg-[var(--card)] px-6 py-16 text-center">
            <Inbox className="h-8 w-8 text-[var(--muted-foreground)]/60" />
            <p className="font-display mt-3 text-base">
              Aucun job dans l’historique
            </p>
            <p className="mt-1 max-w-xs text-xs text-[var(--muted-foreground)]">
              Glisse un livre sur le tableau de bord pour démarrer ta première
              conversion.
            </p>
          </div>
        )}

        {allJobs.length > 0 && (
          <ul className="space-y-3">
            {allJobs.map((job) => (
              <li key={job.id}>
                <JobCard job={job} />
              </li>
            ))}
          </ul>
        )}

        {query.hasNextPage && (
          <div className="mt-8 flex justify-center">
            <Button
              variant="outline"
              size="md"
              onClick={() => void query.fetchNextPage()}
              disabled={query.isFetchingNextPage}
            >
              {query.isFetchingNextPage ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Chargement…
                </>
              ) : (
                'Charger plus'
              )}
            </Button>
          </div>
        )}
      </section>
    </main>
  );
}

function Skeletons() {
  return (
    <ul className="space-y-3" aria-hidden>
      {Array.from({ length: 5 }).map((_, i) => (
        <li
          key={i}
          className="h-[120px] animate-pulse rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--card)]"
        />
      ))}
    </ul>
  );
}
