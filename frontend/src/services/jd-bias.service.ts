import apiClient from '@/lib/api-client';

export interface AnalyzeJdRequest {
  title: string;
  description: string;
  skills?: string[];
}

export interface RewriteJdRequest {
  title: string;
  description: string;
  style: string;
}

export interface AnalyzeJdResponse {
  score: number;
  categories: { name?: string; items?: { phrase: string; category?: string; suggestion?: string }[] }[];
  recommendations?: string[];
  [key: string]: unknown;
}

export interface RewriteJdResponse {
  rewritten_description: string;
  [key: string]: unknown;
}

export interface WordListsResponse {
  categories?: { name?: string; category?: string; words?: string[]; items?: { phrase?: string; word?: string }[] }[];
  [key: string]: unknown;
}

export const jdBiasService = {
  analyzeJd: (body: AnalyzeJdRequest) =>
    apiClient.post<AnalyzeJdResponse>('/jd/analyze', body),

  analyzeExistingJd: (jobId: number) =>
    apiClient.post(`/jd/analyze/${jobId}`),

  rewriteJd: (body: RewriteJdRequest) =>
    apiClient.post<RewriteJdResponse>('/jd/rewrite', body),

  getWordLists: () =>
    apiClient.get<WordListsResponse>('/jd/word-lists'),
};
