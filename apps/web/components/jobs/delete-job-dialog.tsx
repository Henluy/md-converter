'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Trash2 } from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { toast } from 'sonner';

import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { api, type ApiError } from '@/lib/api-client';

export interface DeleteJobDialogProps {
  jobId: string;
  jobLabel: string;
  /** Override the trigger — defaults to a ghost icon button. */
  trigger?: ReactNode;
  /** Called once the deletion has succeeded (after invalidation). */
  onDeleted?: () => void;
}

export function DeleteJobDialog({
  jobId,
  jobLabel,
  trigger,
  onDeleted,
}: DeleteJobDialogProps) {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();

  const mutation = useMutation<void, ApiError, void>({
    mutationFn: () => api.deleteJob(jobId),
    onSuccess: async () => {
      toast.success('Job supprimé');
      setOpen(false);
      await queryClient.invalidateQueries({ queryKey: ['jobs'] });
      await queryClient.invalidateQueries({ queryKey: ['job', jobId] });
      onDeleted?.();
    },
    onError: (error) => {
      toast.error('Suppression impossible', { description: error.detail });
    },
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button
            variant="ghost"
            size="icon"
            aria-label={`Supprimer ${jobLabel}`}
            className="text-[var(--muted-foreground)] hover:text-[var(--destructive)]"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        )}
      </DialogTrigger>
      <DialogContent>
        <div className="space-y-2">
          <DialogTitle>Supprimer le job ?</DialogTitle>
          <DialogDescription>
            Le job <span className="font-medium text-[var(--foreground)]">{jobLabel}</span> et
            tous ses fichiers générés seront effacés. Cette action ne peut pas
            être annulée.
          </DialogDescription>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <DialogClose asChild>
            <Button variant="ghost" size="md">
              Annuler
            </Button>
          </DialogClose>
          <Button
            variant="destructive"
            size="md"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {mutation.isPending ? 'Suppression…' : 'Supprimer'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
