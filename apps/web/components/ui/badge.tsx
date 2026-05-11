import { cva, type VariantProps } from 'class-variance-authority';
import type { HTMLAttributes } from 'react';

import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium tracking-tight',
  {
    variants: {
      variant: {
        neutral:
          'bg-[var(--muted)] text-[var(--muted-foreground)]',
        accent:
          'bg-[color-mix(in_oklch,var(--accent)_15%,transparent)] text-[var(--accent)]',
        success:
          'bg-[color-mix(in_oklch,var(--success)_15%,transparent)] text-[var(--success)]',
        destructive:
          'bg-[color-mix(in_oklch,var(--destructive)_15%,transparent)] text-[var(--destructive)]',
        outline:
          'border border-[var(--border)] text-[var(--muted-foreground)]',
      },
    },
    defaultVariants: { variant: 'neutral' },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
