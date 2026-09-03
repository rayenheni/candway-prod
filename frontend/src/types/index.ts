// ============================================================
// Candway Intelligence Platform - Core Types
// ============================================================

// Auth Types
export type UserRole = 'candidate' | 'recruiter' | 'mentor' | 'admin' | 'company';

export interface User {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  avatar?: string;
  role: UserRole;
  organization?: Organization;
  organizationId?: string;
  isEmailVerified: boolean;
  is_demo?: boolean;
  lastLoginAt?: string;
  createdAt: string;
  updatedAt: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  logo?: string;
  plan: SubscriptionPlan;
  createdAt: string;
}

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  password: string;
  firstName: string;
  lastName: string;
  role: UserRole;
}

export interface OrgRegisterData {
  companyName: string;
  adminName: string;
  adminEmail: string;
  adminPassword: string;
  domain?: string;
  slug?: string;
  billingEmail?: string;
  billingAddress?: string;
  taxId?: string;
}

export interface OrgRegisterResponse {
  access_token: string;
  token_type: string;
  role: UserRole;
  id: number;
  name: string;
  email_verification_required: boolean;
  company_id: number;
}

// OpenAPI auth contracts. Access tokens are intentionally never persisted by
// the frontend; the existing FastAPI cookie session remains the source of
// truth after login/refresh.
export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
  role: UserRole;
}

export interface GuestLoginResponse extends AuthTokenResponse {
  name?: string | null;
  email?: string | null;
  redirect?: string | null;
  application_id?: number | null;
}

export interface UserLoginRequest {
  email: string;
  password: string;
  required_role?: string | null;
}

export interface UserSignupRequest {
  email: string;
  password: string;
  role: 'candidate' | 'recruiter';
  name?: string | null;
  phone?: string | null;
  location?: string | null;
  company_name?: string | null;
  headline?: string | null;
}

export interface UserUpdateRequest {
  name?: string | null;
  phone?: string | null;
  headline?: string | null;
  bio?: string | null;
  location?: string | null;
  linkedin_url?: string | null;
  github_url?: string | null;
  portfolio_url?: string | null;
  avatar_url?: string | null;
  password?: string | null;
}

// Subscription Types
export type SubscriptionPlan = 'free' | 'starter' | 'professional' | 'enterprise';

export interface Subscription {
  id: string;
  plan: SubscriptionPlan;
  status: 'active' | 'canceled' | 'past_due' | 'trialing';
  currentPeriodStart: string;
  currentPeriodEnd: string;
  cancelAtPeriodEnd: boolean;
  features: string[];
}

// Job Types
export type JobStatus = 'draft' | 'published' | 'closed' | 'archived';
export type JobType = 'full_time' | 'part_time' | 'contract' | 'internship' | 'freelance';
export type ExperienceLevel = 'entry' | 'mid' | 'senior' | 'lead' | 'executive';

export interface Job {
  id: string;
  title: string;
  description: string;
  department: string;
  location: string;
  remote: boolean;
  type: JobType;
  experienceLevel: ExperienceLevel;
  salaryMin?: number;
  salaryMax?: number;
  currency: string;
  status: JobStatus;
  skills: Skill[];
  requirements: string[];
  benefits: string[];
  applicationCount: number;
  publishedAt?: string;
  createdAt: string;
  updatedAt: string;
  recruiterId: string;
  organizationId: string;
}

// Candidate Types
export type ApplicationStatus = 
  | 'pending' 
  | 'screening' 
  | 'shortlisted' 
  | 'interview' 
  | 'offer' 
  | 'hired' 
  | 'rejected' 
  | 'withdrawn';

export interface Candidate {
  id: string;
  userId: string;
  user: User;
  resume?: string;
  resumeText?: string;
  skills: Skill[];
  experience: Experience[];
  education: Education[];
  summary?: string;
  linkedIn?: string;
  portfolio?: string;
  location?: string;
  source?: string;
  aiScore?: number;
  createdAt: string;
}

export interface Application {
  id: string;
  candidateId: string;
  candidate: Candidate;
  jobId: string;
  job: Job;
  status: ApplicationStatus;
  source?: string;
  coverLetter?: string;
  resumeUrl?: string;
  aiScore?: number;
  aiNotes?: string;
  notes: Note[];
  createdAt: string;
  updatedAt: string;
}

export interface Skill {
  id: string;
  name: string;
  category: string;
  level?: number; // 1-100
  verified?: boolean;
}

export interface Experience {
  id: string;
  title: string;
  company: string;
  location?: string;
  startDate: string;
  endDate?: string;
  current: boolean;
  description?: string;
}

export interface Education {
  id: string;
  degree: string;
  institution: string;
  field: string;
  startDate: string;
  endDate?: string;
  gpa?: number;
}

// Interview Types
export type InterviewType = 'phone' | 'video' | 'onsite' | 'technical' | 'behavioral';
export type InterviewStatus = 'scheduled' | 'in_progress' | 'completed' | 'canceled' | 'no_show';

export interface Interview {
  id: string;
  applicationId: string;
  application: Application;
  type: InterviewType;
  status: InterviewStatus;
  scheduledAt: string;
  duration: number; // minutes
  location?: string;
  meetingUrl?: string;
  interviewers: User[];
  feedback?: InterviewFeedback;
  notes?: string;
  createdAt: string;
}

