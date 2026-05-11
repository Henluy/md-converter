import { BookOpen, FileText, Sparkles } from 'lucide-react';

import { ThemeToggle } from '@/components/theme-toggle';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-5xl flex-col px-6 py-8 md:px-10">
      <header className="flex items-center justify-between border-b border-[var(--border)] pb-6">
        <div className="flex items-center gap-3">
          <span
            aria-hidden
            className="grid h-9 w-9 place-items-center rounded-[var(--radius-md)] bg-[var(--accent)] text-[var(--accent-foreground)]"
          >
            <BookOpen className="h-5 w-5" />
          </span>
          <div>
            <p className="font-display text-lg leading-none">md-converter</p>
            <p className="text-xs text-[var(--muted-foreground)]">
              EPUB & PDF → Markdown
            </p>
          </div>
        </div>
        <ThemeToggle />
      </header>

      <section className="flex flex-1 flex-col justify-center py-16">
        <Badge variant="accent" className="mb-6 self-start">
          <Sparkles className="h-3 w-3" />
          MVP en cours — Phase 1
        </Badge>
        <h1 className="font-display text-5xl leading-[1.05] tracking-tight md:text-6xl">
          Une bibliothèque silencieuse,
          <br />
          taillée pour le Markdown.
        </h1>
        <p className="mt-6 max-w-2xl text-base leading-relaxed text-[var(--muted-foreground)] md:text-lg">
          Conversion locale d’EPUB et de PDF en Markdown propre, sans dépendance
          cloud, sans coût d’API. Le backend tourne déjà ; l’interface arrive
          ticket par ticket.
        </p>
        <div className="mt-10 flex flex-wrap gap-3">
          <Button size="lg" disabled aria-disabled>
            <FileText className="h-4 w-4" />
            Glisser un livre (bientôt)
          </Button>
          <a
            href="/BRIEF.md"
            className="inline-flex h-11 items-center justify-center rounded-[var(--radius-md)] border border-[var(--border)] px-5 text-base font-medium transition-colors hover:bg-[var(--muted)]"
          >
            Voir le BRIEF
          </a>
        </div>
      </section>

      <section className="grid gap-4 border-t border-[var(--border)] pt-10 md:grid-cols-3">
        <Card
          title="EPUB"
          subtitle="Pandoc"
          body="Structure préservée, titres, listes, italique et gras."
        />
        <Card
          title="PDF natif"
          subtitle="pymupdf4llm"
          body="Texte propre, tableaux, footnotes."
        />
        <Card
          title="Word / HTML"
          subtitle="MarkItDown"
          body="Fallback éprouvé pour docx, html et plain text."
        />
      </section>

      <footer className="mt-16 flex items-center justify-between border-t border-[var(--border)] pt-6 text-xs text-[var(--muted-foreground)]">
        <span>© 2026 Henluy Soro</span>
        <span className="font-mono">v0.0.0 — local-only</span>
      </footer>
    </main>
  );
}

function Card({
  title,
  subtitle,
  body,
}: {
  title: string;
  subtitle: string;
  body: string;
}) {
  return (
    <article className="rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--card)] p-6 transition-colors hover:border-[color-mix(in_oklch,var(--accent)_30%,var(--border))]">
      <div className="flex items-baseline justify-between">
        <h3 className="font-display text-xl">{title}</h3>
        <span className="font-mono text-xs text-[var(--muted-foreground)]">
          {subtitle}
        </span>
      </div>
      <p className="mt-3 text-sm leading-relaxed text-[var(--muted-foreground)]">
        {body}
      </p>
    </article>
  );
}
