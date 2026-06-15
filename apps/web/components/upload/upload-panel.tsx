'use client';

import { useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { toast } from 'sonner';

import { DropZone } from '@/components/upload/drop-zone';
import { StagedFiles } from '@/components/upload/staged-files';
import { useCreateJob } from '@/lib/hooks/use-create-job';

export function UploadPanel() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [staged, setStaged] = useState<File[]>([]);
  const createJob = useCreateJob({
    onSuccess: (job) => {
      toast.success('Conversion lancée', {
        description: 'Suivez la progression et consultez le résultat ici.',
      });
      setStaged([]);
      void queryClient.invalidateQueries({ queryKey: ['jobs'] });
      // Land on the job page so the user watches it convert and reads the
      // final markdown inline, instead of hunting for it in the list.
      router.push(`/jobs/${job.id}`);
    },
    onError: (error) => {
      toast.error('Échec de l’upload', {
        description: error.detail,
      });
    },
  });

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
    createJob.mutate(staged);
  };

  return (
    <div className="space-y-6">
      <DropZone onFilesSelected={onFilesSelected} busy={createJob.isPending} />
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
