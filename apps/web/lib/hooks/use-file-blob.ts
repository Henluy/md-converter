'use client';

import { useEffect, useState } from 'react';

import { fileDownloadUrl } from '@/lib/api-client';

/**
 * Fetch a converted file as an object URL for inline embedding (e.g. a PDF in
 * an <iframe>). We go through fetch + createObjectURL because the download
 * endpoint serves an `attachment` disposition — navigating an iframe straight
 * to it would trigger a download instead of rendering. fetch ignores the
 * disposition, so we read the bytes and hand the browser a blob URL.
 */
export function useFileBlobUrl(fileId: string | null, enabled: boolean) {
  const [url, setUrl] = useState<string | null>(null);
  const [isError, setIsError] = useState(false);

  useEffect(() => {
    if (!fileId || !enabled) return;
    let cancelled = false;
    let objectUrl: string | null = null;
    setUrl(null);
    setIsError(false);

    fetch(fileDownloadUrl(fileId))
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.blob();
      })
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setIsError(true);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [fileId, enabled]);

  return { url, isError };
}
