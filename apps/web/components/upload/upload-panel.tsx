'use client';

import { useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { toast } from 'sonner';

import { DropZone } from '@/components/upload/drop-zone';
import { StagedFiles } from '@/components/upload/staged-files';
import { TARGET_FORMATS, type TargetFormat } from '@/lib/api-client';
import { useCreateJob } from '@/lib/hooks/use-create-job';
import { cn } from '@/lib/utils';

const TARGET_LABELS: Record<TargetFormat, string> = {
  markdown: 'Markdown',
  pdf: 'PDF',
  docx: 'DOCX',
  epub: 'EPUB',
};

export function UploadPanel() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [staged, setStaged] = useState<File[]>([]);
  const [target, setTarget] = useState<TargetFormat>('markdown');
  const createJob = useCreateJob({
    onSuccess: (job) => {
      toast.success('Conversion lancée', {
        description: 'Suivez la progression et consultez le résultat ici.',
      });
      setStaged([]);
      void queryClient.invalidateQueries({ queryKey: ['jobs'] });
      // Land on the job page so the user watches it convert and reads the
      // final result inline, instead of hunting for it in the list.
      router.push(`/jobs/${job.id}`);
    },
    onError: (error) => {
      toast.error('Échec de l’upload', {
        description: error.detail,
      });
    },
  });

  const onTargetChange = (next: TargetFormat) => {
    if (next === target) return;
    // Switching direction changes which inputs are accepted, so drop any
    // files staged for the previous target to avoid silent rejections.
    setTarget(next);
    setStaged([]);
  };

  const onFilesSelected = (files: File[]) => {
    setStaged((current) => {
      const seen = new Set(current.map((f) => `${f.name}|${f.size}`));
      const merged = [...current];
      for (const file of files) {
        const key = `${file.name}|${file.size}`;
        if (!seen.has(key)) {
          merged.push(file);
          seen.add(key);
        }
      }
      return merged;
    });
  };

  const onRemove = (index: number) => {
    setStaged((current) => current.filter((_, i) => i !== index));
  };

  const onSubmit = () => {
    if (staged.length === 0) return;
    createJob.mutate({ files: staged, targetFormat: target });
  };

  return (
    <div className="space-y-6">
      <fieldset
        className="flex flex-wrap items-center gap-3"
        disabled={createJob.isPending}
      >
        <legend className="sr-only">Format de sortie</legend>
        <span className="text-[10px] uppercase tracking-widest text-[var(--muted-foreground)]/70">
          Convertir vers
        </span>
        <div
          role="radiogroup"
          aria-label="Format de sortie"
          className="inline-flex rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--card)] p-1"
        >
          {TARGET_FORMATS.map((fmt) => {
            const active = fmt === target;
            return (
              <button
                key={fmt}
                type="button"
                role="radio"
                aria-checked={active}
                onClick={() => onTargetChange(fmt)}
                className={cn(
                  'rounded-[var(--radius-sm)] px-3 py-1.5 text-xs font-medium transition-colors',
                  active
                    ? 'bg-[var(--accent)] text-[var(--accent-foreground)]'
                    : 'text-[var(--muted-foreground)] hover:bg-[var(--muted)]',
                )}
              >
                {TARGET_LABELS[fmt]}
              </button>
            );
          })}
        </div>
      </fieldset>

      <DropZone
        onFilesSelected={onFilesSelected}
        target={target}
        busy={createJob.isPending}
      />
      <StagedFiles
        files={staged}
        onRemove={onRemove}
        onClear={() => setStaged([])}
        onSubmit={onSubmit}
        busy={createJob.isPending}
      />
    </div>
  );
}
