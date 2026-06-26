'use client';

import { useMutation, type UseMutationOptions } from '@tanstack/react-query';

import {
  api,
  type ApiError,
  type JobRead,
  type TargetFormat,
} from '@/lib/api-client';

export interface CreateJobVars {
  files: File[];
  targetFormat: TargetFormat;
}

export function useCreateJob(
  options?: Omit<
    UseMutationOptions<JobRead, ApiError, CreateJobVars>,
    'mutationFn'
  >,
) {
  return useMutation<JobRead, ApiError, CreateJobVars>({
    mutationFn: ({ files, targetFormat }) => api.createJob(files, targetFormat),
    ...options,
  });
}
