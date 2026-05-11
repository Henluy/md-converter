'use client';

import { useQuery } from '@tanstack/react-query';

import { api, type ApiError, type JobRead } from '@/lib/api-client';

const ACTIVE_STATUSES = new Set(['pending', 'processing']);

/** Poll every 2s while at least one job is still running, otherwise idle. */
export function useJobs(limit = 10) {
  return useQuery<JobRead[], ApiError>({
    queryKey: ['jobs', { limit }],
    queryFn: () => api.listJobs({ limit }),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 2_000;
      const anyActive = data.some((job) => ACTIVE_STATUSES.has(job.status));
      return anyActive ? 2_000 : false;
    },
    refetchIntervalInBackground: false,
  });
}
