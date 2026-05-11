'use client';

import { ArrowLeft, BookOpen, FileText, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useState } from 'react';

import { MarkdownPreview } from '@/components/markdown/markdown-preview';
import { ThemeToggle } from '@/components/theme-toggle';
import { Badge, type BadgeProps } from '@/components/ui/badge';
import type { FileRead, JobStatus } from '@/lib/api-client';
import { useFileContent } from '@/lib/hooks/use-file-content';
import { useJob } from '@/lib/hooks/use-job';
import { formatBytes } from '@/lib/format';
import { cn } from '@/lib/utils';

const STATUS_COPY: Record<JobStatus, { label: string; variant: BadgeProps['variant'] }> = {
  pending: { label: 'En attente', variant: 'outline' },
  processing: { label: 'Conversion…', variant: 'accent' },
  done: { label: 'Terminé', variant: 'success' },
  failed: { label: 'Échec', variant: 'destructive' },
};

export default function JobDetailPage() {
  const params = useParams<{ id: string }>();
  const jobId = params.id;
  const job = useJob(jobId);

  const doneFiles = (job.data?.files ?? []).filter((f) => f.output_path);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const activeId = selectedId ?? doneFiles[0]?.id ?? null;

  return (
    <main className="mx-auto flex min-h-dvh max-w-7xl flex-col px-6 py-8 md:px-10">
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
              Retour au tableau de bord
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
          Tous les jobs
        </Link>
      </div>

      {job.isError && (
        <ErrorState detail={job.error?.detail ?? 'Erreur inconnue'} />
      )}

      {!job.isError && job.isLoading && <LoadingState />}

      {job.data && (
        <div className="grid flex-1 grid-cols-1 gap-8 lg:grid-cols-[280px_1fr]">
          <aside className="space-y-4">
            <section className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--card)] p-5">
              <div className="mb-4 flex items-center justify-between">
                <span className="text-[10px] uppercase tracking-widest text-[var(--muted-foreground)]/70">
                  Statut
                </span>
                <Badge variant={STATUS_COPY[job.data.status].variant}>
                  {STATUS_COPY[job.data.status].label}
                </Badge>
              </div>
              <dl className="space-y-2 text-xs">
                <Row label="Fichiers" value={`${job.data.processed_files}/${job.data.total_files}`} />
                <Row
                  label="Créé"
                  value={
                    job.data.created_at
                      ? new Date(job.data.created_at).toLocaleString('fr-FR')
                      : '—'
                  }
                />
                <Row
                  label="Terminé"
                  value={
                    job.data.completed_at
                      ? new Date(job.data.completed_at).toLocaleString('fr-FR')
                      : '—'
                  }
                />
              </dl>
              {job.data.error_message && (
                <p className="mt-4 rounded-[var(--radius-sm)] bg-[color-mix(in_oklch,var(--destructive)_10%,transparent)] px-3 py-2 text-xs text-[var(--destructive)]">
                  {job.data.error_message}
                </p>
              )}
            </section>

            <FileList
              files={job.data.files}
              activeId={activeId}
              onSelect={setSelectedId}
            />
          </aside>

          <article>
            {activeId ? (
              <FilePreview fileId={activeId} />
            ) : (
              <PreviewEmpty status={job.data.status} />
            )}
          </article>
        </div>
      )}
    </main>
  );
}

function FilePreview({ fileId }: { fileId: string }) {
  const content = useFileContent(fileId);
  if (content.isLoading) return <PreviewSkeleton />;
  if (content.isError) {
    return (
      <ErrorState
        detail={content.error?.detail ?? 'Lecture du markdown impossible.'}
      />
    );
  }
  return <MarkdownPreview content={content.data ?? ''} />;
}

function FileList({
  files,
  activeId,
  onSelect,
}: {
  files: FileRead[];
  activeId: string | null;
  onSelect: (id: string) => void;
}) {
  if (files.length === 0) return null;
  return (
    <section>
      <h2 className="font-display mb-3 text-sm tracking-tight text-[var(--muted-foreground)]">
        Fichiers
      </h2>
      <ul className="space-y-1.5">
        {files.map((file) => {
          const isActive = file.id === activeId;
          const ready = !!file.output_path;
          return (
            <li key={file.id}>
              <button
                onClick={() => ready && onSelect(file.id)}
                disabled={!ready}
                className={cn(
                  'flex w-full items-center gap-2.5 rounded-[var(--radius-sm)] px-2.5 py-2 text-left text-xs transition-colors',
                  isActive && 'bg-[var(--muted)]',
                  ready
                    ? 'hover:bg-[var(--muted)]'
                    : 'cursor-not-allowed opacity-50',
                )}
              >
                <FileText className="h-3.5 w-3.5 shrink-0" aria-hidden />
                <span className="min-w-0 flex-1 truncate">
                  {file.original_filename}
                </span>
                {file.size_bytes && (
                  <span className="font-mono shrink-0 text-[10px] text-[var(--muted-foreground)]">
                    {formatBytes(file.size_bytes)}
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="shrink-0 text-[var(--muted-foreground)]">{label}</dt>
      <dd className="truncate text-right">{value}</dd>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="grid flex-1 place-items-center py-32 text-[var(--muted-foreground)]">
      <Loader2 className="h-6 w-6 animate-spin" />
      <p className="mt-3 text-xs">Chargement…</p>
    </div>
  );
}

function PreviewSkeleton() {
  return (
    <div className="space-y-3 rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--card)] p-8">
      {[...Array(8)].map((_, i) => (
        <div
          key={i}
          className="h-3 animate-pulse rounded-[var(--radius-sm)] bg-[var(--muted)]"
          style={{ width: `${60 + ((i * 13) % 35)}%` }}
        />
      ))}
    </div>
  );
}

function PreviewEmpty({ status }: { status: JobStatus }) {
  const copy =
    status === 'pending'
      ? 'En file d’attente.'
      : status === 'processing'
      ? 'Conversion en cours, la preview apparaîtra ici.'
      : status === 'failed'
      ? 'Aucun fichier n’a pu être converti.'
      : 'Pas de fichier à prévisualiser.';
  return (
    <div className="grid place-items-center rounded-[var(--radius-md)] border border-dashed border-[var(--border)] bg-[var(--card)] px-6 py-24 text-center">
      <Loader2
        className={cn('h-6 w-6 text-[var(--muted-foreground)]/60', status === 'processing' && 'animate-spin')}
      />
      <p className="font-display mt-4">{copy}</p>
    </div>
  );
}

function ErrorState({ detail }: { detail: string }) {
  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--destructive)] bg-[color-mix(in_oklch,var(--destructive)_5%,var(--card))] p-6">
      <h3 className="font-display text-lg text-[var(--destructive)]">
        Quelque chose s’est mal passé
      </h3>
      <p className="mt-2 text-sm text-[var(--muted-foreground)]">{detail}</p>
      <Link
        href="/"
        className="mt-4 inline-flex h-10 items-center justify-center rounded-[var(--radius-md)] bg-[var(--accent)] px-4 text-sm font-medium text-[var(--accent-foreground)] hover:opacity-90"
      >
        Retour
      </Link>
    </div>
  );
}
