'use client';

import { useMutation, type UseMutationOptions } from '@tanstack/react-query';

import { api, type ApiError, type JobRead } from '@/lib/api-client';

export function useCreateJob(
  options?: Omit<
    UseMutationOptions<JobRead, ApiError, File[]>,
    'mutationFn'
  >,
) {
  return useMutation<JobRead, ApiError, File[]>({
    mutationFn: (files) => api.createJob(files),
    ...options,
  });
}
