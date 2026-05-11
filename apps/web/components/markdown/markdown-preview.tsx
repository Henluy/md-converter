'use client';

import 'highlight.js/styles/github.css';

import { Check, Copy, Download } from 'lucide-react';
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeHighlight from 'rehype-highlight';
import remarkGfm from 'remark-gfm';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export interface MarkdownPreviewProps {
  content: string;
  /** When present, renders a floating "Télécharger" CTA in the bottom-right. */
  downloadUrl?: string;
  className?: string;
}

export function MarkdownPreview({ content, downloadUrl, className }: MarkdownPreviewProps) {
  const [copied, setCopied] = useState(false);

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      toast.success('Markdown copié');
      setTimeout(() => setCopied(false), 1800);
    } catch {
      toast.error('Impossible de copier');
    }
  };

  return (
    <section className={cn('relative', className)}>
      <div className="absolute right-3 top-3 z-10">
        <Button
          variant="outline"
          size="sm"
          onClick={onCopy}
          aria-label="Copier le markdown"
        >
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? 'Copié' : 'Copier'}
        </Button>
      </div>

      <article
        className={cn(
          'prose-editorial rounded-[var(--radius-md)] border border-[var(--border)]',
          'bg-[var(--card)] p-8 md:p-12',
        )}
      >
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeHighlight]}
        >
          {content}
        </ReactMarkdown>
      </article>

      {downloadUrl && (
        <a
          href={downloadUrl}
          download
          className={cn(
            'fixed bottom-6 right-6 z-20 inline-flex items-center gap-2 rounded-full',
            'bg-[var(--accent)] px-5 py-3 text-sm font-medium text-[var(--accent-foreground)]',
            'shadow-[0_2px_12px_color-mix(in_oklch,var(--accent)_30%,transparent)]',
            'transition-transform hover:scale-[1.02] active:scale-[0.98]',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] focus-visible:ring-offset-2',
          )}
          aria-label="Télécharger le markdown"
        >
          <Download className="h-4 w-4" />
          Télécharger
        </a>
      )}
    </section>
  );
}
