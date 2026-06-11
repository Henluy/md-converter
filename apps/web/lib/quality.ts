import type { BadgeProps } from '@/components/ui/badge';
import type { JobStatus, QualityLevel } from '@/lib/api-client';

/** How each job status renders (label + badge colour). */
export const JOB_STATUS_COPY: Record<
  JobStatus,
  { label: string; variant: BadgeProps['variant'] }
> = {
  pending: { label: 'En attente', variant: 'outline' },
  processing: { label: 'Conversion…', variant: 'accent' },
  done: { label: 'Terminé', variant: 'success' },
  failed: { label: 'Échec', variant: 'destructive' },
  partial_success: { label: 'Partiel', variant: 'accent' },
};

/** Confidence band → label + badge colour. */
export const QUALITY_COPY: Record<
  QualityLevel,
  { label: string; variant: BadgeProps['variant'] }
> = {
  high: { label: 'Confiance élevée', variant: 'success' },
  medium: { label: 'Confiance moyenne', variant: 'accent' },
  low: { label: 'Confiance faible', variant: 'destructive' },
};
