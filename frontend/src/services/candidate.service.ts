import apiClient from '@/lib/api-client';

// Define the response structures expected from the Candidate API

export interface CvDocumentSummary {
  id: number;
  application_id: number;
  declared_role?: string | null;
  detected_role?: string | null;
  file_name?: string | null;
  created_at?: string | null;
}

export interface UploadCvResponse {
  success: boolean;
  application_id: number;
  cv_document_id?: number | null;
  status?: string;
  score?: number | null;
  verdict?: string | null;
  detected_role?: string | null;
  message?: string;
}

export interface CandidateComprehensiveProfile {
  id: string;
  name: string;
  email: string;
  phone?: string | null;
  location?: string | null;
  headline?: string | null;
  bio?: string | null;
  avatar?: string | null;
  linkedin_url?: string | null;
  github_url?: string | null;
  portfolio_url?: string | null;
  skills?: string | null;
  tier: string;
  application: {
    id: number;
    status: string;
    score: number;
    verdict?: string | null;
    created_at: string;
  } | null;
  analysis: {
    experience: Array<{ title?: string; role?: string; company?: string; organization?: string; duration?: string; period?: string; description?: string; achievements?: string }>;
    education: Array<{ degree?: string; field?: string; school?: string; institution?: string; year?: string; duration?: string }>;
    skills: Array<{ name: string; level: number }>;
    summary?: string;
    detected_role?: string;
    seniority_level?: string;
    skill_metrics?: Record<string, number>;
    strengths?: string[];
    weaknesses?: string[];
    languages?: string[];
  };
  badges: Array<{
    id: string;
    name: string;
    icon: string;
    description: string;
    color: string;
  }>;
  availability: string;
  work_preference: string;
  salary_min: number;
  salary_max: number;
  relocation_willing?: boolean | null;
  currency: string;
}

export interface CandidateDashboardSummary {
  id: number;
  status: string;
  score: number;
  overall_score: number;
  analysis: any;
  skill_metrics: any;
  intelligence: any;
  applications: Array<{
    id: number;
    title: string;
    company: string;
    status: string;
    created_at: string;
    date: string;
    logo: string;
  }>;
  upcoming_interviews: Array<{
    id: number;
    title: string;
    company: string;
    time: string;
    days: string;
    logo: string;
  }>;
  suggested_jobs: Array<{
    id: number;
    title: string;
    company: string;
    location: string;
    match: number;
    logo: string;
    salary_range: string;
    work_type: string;
  }>;
  checklist: Array<{
    id: string;
    label: string;
    completed: boolean;
  }>;
  ai_activity_feed: Array<{
    type: string;
    icon: string;
    color: string;
    title: string;
    text: string;
    description: string;
    timestamp: string;
  }>;
}

export interface QualificationResponse {
  qualifications: Qualification[];
}

export interface Qualification {
  id: string;
  title: string;
  category: string;
  filename: string;
  file_url: string;
  file_size: number;
  mime_type: string;
  uploaded_at: string;
  verified: boolean;
  user_id: number;
}

export interface PublicProfileResponse {
  id: number;
  name: string;
  headline: string;
  location: string;
  bio: string;
  email: string;
  phone: string | null;
  links: { linkedin: string | null; github: string | null; portfolio: string | null };
  cv: Record<string, any>;
}

