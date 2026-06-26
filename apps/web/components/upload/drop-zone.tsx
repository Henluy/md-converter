'use client';

import { motion } from 'framer-motion';
import { BookOpen, FileText } from 'lucide-react';
import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';

import {
  ALLOWED_EXTENSIONS,
  EXPORT_INPUT_EXTENSIONS,
  MAX_FILE_SIZE_BYTES,
  MAX_FILES_PER_JOB,
  type TargetFormat,
} from '@/lib/api-client';
import { cn } from '@/lib/utils';

const IMPORT_ACCEPT: Record<string, string[]> = {
  'application/epub+zip': ['.epub'],
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/html': ['.html'],
  'text/plain': ['.txt'],
};

// Browsers often report .md with an empty/`text/plain` MIME, so react-dropzone
// falls back to extension matching here.
const EXPORT_ACCEPT: Record<string, string[]> = {
  'text/markdown': ['.md', '.markdown'],
};

interface DropConfig {
  accept: Record<string, string[]>;
  extensions: readonly string[];
  heading: string;
  blurb: string;
}

function dropConfig(target: TargetFormat): DropConfig {
  if (target === 'markdown') {
    return {
      accept: IMPORT_ACCEPT,
      extensions: ALLOWED_EXTENSIONS,
      heading: 'Glisse ton premier livre ici',
      blurb: 'EPUB, PDF, DOCX, HTML, TXT → Markdown',
    };
  }
  return {
    accept: EXPORT_ACCEPT,
    extensions: EXPORT_INPUT_EXTENSIONS,
    heading: 'Glisse ton fichier Markdown ici',
    blurb: `Markdown (.md) → ${target.toUpperCase()}`,
  };
}

export interface DropZoneProps {
  /** Called with the accepted files when the user drops or picks them. */
  onFilesSelected: (files: File[]) => void;
  /** Output format — flips the accepted input types and the copy. */
  target: TargetFormat;
  /** Disabled while a job is being submitted. */
  busy?: boolean;
}

export function DropZone({
  onFilesSelected,
  target,
  busy = false,
}: DropZoneProps) {
  const config = dropConfig(target);

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
    accept: config.accept,
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
          : config.heading}
      </h2>
      <p className="mt-3 max-w-md text-sm text-[var(--muted-foreground)]">
        {config.blurb} — jusqu’à {MAX_FILES_PER_JOB} fichiers,{' '}
        {Math.round(MAX_FILE_SIZE_BYTES / (1024 * 1024))} MB max chacun. Ou{' '}
        <span className="font-medium text-[var(--accent)] underline-offset-2 group-hover:underline">
          parcoure ta bibliothèque
        </span>
        .
      </p>
      <p className="font-mono mt-4 text-[10px] uppercase tracking-widest text-[var(--muted-foreground)]/70">
        {config.extensions.join('  ·  ')}
      </p>
    </motion.div>
  );
}
