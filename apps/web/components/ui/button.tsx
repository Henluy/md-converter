import { cva, type VariantProps } from 'class-variance-authority';
import { forwardRef, type ButtonHTMLAttributes } from 'react';

import { cn } from '@/lib/utils';

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap font-medium ' +
    'transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] ' +
    'focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--background)] ' +
    'disabled:pointer-events-none disabled:opacity-50 ' +
    'rounded-[var(--radius-md)]',
  {
    variants: {
      variant: {
        primary:
          'bg-[var(--accent)] text-[var(--accent-foreground)] hover:bg-[color-mix(in_oklch,var(--accent)_88%,transparent)]',
        secondary:
          'bg-[var(--muted)] text-[var(--foreground)] hover:bg-[color-mix(in_oklch,var(--muted)_92%,var(--foreground)_4%)]',
        ghost:
          'text-[var(--foreground)] hover:bg-[var(--muted)]',
        outline:
          'border border-[var(--border)] bg-transparent text-[var(--foreground)] hover:bg-[var(--muted)]',
        destructive:
          'bg-[var(--destructive)] text-[var(--destructive-foreground)] hover:opacity-90',
      },
      size: {
        sm: 'h-8 px-3 text-sm',
        md: 'h-10 px-4 text-sm',
        lg: 'h-11 px-5 text-base',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  ),
);
Button.displayName = 'Button';

export { buttonVariants };
