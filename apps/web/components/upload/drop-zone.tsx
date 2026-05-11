'use client';

import { motion } from 'framer-motion';
import { BookOpen, FileText } from 'lucide-react';
import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';

import {
  ALLOWED_EXTENSIONS,
  MAX_FILE_SIZE_BYTES,
  MAX_FILES_PER_JOB,
} from '@/lib/api-client';
import { cn } from '@/lib/utils';

const ACCEPT: Record<string, string[]> = {
  'application/epub+zip': ['.epub'],
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/html': ['.html'],
  'text/plain': ['.txt'],
};

export interface DropZoneProps {
  /** Called with the accepted files when the user drops or picks them. */
  onFilesSelected: (files: File[]) => void;
  /** Disabled while a job is being submitted. */
  busy?: boolean;
}

export function DropZone({ onFilesSelected, busy = false }: DropZoneProps) {
  const onDrop = useCallback(
    (accepted: File[]) => {
      if (accepted.length === 0) return;
      onFilesSelected(accepted);
    },
    [onFilesSelected],
  );

  const {
    getRootProps,
    getInputProps,
    isDragActive,
    isDragAccept,
    isDragReject,
    open,
  } = useDropzone({
    onDrop,
    accept: ACCEPT,
    maxFiles: MAX_FILES_PER_JOB,
    maxSize: MAX_FILE_SIZE_BYTES,
    multiple: true,
    noClick: true, // we drive click ourselves via the inner button
    disabled: busy,
  });

  return (
    <motion.div
      {...getRootProps({
        onClick: open,
        role: 'button',
        tabIndex: 0,
        'aria-label': 'Glisser des fichiers à convertir',
      })}
      animate={{
        scale: isDragActive ? 1.005 : 1,
        borderColor: isDragAccept
          ? 'color-mix(in oklch, var(--accent) 70%, var(--border))'
          : isDragReject
          ? 'var(--destructive)'
          : 'var(--border)',
      }}
      transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
      className={cn(
        'group relative grid w-full cursor-pointer place-items-center',
        'rounded-[var(--radius-lg)] border-2 border-dashed bg-[var(--card)]',
        'px-6 py-16 text-center transition-colors',
        'hover:bg-[color-mix(in_oklch,var(--accent)_4%,var(--card))]',
        isDragActive && 'bg-[color-mix(in_oklch,var(--accent)_8%,var(--card))]',
        busy && 'pointer-events-none opacity-60',
      )}
    >
      <input {...getInputProps()} aria-hidden />

      <motion.span
        aria-hidden
        animate={{ y: isDragActive ? -4 : 0 }}
        transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
        className={cn(
          'grid h-16 w-16 place-items-center rounded-full',
          'bg-[color-mix(in_oklch,var(--accent)_12%,transparent)]',
          'text-[var(--accent)]',
        )}
      >
        {isDragActive ? (
          <FileText className="h-7 w-7" />
        ) : (
          <BookOpen className="h-7 w-7" />
        )}
      </motion.span>

      <h2 className="font-display mt-6 text-2xl tracking-tight">
        {isDragReject
          ? 'Format non supporté'
          : isDragActive
          ? 'Relâche pour commencer'
          : 'Glisse ton premier livre ici'}
      </h2>
      <p className="mt-3 max-w-md text-sm text-[var(--muted-foreground)]">
        EPUB, PDF, DOCX, HTML, TXT — jusqu’à {MAX_FILES_PER_JOB} fichiers,{' '}
        {Math.round(MAX_FILE_SIZE_BYTES / (1024 * 1024))} MB max chacun. Ou{' '}
        <span className="font-medium text-[var(--accent)] underline-offset-2 group-hover:underline">
          parcoure ta bibliothèque
        </span>
        .
      </p>
      <p className="font-mono mt-4 text-[10px] uppercase tracking-widest text-[var(--muted-foreground)]/70">
        {ALLOWED_EXTENSIONS.join('  ·  ')}
      </p>
    </motion.div>
  );
}