export const candidateService = {
  // Profile Endpoints
  getComprehensiveProfile: () => 
    apiClient.get<CandidateComprehensiveProfile>('/candidate/profile/comprehensive'),

  getProfileData: () => 
    apiClient.get<any>('/candidate/profile-data'),

  getProfileVisitors: () =>
    apiClient.get<any[]>('/candidate/profile-visitors'),

  getProfile: () =>
    apiClient.get<any>('/candidate/profile'),

  updateProfile: (data: any) =>
    apiClient.put<any>('/candidate/profile', data),

  completeOnboarding: () =>
    apiClient.post<any>('/candidate/onboarding/complete', {}),

  uploadAvatar: (formData: FormData) =>
    apiClient.postFormData<any>('/candidate/avatar', formData),

  getPublicProfile: (userId: number) =>
    apiClient.get<PublicProfileResponse>(`/candidate/profile/${userId}`),

  recordProfileView: (userId: number) =>
    apiClient.post<any>(`/candidate/profile/${userId}/view`),

  // Qualification Endpoints
  getQualifications: () =>
    apiClient.get<{ qualifications: Qualification[] }>('/candidate/qualifications'),

  uploadQualification: (formData: FormData) =>
    apiClient.postFormData<any>('/candidate/qualifications/upload', formData),

  deleteQualification: (qualId: string) =>
    apiClient.delete<{ message: string }>(`/candidate/qualifications/${qualId}`),

  // Jobs
  getJobs: (limit?: number) =>
    apiClient.get<any[]>(`/candidate/jobs/matches${limit ? `?limit=${limit}` : ''}`),

  getJob: (jobId: number) =>
    apiClient.get<any>(`/candidate/jobs/${jobId}`),

  applyToJob: (jobId: number, source?: string, cvDocumentId?: number) =>
    apiClient.post<any>(`/candidate/jobs/${jobId}/apply`, {
      ...(source ? { source } : {}),
      ...(cvDocumentId ? { cv_document_id: cvDocumentId } : {}),
    }),

  // Applications/Dashboard Endpoints
  getDashboardSummary: () =>
    apiClient.get<CandidateDashboardSummary>('/candidate/applications/me'),

  getDashboard: () =>
    apiClient.get<any>('/candidate/dashboard'),

  // Saved Jobs
  getSavedJobs: () =>
    apiClient.get<any[]>('/candidate/saved-jobs'),

  saveJob: (jobId: number) =>
    apiClient.post<any>('/candidate/saved-jobs', { job_id: jobId }),

  removeSavedJob: (savedJobId: string) =>
    apiClient.delete<any>(`/candidate/saved-jobs/${savedJobId}`),

  // CV Endpoints
  uploadCv: (formData: FormData) =>
    apiClient.postFormData<UploadCvResponse>('/candidate/upload-cv', formData),

  getCvDocuments: () =>
    apiClient.get<{ documents: CvDocumentSummary[] }>('/candidate/cv-documents'),

  getCvData: () =>
    apiClient.get<any>('/candidate/cv-data'),

  saveBuilderData: (sections: any) =>
    apiClient.put<any>('/candidate/builder-data', sections),

  getCvReview: (force = false) =>
    apiClient.get<any>(`/candidate/cv-review${force ? '?force=true' : ''}`),

  // Applications
  getApplicationDetail: (appId: string | number) =>
    apiClient.get<any>(`/candidate/applications/${appId}`),

  createApplication: (data: any) =>
    apiClient.post<any>('/candidate/applications', data),

  withdrawApplication: (appId: string | number) =>
    apiClient.post<any>(`/candidate/applications/${appId}/withdraw`, {}),

  downloadInterviewReport: (appId: string | number) =>
    apiClient.getBlob(`/candidate/applications/${appId}/pdf`),

  // Subscription
  getPlans: () =>
    apiClient.get<any[]>('/candidate/plans'),

  getSubscriptionUsage: () =>
    apiClient.get<any>('/candidate/subscription/usage'),

  upgradePlan: (data: any) =>
    apiClient.post<any>('/candidate/upgrade', data),

  // Interview Endpoints
  getInterviewHistory: () =>
    apiClient.get<any[]>('/candidate/interviews/history'),

  getInterviewAnalysis: (appId: string) =>
    apiClient.get<any>(`/candidate/interviews/${appId}/analysis`),

  resetInterview: (appId: string) =>
    apiClient.post<any>('/candidate/reset-interview', { application_id: appId }),

  // Direct interview
  startDirectInterview: (data: { rubric_id?: number; role_title?: string; skills?: string }) =>
    apiClient.post<any>('/candidate/interviews/direct-start', data),

  // Rubrics
  getRubrics: () =>
    apiClient.get<any[]>('/candidate/rubrics'),
};
