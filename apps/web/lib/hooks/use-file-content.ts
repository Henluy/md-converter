'use client';

import { useQuery } from '@tanstack/react-query';

import { api, type ApiError } from '@/lib/api-client';

export function useFileContent(fileId: string | null) {
  return useQuery<string, ApiError>({
    queryKey: ['file-content', fileId],
    queryFn: () => {
      if (!fileId) throw new Error('useFileContent: fileId is required');
      return api.getFileContent(fileId);
    },
    enabled: !!fileId,
    staleTime: 60_000,
    retry: 0,
  });
}
