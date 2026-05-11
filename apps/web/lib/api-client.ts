/**
 * Typed HTTP client for the FastAPI backend.
 *
 * Base URL comes from NEXT_PUBLIC_API_URL — empty string falls back to
 * same-origin so the future Next-proxy or Docker compose deploy works
 * out of the box.
 */

export const API_BASE_URL =
  process.env['NEXT_PUBLIC_API_URL'] ?? 'http://localhost:8000';

export const MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024; // 100 MB
export const MAX_FILES_PER_JOB = 50;
export const ALLOWED_EXTENSIONS = ['.epub', '.pdf', '.docx', '.html', '.txt'] as const;

export type AllowedExtension = (typeof ALLOWED_EXTENSIONS)[number];
export type JobStatus = 'pending' | 'processing' | 'done' | 'failed';

export interface FileRead {
  id: string;
  job_id: string;
  original_filename: string;
  original_format: string;
  converter_used: string | null;
  output_path: string | null;
  size_bytes: number | null;
  pages: number | null;
  created_at: string | null;
}

export interface JobRead {
  id: string;
  status: JobStatus;
  created_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  total_files: number;
  processed_files: number;
  files: FileRead[];
}

export interface ApiError {
  status: number;
  detail: string;
}

async function unwrap<T>(response: Response): Promise<T> {
  if (response.ok) {
    return (await response.json()) as T;
  }
  let detail = response.statusText;
  try {
    const body = (await response.json()) as { detail?: string };
    if (body.detail) detail = body.detail;
  } catch {
    // body wasn't JSON — fall back to statusText
  }
  const err: ApiError = { status: response.status, detail };
  throw err;
}

export const api = {
  async createJob(files: File[]): Promise<JobRead> {
    const body = new FormData();
    for (const file of files) {
      body.append('files', file, file.name);
    }
    const response = await fetch(`${API_BASE_URL}/api/jobs`, {
      method: 'POST',
      body,
    });
    return unwrap<JobRead>(response);
  },

  async getJob(jobId: string): Promise<JobRead> {
    const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}`);
    return unwrap<JobRead>(response);
  },

  async listJobs(params: { limit?: number; offset?: number } = {}): Promise<JobRead[]> {
    const search = new URLSearchParams();
    if (params.limit !== undefined) search.set('limit', String(params.limit));
    if (params.offset !== undefined) search.set('offset', String(params.offset));
    const qs = search.toString();
    const response = await fetch(
      `${API_BASE_URL}/api/jobs${qs ? `?${qs}` : ''}`,
    );
    return unwrap<JobRead[]>(response);
  },
};
