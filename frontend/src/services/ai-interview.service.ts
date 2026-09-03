import apiClient from '@/lib/api-client';

export interface SyncProctoringRequest {
  application_id: number;
  violation_type: string;
  timestamp: string;
  details?: string;
}

export interface ResumeInterviewRequest {
  application_id: number;
}

export interface PauseInterviewRequest {
  application_id: number;
  time_left?: number;
}

export interface InterviewTimeResponse {
  time_left: number;
  interview_state: string;
  interview_progress: number;
}

export interface GenerateQuestionsRequest {
  application_id: number;
  language?: string;
}

export interface ChatRequest {
  candidate_id: number;
  message: string;
  language?: string;
}

export interface PracticeRequest {
  message: string;
  role?: string;
  language?: string;
  history?: any[];
  current_score?: number;
}

export interface EvaluateFinalRequest {
  application_id: number;
  force_reevaluation?: boolean;
}

export interface FraudReportRequest {
  application_id: number;
  reason: string;
}

export interface InterviewResumeResponse {
  can_resume: boolean;
  application_id: number;
  progress: number;
  total_questions: number;
  history: any[];
  qa_history: any[];
  current_score: number;
  language: string;
  last_saved: string | null;
  state: string;
  time_left: number;
  reason?: string | null;
  skill_metrics: any;
  cv_skill_metrics: any;
}

export const aiInterviewService = {
  syncProctoring: (data: SyncProctoringRequest) =>
    apiClient.post<{ status: string; count: number; server_trust_score: number; review_recommended: boolean }>('/ai/interview/sync-proctoring', data),

  resumeInterview: (data: ResumeInterviewRequest) =>
    apiClient.post<InterviewResumeResponse>('/ai/interview/resume', data),

  pauseInterview: (data: PauseInterviewRequest) =>
    apiClient.post<{ success: boolean; message: string; progress: number; total_questions: number; percentage: number }>('/ai/interview/pause', data),

  getInterviewTime: () =>
    apiClient.get<InterviewTimeResponse>('/ai/interview/time'),

  generateQuestions: (data: GenerateQuestionsRequest) =>
    apiClient.post<{ questions: string[] }>('/ai/generate-interview', data),

  testGroqConnection: () =>
    apiClient.get<{ status: string; message: string; api_key_env: boolean; api_key_db: boolean }>('/ai/test/groq-connection'),

  sendChat: (data: ChatRequest) =>
    apiClient.post<Record<string, any>>('/ai/interview/chat', data),

  practiceInterview: (data: PracticeRequest) =>
    apiClient.post<Record<string, any>>('/ai/interview/practice', data),

  evaluateFinal: (data: EvaluateFinalRequest) =>
    apiClient.post<Record<string, any>>('/ai/interview/evaluate-final', data),

  reportFraud: (data: FraudReportRequest) =>
    apiClient.post<Record<string, any>>('/ai/interview/report-fraud', data),

  uploadVideo: (applicationId: number, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.upload<{ status: string; message: string }>('/ai/interview/upload-video', file, { application_id: String(applicationId) });
  },

  uploadVideoSegment: (applicationId: number, segment: Blob) => {
    const formData = new FormData();
    formData.append('video_segment', segment);
    return apiClient.upload<{ status: string; segment: string }>('/ai/interview/upload-segment', new File([segment], 'segment.webm'), { application_id: String(applicationId) });
  },

  speechToText: (file: File) =>
    apiClient.upload<{ text: string }>('/ai/voice/stt', file),

  textToSpeech: (text: string) =>
    apiClient.post<Record<string, any> | Blob>('/ai/voice/tts', { text }),
};
