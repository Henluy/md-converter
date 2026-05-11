'use client';

import { AnimatePresence, motion } from 'framer-motion';
import { FileText, Loader2, X } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { fileExtension, formatBytes } from '@/lib/format';

export interface StagedFilesProps {
  files: File[];
  /** Called with the file's index inside the array. */
  onRemove?: (index: number) => void;
  onSubmit?: () => void;
  onClear?: () => void;
  busy?: boolean;
}

export function StagedFiles({
  files,
  onRemove,
  onSubmit,
  onClear,
  busy = false,
}: StagedFilesProps) {
  if (files.length === 0) return null;

  const total = files.reduce((sum, f) => sum + f.size, 0);

  return (
    <section className="rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--card)] p-5">
      <header className="flex items-baseline justify-between">
        <div>
          <h3 className="font-display text-lg">
            {files.length} fichier{files.length > 1 ? 's' : ''} en attente
          </h3>
          <p className="text-xs text-[var(--muted-foreground)]">
            {formatBytes(total)} au total
          </p>
        </div>
        {!busy && onClear && (
          <Button variant="ghost" size="sm" onClick={onClear}>
            Tout retirer
          </Button>
        )}
      </header>

      <ul className="mt-4 divide-y divide-[var(--border)]">
        <AnimatePresence initial={false}>
          {files.map((file, idx) => (
            <motion.li
              key={`${file.name}-${idx}`}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, x: -8, transition: { duration: 0.12 } }}
              transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1], delay: idx * 0.02 }}
              className="flex items-center gap-3 py-2.5"
            >
              <span
                aria-hidden
                className="grid h-8 w-8 place-items-center rounded-[var(--radius-sm)] bg-[var(--muted)] text-[var(--muted-foreground)]"
              >
                <FileText className="h-4 w-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm">{file.name}</p>
                <p className="text-xs text-[var(--muted-foreground)]">
                  <span className="font-mono">{fileExtension(file.name) || '?'}</span>
                  {' · '}
                  {formatBytes(file.size)}
                </p>
              </div>
              {onRemove && !busy && (
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Retirer ${file.name}`}
                  onClick={() => onRemove(idx)}
                  className="h-8 w-8"
                >
                  <X className="h-4 w-4" />
                </Button>
              )}
            </motion.li>
          ))}
        </AnimatePresence>
      </ul>

      <footer className="mt-5 flex flex-wrap items-center justify-end gap-3">
        <Button
          size="lg"
          onClick={onSubmit}
          disabled={busy || files.length === 0}
        >
          {busy ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Conversion en cours…
            </>
          ) : (
            <>Lancer la conversion</>
          )}
        </Button>
      </footer>
    </section>
  );
}
