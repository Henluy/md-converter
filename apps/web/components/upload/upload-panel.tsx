'use client';

import { useState } from 'react';
import { toast } from 'sonner';

import { DropZone } from '@/components/upload/drop-zone';
import { StagedFiles } from '@/components/upload/staged-files';
import { useCreateJob } from '@/lib/hooks/use-create-job';

export function UploadPanel() {
  const [staged, setStaged] = useState<File[]>([]);
  const createJob = useCreateJob({
    onSuccess: (job) => {
      toast.success('Job créé', {
        description: `${job.total_files} fichier${job.total_files > 1 ? 's' : ''} en file d’attente.`,
      });
      setStaged([]);
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