export interface InterviewFeedback {
  id: string;
  interviewId: string;
  rating: number; // 1-5
  strengths: string[];
  weaknesses: string[];
  recommendation: 'strong_hire' | 'hire' | 'neutral' | 'no_hire' | 'strong_no_hire';
  notes: string;
  scores: Record<string, number>;
  submittedBy: User;
  submittedAt: string;
}

// Pipeline Types
export interface PipelineStage {
  id: string;
  name: string;
  order: number;
  color: string;
  applicationCount: number;
}

export interface Pipeline {
  id: string;
  jobId: string;
  stages: PipelineStage[];
  applications: Application[];
}

// Note Types
export interface Note {
  id: string;
  content: string;
  author: User;
  createdAt: string;
  updatedAt: string;
}

// Message Types
export interface Message {
  id: string;
  senderId: string;
  sender: User;
  receiverId: string;
  content: string;
  read: boolean;
  createdAt: string;
}

export interface Conversation {
  id: string;
  participants: User[];
  lastMessage?: Message;
  unreadCount: number;
  updatedAt: string;
}

// Calendar Types
export interface CalendarEvent {
  id: string;
  title: string;
  description?: string;
  start: string;
  end: string;
  type: 'interview' | 'meeting' | 'task' | 'reminder';
  color?: string;
  attendees?: User[];
  location?: string;
  meetingUrl?: string;
}

// Analytics Types
export interface AnalyticsData {
  label: string;
  value: number;
  change?: number;
  trend?: 'up' | 'down' | 'flat';
}

export interface ChartDataPoint {
  date: string;
  value: number;
  category?: string;
}

// Notification Types
export type NotificationType = 'info' | 'success' | 'warning' | 'error' | 'message' | 'interview' | 'application';

export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  read: boolean;
  actionUrl?: string;
  createdAt: string;
}

// Email Campaign Types
export interface EmailCampaign {
  id: string;
  name: string;
  subject: string;
  content: string;
  status: 'draft' | 'scheduled' | 'sent' | 'failed';
  recipientCount: number;
  openRate?: number;
  clickRate?: number;
  scheduledAt?: string;
  sentAt?: string;
  createdAt: string;
}

// Course Types (Candidate Learning)
export interface Course {
  id: string;
  title: string;
  description: string;
  category: string;
  duration: number; // hours
  level: 'beginner' | 'intermediate' | 'advanced';
  thumbnail?: string;
  progress: number; // 0-100
  enrolled: boolean;
  modules: CourseModule[];
  certificateUrl?: string;
  rating: number;
  enrollmentCount: number;
}

export interface CourseModule {
  id: string;
  title: string;
  type: 'video' | 'reading' | 'quiz' | 'exercise';
  duration: number; // minutes
  completed: boolean;
}

// Rubric Types
export interface Rubric {
  id: string;
  name: string;
  description: string;
  criteria: RubricCriteria[];
  jobId?: string;
  createdAt: string;
}

export interface RubricCriteria {
  id: string;
  name: string;
  description: string;
  weight: number;
  levels: RubricLevel[];
}

export interface RubricLevel {
  score: number;
  label: string;
  description: string;
}

// Skill Tree Types
export interface SkillTree {
  id: string;
  name: string;
  nodes: SkillNode[];
  edges: SkillEdge[];
}

export interface SkillNode {
  id: string;
  skill: string;
  level: number;
  category: string;
  x: number;
  y: number;
}

export interface SkillEdge {
  source: string;
  target: string;
  type: 'prerequisite' | 'related' | 'advancement';
}

// Achievement Types
export interface Achievement {
  id: string;
  name: string;
  description: string;
  icon: string;
  unlockedAt?: string;
  progress: number;
  maxProgress: number;
}

// API Response Types
export interface ApiResponse<T> {
  data: T;
  message?: string;
  status: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface ApiError {
  message: string;
  status: number;
  errors?: unknown;
}

// Dashboard Types
export interface DashboardStats {
  active_jobs_count?: number;
  active_jobs_change?: string;
  total_applications?: number;
  applications_change?: string;
  applied?: number;
  screening_count?: number;
  interviewing?: number;
  interviews_change?: string;
  offer_count?: number;
  scheduled_interviews?: number;
  total_interviews?: number;
  interviews_completed_count?: number;
  avg_time_to_hire?: string | number;
  hire_time_change?: string;
  hire_time_trend?: 'up' | 'down';
  in_review?: number;
  hired?: number;
}

export interface RecentActivity {
  id: string;
  type: string;
  message: string;
  timestamp: string;
  user?: User;
  metadata?: Record<string, unknown>;
}

// Platform Health Types (Admin)
export interface PlatformHealth {
  uptime: number;
  responseTime: number;
  errorRate: number;
  activeUsers: number;
  totalUsers: number;
  aiRequestsToday: number;
  aiSuccessRate: number;
  storageUsed: number;
  storageTotal: number;
}

// Permission Types
export interface Permission {
  id: string;
  name: string;
  resource: string;
  action: string;
}

export interface Role {
  id: string;
  name: UserRole;
  permissions: Permission[];
}
