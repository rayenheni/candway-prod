import apiClient from '@/lib/api-client';

export interface PublicJob {
  id: number;
  title: string;
  company: string;
  company_id?: number | null;
  company_website?: string | null;
  company_verified?: boolean;
  location: string;
  salary_range: string;
  type: string;
  category: string;
  required_skills: string;
  summary?: string | null;
  logo_url: string;
  applicants?: number;
  created_at?: string | null;
}

export interface PublicJobRubricItem {
  name: string;
  weight: number;
}

export interface PublicJobDetail {
  id: number;
  title: string;
  company: string;
  company_id?: number | null;
  company_website?: string | null;
  company_verified?: boolean;
  location: string;
  salary_range: string;
  type: string;
  description: string;
  summary?: string | null;
  about?: string[];
  responsibilities?: string[];
  required_skills: string;
  requirements?: string | null;
  benefits?: string | null;
  nice_to_have?: string[];
  perks?: string[];
  rubric?: PublicJobRubricItem[];
  category: string;
  logo_url: string;
  recruiter_name?: string | null;
  recruiter_role?: string | null;
  applicants?: number;
  created_at?: string | null;
  valid_through?: string | null;
}

export interface PublicCourse {
  id: number;
  title: string;
  mentor_name: string;
  category: string;
  price: number;
  rating: number;
  thumbnail_url: string;
  description: string;
  duration: string;
  level: string;
}

export interface PublicBlog {
  id: number;
  title: string;
  slug: string;
  summary: string;
  image_url: string;
  tags: string;
  date: string;
  author_name: string;
}

export interface PublicBlogDetail {
  id: number;
  title: string;
  content: string;
  image_url: string;
  tags: string;
  date: string;
  author_name: string;
}

export interface PublicOpportunity {
  id: number;
  title: string;
  type: string;
  description: string;
  link: string;
  image_url: string;
  date: string;
}

export interface PublicStats {
  verified_talent: number;
  active_jobs: number;
  interviews_today: number;
  hiring_companies: number;
}

export interface PublicPlan {
  id: number;
  name: string;
  slug: string;
  target_audience: string;
  price_monthly: number;
  price_yearly: number;
  currency: string;
  description?: string;
  team_seat_limit?: number;
}

export const publicService = {
  getJobs: (params?: { category_id?: number; search?: string }) =>
    apiClient.get<PublicJob[]>('/jobs/public', params),

  getJob: (id: number | string) =>
    apiClient.get<PublicJobDetail>(`/jobs/public/${id}`),

  getCourses: (params?: { category_id?: number; search?: string }) =>
    apiClient.get<PublicCourse[]>('/courses/public', params),

  getBlogs: (limit = 10) =>
    apiClient.get<PublicBlog[]>('/blogs', { limit }),

  getBlog: (slug: string) =>
    apiClient.get<PublicBlogDetail>(`/blogs/${encodeURIComponent(slug)}`),

  getOpportunities: () =>
    apiClient.get<PublicOpportunity[]>('/opportunities'),

  getStats: () =>
    apiClient.get<PublicStats>('/stats/public'),

  getPlans: () =>
    apiClient.get<PublicPlan[]>('/candidate/plans'),
};
