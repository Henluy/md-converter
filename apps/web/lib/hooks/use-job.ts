'use client';

import { useQuery } from '@tanstack/react-query';

import { api, type ApiError, type JobRead } from '@/lib/api-client';

const ACTIVE_STATUSES = new Set(['pending', 'processing']);

export function useJob(jobId: string | null) {
  return useQuery<JobRead, ApiError>({
    queryKey: ['job', jobId],
    queryFn: () => {
      if (!jobId) throw new Error('useJob: jobId is required');
      return api.getJob(jobId);
    },
    enabled: !!jobId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 2_000;
      return ACTIVE_STATUSES.has(data.status) ? 2_000 : false;
    },
  });
}
