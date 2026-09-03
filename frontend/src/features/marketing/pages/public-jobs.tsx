import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { FileText, Loader2, LogIn, Upload } from "lucide-react";
import { cn } from "../../../utils/cn";
import {
  publicService,
  type PublicJob,
  type PublicJobDetail,
} from "../../../services/public.service";
import {
  candidateService,
  type CvDocumentSummary,
} from "../../../services/candidate.service";
import { useAuth } from "../../../contexts/auth-context";
import { useLanguage } from "../../../contexts/language-context";
import {
  DottedArrow,
  DotCluster,
  DotHalo,
  IconArrowRight,
  IconBriefcase,
  IconCheck,
  IconLock,
  IconMail,
  IconMic,
  IconSpark,
  IconUnlock,
  LogoMark,
  Reveal,
  TunisiaDots,
} from "./candway-landing";

/* ------------------------------------------------------------------ */
/*  Data                                                               */
/* ------------------------------------------------------------------ */

type WorkMode = "Remote" | "Hybrid" | "On-site";

type Job = {
  id: number;
  title: string;
  company: string;
  companyMark: string;
  markGradient: string;
  logoUrl: string | null;
  companyVerified: boolean;
  companyWebsite: string | null;
  location: string;
  workMode: WorkMode | null;
  type: string;
  posted: string;
  applicants: number;
  salary: string;
  tags: string[];
  summary: string;
  about: string[];
  responsibilities: string[];
  requirements: string[];
  niceToHave: string[];
  perks: string[];
  rubric: { name: string; weight: number }[];
  manager: { name: string; role: string; initials: string; gradient: string };
};

const MODES: ("All" | WorkMode)[] = ["All", "Remote", "Hybrid", "On-site"];

function getApplySteps(t: (k: string) => string) {
  return [
    { label: t("careers.applyOnce"), Icon: IconBriefcase },
    { label: t("careers.scoredVsRubric"), Icon: IconSpark },
    { label: t("careers.recruiterInvite"), Icon: IconLock },
    { label: t("careers.aiInterview"), Icon: IconMic },
  ];
}

function getTrustCards(t: (k: string) => string) {
  return [
    {
      Icon: IconSpark,
      title: t("careers.trustTitle1"),
      body: t("careers.trustBody1"),
    },
    {
      Icon: IconLock,
      title: t("careers.trustTitle2"),
      body: t("careers.trustBody2"),
    },
    {
      Icon: IconUnlock,
      title: t("careers.trustTitle3"),
      body: t("careers.trustBody3"),
    },
  ];
}

const GRADIENTS = [
  "from-violet-500 to-fuchsia-400",
  "from-sky-500 to-indigo-400",
  "from-emerald-500 to-teal-400",
  "from-fuchsia-500 to-primary-500",
  "from-amber-500 to-orange-400",
  "from-rose-500 to-primary-600",
];

function initialsOf(name: string): string {
  return (
    name
      .split(/\s+/)
      .map((w) => w.charAt(0))
      .filter(Boolean)
      .slice(0, 2)
      .join("")
      .toUpperCase() || "CW"
  );
}

function splitParagraphs(html?: string | null): string[] {
  if (!html) return [];
  const normalized = html
    .replace(/<\/(p|h1|h2|h3|h4)>/gi, "\n\n")
    .replace(/<(li|br)>/gi, "\n")
    .replace(/<[^>]+>/g, " ");
  return normalized
    .split("\n\n")
    .map((p) => p.replace(/\s+/g, " ").trim())
    .filter(Boolean);
}

function timeAgo(iso: string | null | undefined, t: (k: string) => string): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const days = Math.max(0, Math.floor((Date.now() - then) / 86_400_000));
  if (days <= 0) return t("careers.today");
  if (days === 1) return t("careers.dayAgo");
  if (days < 7) return t("careers.daysAgo").replace("{n}", String(days));
  if (days < 30) {
    const weeks = Math.floor(days / 7);
    return t("careers.weeksAgo").replace("{n}", String(weeks));
  }
  const months = Math.floor(days / 30);
  return t("careers.monthsAgo").replace("{n}", String(months));
}

function deriveWorkMode(location?: string | null): WorkMode | null {
  const loc = (location || "").toLowerCase();
  if (loc.includes("remote")) return "Remote";
  if (loc.includes("hybrid")) return "Hybrid";
  if (loc.includes("on-site") || loc.includes("onsite")) return "On-site";
  return null;
}

function toSkills(requiredSkills?: string | null): string[] {
  return (requiredSkills || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function cvLabel(d: CvDocumentSummary, t: (k: string) => string): string {
  const role = d.declared_role || d.detected_role;
  if (role) return role;
  if (d.file_name) return d.file_name;
  if (d.created_at)
    return t("jobDetails.cvFrom").replace("{date}", new Date(d.created_at).toLocaleDateString());
  return t("jobDetails.cvId").replace("{id}", String(d.id));
}

function firstName(name: string | undefined, t: (k: string) => string): string {
  return (name || "").trim().split(/\s+/)[0] || t("jobDetails.andWelcome");
}

function mapJob(src: PublicJob | PublicJobDetail, t: (k: string) => string): Job {
  const p = src as PublicJobDetail;
  const id = Number(p.id);
  const title = p.title || t("careers.untitledRole");
  const company = p.company || t("careers.genericCompany");
  const skills = toSkills(p.required_skills);
  const about = splitParagraphs(p.description);
  const summary = p.summary?.trim() || (about.length ? about[0].slice(0, 160) : "");
  const workMode = deriveWorkMode(p.location);
  const tags = skills.length
    ? skills.slice(0, 4)
    : p.category && p.category !== t("careers.generalCategory")
      ? [p.category]
      : [];
  const rubric = Array.isArray(p.rubric) && p.rubric.length ? p.rubric : [];
  const requirements = rubric.length ? rubric.map((r) => r.name) : skills;
  const responsibilities =
    Array.isArray(p.responsibilities) && p.responsibilities.length
      ? p.responsibilities
      : [];
  const niceToHave = Array.isArray(p.nice_to_have) ? p.nice_to_have : [];
  const perks = Array.isArray(p.perks) ? p.perks : [];
  const recruiterName = p.recruiter_name || "";
  const managerName = recruiterName || company;
  return {
    id,
    title,
    company,
    companyMark: initialsOf(company),
    markGradient: GRADIENTS[id % GRADIENTS.length],
    logoUrl: p.logo_url || null,
    companyVerified: Boolean(p.company_verified),
    companyWebsite: p.company_website || null,
    location: p.location || t("careers.remote"),
    workMode,
    type: p.type || t("careers.fullTime"),
    posted: timeAgo(p.created_at, t),
    applicants: p.applicants ?? 0,
    salary: p.salary_range || t("careers.salaryNotDisclosed"),
    tags,
    summary,
    about,
    responsibilities,
    requirements,
    niceToHave,
    perks,
    rubric,
    manager: {
      name: managerName,
      role: p.recruiter_role || (recruiterName ? t("careers.hiringManager") : t("careers.recruitingTeam")),
      initials: initialsOf(managerName),
      gradient: GRADIENTS[(id + 2) % GRADIENTS.length],
    },
  };
}

/* ------------------------------------------------------------------ */
/*  Local icons                                                        */
/* ------------------------------------------------------------------ */

function localSvg(className?: string) {
  return {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    className,
    "aria-hidden": true,
  };
}

export function IconArrowLeft({ className }: { className?: string }) {
  return (
    <svg {...localSvg(className)}>
      <path d="M20 12H4" />
      <path d="m11 5-7 7 7 7" />
    </svg>
  );
}

export function IconSearch({ className }: { className?: string }) {
  return (
    <svg {...localSvg(className)}>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </svg>
  );
}

export function IconPin({ className }: { className?: string }) {
  return (
    <svg {...localSvg(className)}>
      <path d="M12 21s-6.5-5.5-6.5-10.5a6.5 6.5 0 0 1 13 0C18.5 15.5 12 21 12 21Z" />
      <circle cx="12" cy="10.5" r="2.3" />
    </svg>
  );
}

export function IconClock({ className }: { className?: string }) {
  return (
    <svg {...localSvg(className)}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 2" />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  Shared bits                                                        */
/* ------------------------------------------------------------------ */

const careersBtn =
  "inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-primary-600/30 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-xl hover:shadow-primary-600/35 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600";

const inputCls =
  "w-full rounded-xl border border-ink/10 bg-white/80 px-4 py-3 text-sm text-ink shadow-sm outline-none transition placeholder:text-ink-faint/70 focus:border-primary-400 focus:ring-4 focus:ring-primary-500/10";

export function CareersShell({
  children,
  onBack,
  title,
  badge,
}: {
  children: React.ReactNode;
  onBack: () => void;
  title: string;
  badge?: string;
}) {
  const { language, setLanguage, t } = useLanguage();
  return (
    <div className="relative min-h-screen overflow-x-clip bg-[#fbfaff] font-sans text-ink">
      <div className="cw-noise pointer-events-none fixed inset-0 z-40" aria-hidden />

      <header className="sticky top-0 z-50 px-3 pt-3 sm:px-5">
        <div className="mx-auto flex max-w-6xl items-center justify-between rounded-full border border-white/80 bg-white/75 px-3.5 py-2 shadow-[0_16px_44px_-22px_rgba(108,57,232,0.4)] backdrop-blur-xl sm:px-4">
          <div className="flex items-center gap-2.5">
            <LogoMark className="h-8 w-8" />
            <span className="text-[16px] font-semibold tracking-tight">Candway</span>
            <span className="rounded-full bg-primary-500/12 px-2 py-0.5 text-[10px] font-bold tracking-wide text-primary-700">
              {badge ?? t("careers.careersBadge")}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1 rounded-full border border-ink/10 bg-white/80 p-0.5 text-xs font-semibold">
              <button
                type="button"
                onClick={() => setLanguage("en")}
                className={cn(
                  "rounded-full px-2.5 py-0.5 transition-colors",
                  language === "en" ? "bg-primary-600 text-white shadow-sm" : "text-ink-soft hover:text-ink"
                )}
              >
                EN
              </button>
              <button
                type="button"
                onClick={() => setLanguage("fr")}
                className={cn(
                  "rounded-full px-2.5 py-0.5 transition-colors",
                  language === "fr" ? "bg-primary-600 text-white shadow-sm" : "text-ink-soft hover:text-ink"
                )}
              >
                FR
              </button>
            </div>
            <button
              type="button"
              onClick={onBack}
              className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] font-semibold text-ink-soft transition-colors hover:bg-ink/5 hover:text-ink"
            >
              <IconArrowLeft className="h-3.5 w-3.5" />
              {title}
            </button>
          </div>
        </div>
      </header>

      {children}

      <footer className="border-t border-ink/8 py-10">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-5 sm:flex-row sm:px-8">
          <div className="flex items-center gap-2.5">
            <LogoMark className="h-7 w-7" />
            <p className="text-sm font-semibold">Candway</p>
            <p className="font-accent text-sm italic text-ink-faint">
              {t("careers.footerTagline")}
            </p>
          </div>
          <div className="flex items-center gap-5 text-[13px] text-ink-soft">
            <a
              href="mailto:careers@candway.tn"
              className="flex items-center gap-1.5 hover:text-primary-700"
            >
              <IconMail className="h-4 w-4" />
              careers@candway.tn
            </a>
            <span className="text-ink-faint">{t("careers.footerCopyright")}</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

function CompanyBadge({ job, size }: { job: Job; size: "sm" | "lg" }) {
  const dims =
    size === "lg"
      ? "h-14 w-14 rounded-2xl text-lg"
      : "h-11 w-11 rounded-xl text-sm";
  if (job.logoUrl) {
    return (
      <span
        className={cn(
          "grid place-items-center overflow-hidden bg-white shadow-md shadow-primary-500/20",
          dims
        )}
      >
        <img
          src={job.logoUrl}
          alt={job.company}
          loading="lazy"
          className="h-full w-full object-cover"
        />
      </span>
    );
  }
  return (
    <span
      className={cn(
        "grid place-items-center bg-gradient-to-br font-bold text-white shadow-md shadow-primary-500/20",
        job.markGradient,
        dims
      )}
    >
      {job.companyMark}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  Careers (list) page                                                */
/* ------------------------------------------------------------------ */

function JobCard({ job, onOpen, delay }: { job: Job; onOpen: () => void; delay: number }) {
  const { t } = useLanguage();
  return (
    <Reveal delay={delay} className="h-full">
      <button
        type="button"
        onClick={onOpen}
        className="cw-glass cw-lift group flex h-full w-full flex-col rounded-3xl p-6 text-left"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <CompanyBadge job={job} size="sm" />
            <div>
              <p className="text-sm font-semibold text-ink">{job.company}</p>
              <p className="flex items-center gap-1 text-xs text-ink-faint">
                <IconPin className="h-3 w-3" />
                {job.location}
              </p>
            </div>
          </div>
          {job.posted && (
            <span className="flex items-center gap-1 rounded-full bg-ink/4 px-2.5 py-1 text-[11px] font-medium text-ink-faint">
              <IconClock className="h-3 w-3" />
              {job.posted}
            </span>
          )}
        </div>

        <h3 className="mt-4 text-xl font-semibold tracking-tight text-ink transition-colors group-hover:text-primary-700">
          {job.title}
        </h3>
        <p className="mt-1.5 text-sm leading-relaxed text-ink-soft">
          {job.summary || t("careers.openRoleFallback")}
        </p>

        {job.tags.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-1.5">
            {job.tags.map((t) => (
              <span
                key={t}
                className="rounded-full border border-primary-200/70 bg-primary-500/8 px-2.5 py-1 text-[11px] font-semibold text-primary-700"
              >
                {t}
              </span>
            ))}
          </div>
        )}

        <div className="mt-5 flex items-center justify-between border-t border-ink/8 pt-4">
          <p className="text-xs font-medium text-ink-faint">
            {job.applicants} {t("careers.applicants")}
            {job.salary !== t("careers.salaryNotDisclosed") && (
              <>
                {" · "}
                <span className="text-primary-700">{job.salary}</span>
              </>
            )}
          </p>
          <span className="flex items-center gap-1.5 text-sm font-semibold text-primary-700">
            {t("careers.apply")}
            <IconArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
          </span>
        </div>
      </button>
    </Reveal>
  );
}

export default function CareersPage() {
  const navigate = useNavigate();
  const { t } = useLanguage();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<"All" | WorkMode>("All");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    publicService
      .getJobs()
      .then((data) => {
        if (active) setJobs((data || []).map((j) => mapJob(j, t)));
      })
      .catch((err) => {
        if (active) setError(err?.message || t("careers.loadError"));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [t]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return jobs.filter((j) => {
      const okMode = mode === "All" || j.workMode === mode;
      const okQuery =
        !q ||
        j.title.toLowerCase().includes(q) ||
        j.company.toLowerCase().includes(q) ||
        j.location.toLowerCase().includes(q) ||
        j.tags.some((t) => t.toLowerCase().includes(q));
      return okMode && okQuery;
    });
  }, [jobs, query, mode]);

  const totalApplicants = useMemo(() => jobs.reduce((sum, j) => sum + j.applicants, 0), [jobs]);

  const applySteps = getApplySteps(t);
  const trustCards = getTrustCards(t);

  const resetFilters = () => {
    setQuery("");
    setMode("All");
  };

  return (
    <CareersShell onBack={() => (window.location.hash = "#top")} title={t("careers.backToSite")}>
      {/* hero */}
      <section className="relative overflow-hidden">
        <div
          className="pointer-events-none absolute inset-0"
          aria-hidden
          style={{
            background:
              "radial-gradient(60% 50% at 50% 0%, rgba(157,114,255,0.18), transparent 62%)",
          }}
        />
        <TunisiaDots className="pointer-events-none absolute -right-8 top-10 hidden h-[135%] text-primary-500/[0.13] [mask-image:linear-gradient(to_left,black_55%,transparent)] lg:block" />
        <DotHalo className="pointer-events-none absolute -left-24 top-1/3 h-72 w-72 text-primary-400/20" />
        <DotCluster className="pointer-events-none absolute right-[8%] top-24 h-9 w-9 text-primary-400/40" />

        <div className="relative mx-auto max-w-6xl px-5 pb-14 pt-16 sm:px-8 md:pt-20">
          <div className="mx-auto max-w-2xl text-center">
            <span className="inline-flex items-center gap-2 rounded-full border border-primary-200/80 bg-white/70 px-3.5 py-1.5 text-xs font-semibold text-primary-700 shadow-sm backdrop-blur">
              <span className="cw-blink h-1.5 w-1.5 rounded-full bg-emerald-500" />
              {t('careers.heroEyebrow')}
            </span>
            <h1 className="mt-6 text-4xl font-semibold leading-[1.05] tracking-[-0.03em] text-ink sm:text-5xl lg:text-6xl">
              {t('careers.heroTitlePrefix')}{" "}
              <span className="font-accent font-medium italic text-primary-600">
                {t('careers.heroTitleHighlight')}
              </span>
            </h1>
            <p className="mx-auto mt-5 max-w-xl text-base leading-relaxed text-ink-soft sm:text-lg">
              {t('careers.heroSubtitle')}
            </p>
          </div>

          {/* search + filters */}
          <div className="mx-auto mt-9 max-w-2xl">
            <div className="flex items-center gap-3 rounded-2xl border border-ink/10 bg-white/85 px-4 py-3.5 shadow-[0_18px_44px_-20px_rgba(108,57,232,0.35)] backdrop-blur transition focus-within:border-primary-400 focus-within:ring-4 focus-within:ring-primary-500/10">
              <IconSearch className="h-4.5 w-4.5 shrink-0 text-ink-faint" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t('careers.searchPlaceholder')}
                className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink-faint/70"
              />
            </div>
            <div className="mt-3.5 flex flex-wrap items-center justify-center gap-2">
              {MODES.map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  className={cn(
                    "rounded-full px-4 py-1.5 text-[13px] font-semibold transition-all",
                    mode === m
                      ? "bg-ink text-white shadow-md"
                      : "bg-white/70 text-ink-soft hover:bg-white hover:text-ink"
                  )}
                >
                  {m === "All" ? t('careers.allModes') : m === "Remote" ? t('careers.remote') : m === "Hybrid" ? t('careers.hybrid') : t('careers.onsite')}
                </button>
              ))}
            </div>
          </div>

          <p className="mt-6 text-center text-[13px] font-medium text-ink-faint">
            {loading
              ? t("careers.loading")
              : t("careers.showingRoles")
                  .replace("{x}", String(filtered.length))
                  .replace("{y}", String(jobs.length))
                  .replace("{n}", String(totalApplicants))}
          </p>
        </div>
      </section>

      {/* jobs */}
      <section className="mx-auto max-w-6xl px-5 pb-20 sm:px-8">
        {loading ? (
          <div className="grid gap-5 md:grid-cols-2">
            {[0, 1, 2, 3].map((i) => (
              <div
                key={i}
                className="cw-glass h-64 animate-pulse rounded-3xl bg-white/60"
                aria-hidden
              />
            ))}
          </div>
        ) : error ? (
          <Reveal>
            <div className="cw-glass mx-auto max-w-md rounded-3xl p-10 text-center">
              <p className="text-lg font-semibold text-ink">{t("careers.loadError")}</p>
              <p className="mt-2 text-sm text-ink-soft">{error}</p>
              <button
                type="button"
                onClick={() => {
                  setLoading(true);
                  publicService
                    .getJobs()
                    .then((data) => setJobs((data || []).map((j) => mapJob(j, t))))
                    .catch((err) => setError(err?.message || t("careers.loadError")))
                    .finally(() => setLoading(false));
                }}
                className="mt-5 text-sm font-semibold text-primary-700 hover:underline"
              >
                {t("careers.tryAgain")}
              </button>
            </div>
          </Reveal>
        ) : jobs.length === 0 ? (
          <Reveal>
            <div className="cw-glass mx-auto max-w-md rounded-3xl p-10 text-center">
              <p className="text-lg font-semibold text-ink">{t("careers.emptyTitle")}</p>
              <p className="mt-2 text-sm text-ink-soft">{t("careers.emptyBody")}</p>
            </div>
          </Reveal>
        ) : filtered.length === 0 ? (
          <Reveal>
            <div className="cw-glass mx-auto max-w-md rounded-3xl p-10 text-center">
              <p className="text-lg font-semibold text-ink">{t("careers.noMatchTitle")}</p>
              <p className="mt-2 text-sm text-ink-soft">{t("careers.noMatchBody")}</p>
              <button
                type="button"
                onClick={resetFilters}
                className="mt-5 text-sm font-semibold text-primary-700 hover:underline"
              >
                {t("careers.resetFilters")}
              </button>
            </div>
          </Reveal>
        ) : (
          <div className="grid gap-5 md:grid-cols-2">
            {filtered.map((job, i) => (
              <JobCard
                key={job.id}
                job={job}
                onOpen={() => navigate(`/careers/${job.id}`)}
                delay={i * 70}
              />
            ))}
          </div>
        )}
      </section>

      {/* how it works — candidate version */}
      <section className="border-y border-ink/6 bg-white/50 py-14">
        <div className="mx-auto max-w-6xl px-5 sm:px-8">
          <Reveal className="text-center">
            <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-primary-700">
              {t("careers.howTitle")}
            </p>
            <h2 className="mt-3 text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
              {t("careers.howHead1")}{" "}
              <span className="font-accent font-medium italic text-primary-600">
                {t("careers.howHead2")}
              </span>
            </h2>
          </Reveal>
          <Reveal delay={100}>
            <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
              {applySteps.map(({ label, Icon }, i) => (
                <div key={label} className="flex items-center gap-3">
                  <span className="flex items-center gap-2.5 rounded-2xl border border-ink/8 bg-white/85 px-4 py-3 shadow-sm">
                    <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-primary-500 to-indigo-500 text-white">
                      <Icon className="h-4 w-4" />
                    </span>
                    <span className="text-sm font-semibold text-ink">
                      <span className="mr-1.5 text-[11px] font-bold text-primary-600">
                        {i + 1}
                      </span>
                      {label}
                    </span>
                  </span>
                  {i < applySteps.length - 1 && (
                    <DottedArrow className="hidden h-2.5 w-9 shrink-0 text-primary-500/50 md:block" />
                  )}
                </div>
              ))}
            </div>
            <p className="mt-6 flex items-center justify-center gap-2 text-[13px] font-medium text-ink-soft">
              <IconLock className="h-3.5 w-3.5 text-primary-600" />
              {t("careers.howNote")}
            </p>
          </Reveal>
        </div>
      </section>

      {/* trust cards */}
      <section className="mx-auto max-w-6xl px-5 py-16 sm:px-8">
        <div className="grid gap-5 md:grid-cols-3">
          {trustCards.map(({ Icon, title, body }, i) => (
            <Reveal key={title} delay={i * 90}>
              <div className="cw-glass cw-lift h-full rounded-3xl p-6">
                <span className="grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br from-primary-500 to-indigo-500 text-white shadow-md shadow-primary-500/25">
                  <Icon className="h-5 w-5" />
                </span>
                <h3 className="mt-4 text-lg font-semibold tracking-tight text-ink">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-ink-soft">{body}</p>
              </div>
            </Reveal>
          ))}
        </div>

        <Reveal delay={150}>
          <div className="mt-6 flex flex-col items-center justify-between gap-4 rounded-3xl border border-primary-200/60 bg-gradient-to-br from-white via-primary-50 to-lilac-100 px-6 py-7 sm:flex-row sm:px-8">
            <div>
              <p className="text-base font-semibold text-ink">{t("careers.ctaTitle")}</p>
              <p className="mt-1 text-sm text-ink-soft">
                {t("careers.ctaBody")}
              </p>
            </div>
            <a href="#top" className={careersBtn}>
              {t("careers.ctaBtn")}
              <IconArrowRight className="h-4 w-4" />
            </a>
          </div>
        </Reveal>
      </section>
    </CareersShell>
  );
}

/* ------------------------------------------------------------------ */
/*  Job detail page                                                    */
/* ------------------------------------------------------------------ */

function getReviewSteps(t: (k: string) => string) {
  return [
    {
      label: t("jobDetails.review1_t"),
      body: t("jobDetails.review1_b"),
    },
    {
      label: t("jobDetails.review2_t"),
      body: t("jobDetails.review2_b"),
    },
    {
      label: t("jobDetails.review3_t"),
      body: t("jobDetails.review3_b"),
    },
    {
      label: t("jobDetails.review4_t"),
      body: t("jobDetails.review4_b"),
    },
  ];
}

export function PublicJobDetailPage({
  job: initialJob,
  onBack,
}: {
  job?: Job;
  onBack?: () => void;
}) {
  const { jobId = "" } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const { t } = useLanguage();
  const { user, isAuthenticated } = useAuth();
  const [job, setJob] = useState<Job | null>(initialJob ?? null);
  const [loading, setLoading] = useState(!initialJob);
  const [error, setError] = useState("");
  const [cvDocs, setCvDocs] = useState<CvDocumentSummary[]>([]);
  const [cvDocsLoading, setCvDocsLoading] = useState(false);
  const [cvMode, setCvMode] = useState<"existing" | "upload">("existing");
  const [selectedCvId, setSelectedCvId] = useState<number | "">("");
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState("");
  const [why, setWhy] = useState("");
  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState("");
  const [result, setResult] = useState<{
    message: string;
    application_id?: number;
    alreadyApplied?: boolean;
  } | null>(null);

  const goBack = onBack || (() => navigate("/careers"));
  const reviewSteps = getReviewSteps(t);

  useEffect(() => {
    if (initialJob) return;
    let active = true;
    setLoading(true);
    setError("");
    publicService
      .getJob(jobId)
      .then((data) => {
        if (active) {
          setJob(mapJob(data, t));
          document.title = `${data.title} — ${data.company}${t("jobDetails.titleSuffix")}`;
        }
      })
      .catch((err) => {
        if (active) setError(err?.message || t("jobDetails.loadError"));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [jobId, initialJob, t]);

  // Load the candidate's saved CVs so the apply form can offer the
  // "use an existing CV" choice. Anonymous visitors see a login invite
  // instead (they have no CVs of their own yet).
  useEffect(() => {
    if (!isAuthenticated) return;
    let active = true;
    setCvDocsLoading(true);
    candidateService
      .getCvDocuments()
      .then((res) => {
        if (active) {
          const docs = res.documents ?? [];
          setCvDocs(docs);
          if (docs.length) setSelectedCvId(docs[0].id);
        }
      })
      .catch(() => {
        // Picker is optional — the form still works via upload mode.
      })
      .finally(() => {
        if (active) setCvDocsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [isAuthenticated]);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!job) return;
    setApplyError("");
    setApplying(true);
    try {
      let docId: number | null;
      if (cvMode === "upload") {
        if (!file) {
          setApplyError(t("jobDetails.attachRequired"));
          setApplying(false);
          return;
        }
        const formData = new FormData();
        formData.append("file", file);
        formData.append("declared_role", job.title);
        const uploaded = await candidateService.uploadCv(formData);
        docId = uploaded.cv_document_id ?? null;
        if (!docId) {
          throw new Error(t("jobDetails.attachFailed"));
        }
      } else {
        if (!selectedCvId) {
          setApplyError(t("jobDetails.chooseCvError"));
          setApplying(false);
          return;
        }
        docId = Number(selectedCvId);
      }
      const res = await candidateService.applyToJob(job.id, source || "direct", docId);
      setResult({
        ...res,
        alreadyApplied: res?.message === "Already applied",
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t("jobDetails.somethingWrong");
      setApplyError(msg);
    } finally {
      setApplying(false);
    }
  };

  if (loading) {
    return (
      <CareersShell onBack={goBack} title={t("jobDetails.allOpenRoles")}>
        <div className="mx-auto max-w-6xl px-5 py-16 sm:px-8">
          <div className="grid gap-8 lg:grid-cols-[1fr_340px]">
            <div className="space-y-4">
              <div className="h-10 w-40 animate-pulse rounded-xl bg-white/70" />
              <div className="h-16 w-3/4 animate-pulse rounded-2xl bg-white/70" />
              <div className="h-4 w-full animate-pulse rounded bg-white/70" />
              <div className="h-4 w-5/6 animate-pulse rounded bg-white/70" />
              <div className="h-4 w-2/3 animate-pulse rounded bg-white/70" />
            </div>
            <div className="h-80 animate-pulse rounded-3xl bg-white/70" />
          </div>
        </div>
      </CareersShell>
    );
  }

  if (error || !job) {
    return (
      <CareersShell onBack={goBack} title={t('jobDetails.backToCareers')}>
        <div className="mx-auto max-w-xl px-5 py-20 text-center">
          <h1 className="text-3xl font-semibold tracking-tight text-ink">{t('jobDetails.notFound')}</h1>
          <p className="mt-3 text-sm text-ink-soft">
            {error || t('jobDetails.notFound')}
          </p>
          <button
            type="button"
            onClick={goBack}
            className="mt-6 inline-flex items-center gap-2 rounded-xl border border-ink/10 bg-white/75 px-5 py-3 text-sm font-semibold text-ink transition-all hover:-translate-y-0.5 hover:border-primary-300 hover:text-primary-700"
          >
            <IconArrowLeft className="h-4 w-4" />
            {t('jobDetails.backToCareers')}
          </button>
        </div>
      </CareersShell>
    );
  }

  return (
    <CareersShell onBack={goBack} title={t('jobDetails.backToCareers')}>
      {/* header */}
      <section className="relative overflow-hidden">
        <div
          className="pointer-events-none absolute inset-0"
          aria-hidden
          style={{
            background:
              "radial-gradient(60% 55% at 75% 0%, rgba(157,114,255,0.18), transparent 62%)",
          }}
        />
        <DotHalo className="pointer-events-none absolute -right-24 top-10 h-80 w-80 text-primary-400/25" />
        <DotCluster className="pointer-events-none absolute left-[6%] top-28 h-9 w-9 text-primary-400/40" />

        <div className="relative mx-auto max-w-6xl px-5 pb-12 pt-12 sm:px-8 md:pt-16">
          <button
            type="button"
            onClick={goBack}
            className="flex items-center gap-1.5 text-sm font-semibold text-ink-soft transition-colors hover:text-ink"
          >
            <IconArrowLeft className="h-4 w-4" />
            {t('jobDetails.backToCareers')}
          </button>

          <div className="mt-7 flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-2xl">
              <div className="flex items-center gap-3.5">
                <CompanyBadge job={job} size="lg" />
                <div>
                  <p className="text-sm font-semibold text-ink">
                    {job.company}
                    {job.companyVerified && (
                      <span className="ml-2 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-bold text-emerald-700">
                        {t('careers.verifiedRole')}
                      </span>
                    )}
                  </p>
                  <p className="text-[13px] text-ink-faint">
                    {t('jobDetails.posted')} {job.posted || t("jobDetails.recently")} · {job.applicants} {t('jobDetails.applicants')}
                  </p>
                </div>
              </div>
              <h1 className="mt-5 text-4xl font-semibold leading-[1.06] tracking-[-0.025em] text-ink sm:text-5xl">
                {job.title}
              </h1>
              <div className="mt-5 flex flex-wrap gap-2">
                {[
                  [t('jobDetails.location'), job.location, IconPin],
                  [t('jobDetails.contractType'), job.type, IconBriefcase],
                ].map(([label, value, Icon]) => (
                  <span
                    key={String(label)}
                    className="flex items-center gap-2 rounded-full border border-ink/10 bg-white/80 px-3.5 py-1.5 text-[13px] font-medium text-ink-soft"
                  >
                    <Icon className="h-3.5 w-3.5 text-primary-600" />
                    {value as string}
                  </span>
                ))}
                {job.workMode && (
                  <span className="flex items-center gap-2 rounded-full border border-ink/10 bg-white/80 px-3.5 py-1.5 text-[13px] font-medium text-ink-soft">
                    <IconClock className="h-3.5 w-3.5 text-primary-600" />
                    {job.workMode === 'Remote' ? t('careers.remote') : job.workMode === 'Hybrid' ? t('careers.hybrid') : t('careers.onsite')}
                  </span>
                )}
              </div>
            </div>

            <div className="flex flex-col items-start gap-3 lg:items-end">
              <button
                type="button"
                onClick={() =>
                  document.getElementById("apply")?.scrollIntoView({
                    behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
                      ? "auto"
                      : "smooth",
                    block: "start",
                  })
                }
                className={careersBtn}
              >
                {t('jobDetails.applyForRole')}
                <IconArrowRight className="h-4 w-4" />
              </button>
              <p className="flex items-center gap-2 rounded-full border border-primary-200/70 bg-white/70 px-3.5 py-1.5 text-[12px] font-semibold text-primary-800">
                <IconLock className="h-3.5 w-3.5" />
                {t('careers.trustTitle2')}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* body */}
      <section className="mx-auto max-w-6xl px-5 pb-20 sm:px-8">
        <div className="grid gap-8 lg:grid-cols-[1fr_340px]">
          {/* main column */}
          <div className="space-y-10">
            {job.about.length > 0 && (
              <Reveal>
                <div>
                  <h2 className="text-xl font-semibold tracking-tight text-ink">{t("jobDetails.aboutRole")}</h2>
                  <div className="mt-3 space-y-4">
                    {job.about.map((p, i) => (
                      <p key={i} className="text-[15px] leading-relaxed text-ink-soft">
                        {p}
                      </p>
                    ))}
                  </div>
                </div>
              </Reveal>
            )}

            {job.responsibilities.length > 0 && (
              <Reveal>
                <div>
                  <h2 className="text-xl font-semibold tracking-tight text-ink">{t("jobDetails.whatYoullDo")}</h2>
                  <ul className="mt-4 space-y-2.5">
                    {job.responsibilities.map((r, i) => (
                      <li key={i} className="flex items-start gap-3">
                        <span className="mt-0.5 grid h-5.5 w-5.5 shrink-0 place-items-center rounded-full bg-primary-500/10 text-primary-700">
                          <IconCheck className="h-3 w-3" />
                        </span>
                        <span className="text-[15px] leading-relaxed text-ink-soft">{r}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </Reveal>
            )}

            {job.requirements.length > 0 && (
              <Reveal>
                <div className="cw-glass rounded-3xl p-6 sm:p-7">
                  <div className="flex items-center justify-between gap-3">
                    <h2 className="text-xl font-semibold tracking-tight text-ink">
                      {t("jobDetails.whatLookingFor")}
                    </h2>
                    <span className="rounded-full bg-primary-500/10 px-3 py-1 text-[11px] font-bold tracking-wide text-primary-700">
                      {job.rubric.length ? t("jobDetails.rubricBadge") : t("jobDetails.skillsBadge")}
                    </span>
                  </div>
                  <p className="mt-2 text-sm leading-relaxed text-ink-soft">
                    {job.rubric.length
                      ? t("jobDetails.rubricDesc")
                      : t("jobDetails.skillsDesc")}
                  </p>
                  <ol className="mt-5 space-y-3">
                    {job.requirements.map((r, i) => (
                      <li key={i} className="flex items-start gap-3">
                        <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-primary-500/12 text-[11px] font-bold text-primary-700">
                          {i + 1}
                        </span>
                        <span className="pt-0.5 text-[15px] leading-relaxed text-ink-soft">{r}</span>
                      </li>
                    ))}
                  </ol>
                  {job.niceToHave.length > 0 && (
                    <div className="mt-5 border-t border-ink/8 pt-5">
                      <p className="text-xs font-semibold uppercase tracking-wide text-ink-faint">
                        {t("jobDetails.niceToHave")}
                      </p>
                      <div className="mt-2.5 flex flex-wrap gap-2">
                        {job.niceToHave.map((n, i) => (
                          <span
                            key={i}
                            className="rounded-full border border-ink/10 bg-white/80 px-3 py-1.5 text-[12px] font-medium text-ink-soft"
                          >
                            {n}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </Reveal>
            )}

            {job.perks.length > 0 && (
              <Reveal>
                <div>
                  <h2 className="text-xl font-semibold tracking-tight text-ink">{t("jobDetails.whatYouGet")}</h2>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    {job.perks.map((p, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-3 rounded-2xl border border-ink/8 bg-white/80 px-4 py-3.5"
                      >
                        <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-emerald-500/12 text-emerald-600">
                          <IconCheck className="h-3.5 w-3.5" />
                        </span>
                        <span className="text-sm font-medium text-ink-soft">{p}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </Reveal>
            )}

            <Reveal>
              <div className="relative overflow-hidden rounded-3xl bg-ink px-6 py-8 text-white shadow-[0_30px_70px_-30px_rgba(23,18,58,0.6)] sm:px-8">
                <div className="cw-dots pointer-events-none absolute inset-0 opacity-20 invert" aria-hidden />
                <div
                  className="pointer-events-none absolute -top-20 left-1/2 h-44 w-96 -translate-x-1/2 rounded-full bg-primary-500/30 blur-3xl"
                  aria-hidden
                />
                <div className="relative">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-white/50">
                    {t("jobDetails.howReviewed")}
                  </p>
                  <ol className="mt-6 grid gap-6 sm:grid-cols-2">
                    {reviewSteps.map((s, i) => (
                      <li key={s.label} className="flex gap-3">
                        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-white/10 text-sm font-bold text-primary-300">
                          {i + 1}
                        </span>
                        <div>
                          <p className="text-sm font-semibold">{s.label}</p>
                          <p className="mt-1 text-[13px] leading-relaxed text-white/65">{s.body}</p>
                        </div>
                      </li>
                    ))}
                  </ol>
                  <p className="mt-6 flex items-center gap-2 border-t border-white/10 pt-5 text-[13px] text-white/70">
                    <IconLock className="h-3.5 w-3.5 shrink-0" />
                    {t("jobDetails.everyStepVisible")}
                  </p>
                </div>
              </div>
            </Reveal>

            {/* application form */}
            <Reveal>
              <div id="apply" className="cw-glass-strong scroll-mt-28 rounded-3xl p-6 sm:p-8">
                {result ? (
                  <div className="flex flex-col items-center gap-4 py-10 text-center">
                    <span className="grid h-16 w-16 place-items-center rounded-full bg-emerald-500/12 text-emerald-600">
                      <IconCheck className="h-8 w-8" />
                    </span>
                    <h3 className="text-2xl font-semibold tracking-tight text-ink">
                      {result.alreadyApplied ? t("jobDetails.alreadyAppliedTitle") : t("jobDetails.appReceived")}
                    </h3>
                    <p className="max-w-md text-sm leading-relaxed text-ink-soft">
                      {result.alreadyApplied
                        ? t("jobDetails.alreadyAppliedBody").replace("{role}", job.title)
                        : t("jobDetails.thanksBody")
                            .replace("{name}", firstName(user?.firstName || user?.lastName, t))
                            .replace("{role}", job.title)}
                    </p>
                    <div className="mt-3 flex flex-wrap items-center justify-center gap-3 text-[13px] font-semibold text-ink-soft">
                      <span className="rounded-full bg-emerald-500/10 px-3 py-1.5 text-emerald-700">
                        {t("jobDetails.step1Scored")}
                      </span>
                      <DottedArrow className="h-2.5 w-8 text-primary-500/50" />
                      <span className="rounded-full bg-primary-500/10 px-3 py-1.5 text-primary-700">
                        {t("jobDetails.step2Invite")}
                      </span>
                      <DottedArrow className="h-2.5 w-8 text-primary-500/50" />
                      <span className="rounded-full bg-ink/5 px-3 py-1.5 text-ink-soft">
                        {t("jobDetails.step3Interview")}
                      </span>
                    </div>
                    <div className="mt-3 flex flex-wrap items-center justify-center gap-3">
                      <Link
                        to="/dashboard"
                        className={cn(careersBtn, "px-6")}
                      >
                        {t("jobDetails.openPortal")}
                        <IconArrowRight className="h-4 w-4" />
                      </Link>
                      <button
                        type="button"
                        onClick={goBack}
                        className="inline-flex items-center gap-2 rounded-xl border border-ink/10 bg-white/75 px-5 py-3 text-sm font-semibold text-ink transition-all hover:-translate-y-0.5 hover:border-primary-300 hover:text-primary-700"
                      >
                        <IconArrowLeft className="h-4 w-4" />
                        {t("jobDetails.backToRoles")}
                      </button>
                    </div>
                  </div>
                ) : !isAuthenticated ? (
                  <div className="flex flex-col items-center gap-4 py-10 text-center">
                    <span className="grid h-14 w-14 place-items-center rounded-full bg-primary-500/10 text-primary-700">
                      <LogIn className="h-6 w-6" />
                    </span>
                    <div>
                      <h3 className="text-xl font-semibold tracking-tight text-ink">
                        {t("jobDetails.loginTitle")}
                      </h3>
                      <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-ink-soft">
                        {t("jobDetails.loginBody").replace("{role}", job.title)}
                      </p>
                    </div>
                    <div className="mt-2 flex flex-col gap-2.5 sm:flex-row">
                      <Link
                        to={`/auth/login?redirect=${encodeURIComponent(`/careers/${job.id}`)}`}
                        className={cn(careersBtn, "px-6")}
                      >
                        <LogIn className="h-4 w-4" />
                        {t("jobDetails.loginTitle")}
                      </Link>
                      <Link
                        to={`/auth/register?role=candidate&redirect=${encodeURIComponent(`/careers/${job.id}`)}`}
                        className="inline-flex items-center justify-center gap-2 rounded-xl border border-ink/10 bg-white/75 px-6 py-3 text-sm font-semibold text-ink transition-all hover:-translate-y-0.5 hover:border-primary-300 hover:text-primary-700"
                      >
                        {t("jobDetails.createAccount")}
                      </Link>
                    </div>
                    <p className="text-xs text-ink-faint">
                      {t("jobDetails.haveAccount")}
                    </p>
                  </div>
                ) : (
                  <>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h3 className="text-xl font-semibold tracking-tight text-ink">{t("jobDetails.applyTitle")}</h3>
                        <p className="mt-1 text-sm text-ink-soft">
                          {t("jobDetails.applyMeta").replace(
                            "{account}",
                            user?.email || t("jobDetails.yourAccount")
                          )}
                        </p>
                      </div>
                      <span className="shrink-0 rounded-full bg-emerald-500/10 px-3 py-1 text-[11px] font-semibold text-emerald-700">
                        {job.applicants} {t("jobDetails.applicants")}
                      </span>
                    </div>

                    <form onSubmit={handleSubmit} className="mt-6 space-y-5">
                      <div>
                        <p className="mb-2 text-sm font-medium text-ink">{t("jobDetails.yourCv")}</p>
                        <div className="grid grid-cols-2 gap-1.5 rounded-2xl bg-ink/4 p-1.5">
                          <button
                            type="button"
                            onClick={() => setCvMode("existing")}
                            className={cn(
                              "flex items-center justify-center gap-2 rounded-xl px-3 py-2.5 text-sm font-semibold transition-all",
                              cvMode === "existing"
                                ? "bg-white text-ink shadow-sm"
                                : "text-ink-soft hover:text-ink"
                            )}
                          >
                            <FileText className="h-4 w-4" />
                            {t("careers.useExistingCv")}
                          </button>
                          <button
                            type="button"
                            onClick={() => setCvMode("upload")}
                            className={cn(
                              "flex items-center justify-center gap-2 rounded-xl px-3 py-2.5 text-sm font-semibold transition-all",
                              cvMode === "upload"
                                ? "bg-white text-ink shadow-sm"
                                : "text-ink-soft hover:text-ink"
                            )}
                          >
                            <Upload className="h-4 w-4" />
                            {t("careers.uploadNewCv")}
                          </button>
                        </div>

                        {cvMode === "existing" ? (
                          cvDocsLoading ? (
                            <div className="mt-3 flex items-center gap-2 text-sm text-ink-soft">
                              <Loader2 className="h-4 w-4 animate-spin" />
                              {t("jobDetails.loadingCvs")}
                            </div>
                          ) : cvDocs.length === 0 ? (
                            <div className="mt-3 rounded-xl border border-dashed border-ink/15 bg-white/60 px-4 py-3 text-sm text-ink-soft">
                              {t("jobDetails.noSavedCv")}{" "}
                              <button
                                type="button"
                                onClick={() => setCvMode("upload")}
                                className="font-semibold text-primary-700 underline underline-offset-2"
                              >
                                {t("jobDetails.uploadOne")}
                              </button>
                              .
                            </div>
                          ) : (
                            <select
                              value={selectedCvId}
                              onChange={(e) => setSelectedCvId(e.target.value ? Number(e.target.value) : "")}
                              className={cn(inputCls, "mt-3 appearance-none")}
                            >
                              {cvDocs.map((d) => (
                                <option key={d.id} value={d.id}>
                                  {cvLabel(d, t)}
                                </option>
                              ))}
                            </select>
                          )
                        ) : (
                          <div className="mt-3">
                            <label
                              htmlFor="app-cv-file"
                              className="flex cursor-pointer items-center justify-between gap-3 rounded-xl border border-dashed border-primary-300/70 bg-primary-500/5 px-4 py-3.5 transition-colors hover:bg-primary-500/10"
                            >
                              <span className="flex min-w-0 items-center gap-2.5 text-sm font-medium text-ink">
                                <Upload className="h-4 w-4 shrink-0 text-primary-700" />
                                <span className="truncate">
                                  {file ? file.name : t("jobDetails.chooseCv")}
                                </span>
                              </span>
                              <span className="shrink-0 rounded-lg bg-primary-600 px-3 py-1.5 text-xs font-semibold text-white">
                                {t("jobDetails.browse")}
                              </span>
                              <input
                                id="app-cv-file"
                                type="file"
                                accept=".pdf,.doc,.docx,.txt"
                                className="hidden"
                                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                              />
                            </label>
                          </div>
                        )}
                      </div>

                      <div>
                        <label htmlFor="app-source" className="mb-1.5 block text-sm font-medium text-ink">
                          {t("careers.howHeard")}{" "}
                          <span className="text-ink-faint">{t("jobDetails.optional")}</span>
                        </label>
                        <select
                          id="app-source"
                          value={source}
                          onChange={(e) => setSource(e.target.value)}
                          className={cn(inputCls, "appearance-none")}
                        >
                          <option value="">{t("jobDetails.sourceSelect")}</option>
                          <option value="linkedin">{t("jobDetails.sourceLinkedIn")}</option>
                          <option value="social_media">{t("jobDetails.sourceSocial")}</option>
                          <option value="website">{t("jobDetails.sourceWebsite")}</option>
                          <option value="referral">{t("jobDetails.sourceReferral")}</option>
                          <option value="direct">{t("jobDetails.sourceDirect")}</option>
                        </select>
                      </div>

                      <div>
                        <label htmlFor="app-why" className="mb-1.5 block text-sm font-medium text-ink">
                          {t("jobDetails.whyRole")}{" "}
                          <span className="text-ink-faint">{t("jobDetails.optional")}</span>
                        </label>
                        <textarea
                          id="app-why"
                          rows={3}
                          placeholder={t("jobDetails.whyPlaceholder")}
                          className={cn(inputCls, "resize-none")}
                          value={why}
                          onChange={(e) => setWhy(e.target.value)}
                        />
                      </div>

                      {applyError && (
                        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700">
                          {applyError}
                        </div>
                      )}

                      <button
                        type="submit"
                        disabled={applying}
                        className={cn(
                          careersBtn,
                          "w-full py-3.5 disabled:cursor-not-allowed disabled:opacity-60"
                        )}
                      >
                        {applying ? (
                          <>
                            <Loader2 className="h-4 w-4 animate-spin" />
                            {t("jobDetails.submitting")}
                          </>
                        ) : (
                          <>
                            {t("jobDetails.sendApplication")}
                            <IconArrowRight className="h-4 w-4" />
                          </>
                        )}
                      </button>
                      <p className="text-center text-xs text-ink-faint">
                        {t("jobDetails.attachNote").replace(
                          "{account}",
                          user?.email || t("jobDetails.yourAccount")
                        )}
                      </p>
                    </form>
                  </>
                )}
              </div>
            </Reveal>
          </div>

          {/* sidebar */}
          <div className="space-y-5 lg:sticky lg:top-28 lg:self-start">
            <Reveal delay={80}>
              <div className="cw-glass rounded-3xl p-6">
                <p className="text-xs font-semibold uppercase tracking-wide text-ink-faint">
                  {t("jobDetails.atAGlance")}
                </p>
                <dl className="mt-4 space-y-3 text-sm">
                  {[
                    [t("jobDetails.salary"), job.salary],
                    [t("jobDetails.location"), job.location],
                    ...(job.workMode ? ([[t("jobDetails.mode"), job.workMode]] as const) : []),
                    [t("jobDetails.type"), job.type],
                    ...(job.posted ? ([[t("jobDetails.posted"), job.posted]] as const) : []),
                  ].map(([k, v]) => (
                    <div key={k} className="flex items-start justify-between gap-3">
                      <dt className="shrink-0 text-ink-faint">{k}</dt>
                      <dd className="text-right font-semibold text-ink">{v}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            </Reveal>

            {job.rubric.length > 0 && (
              <Reveal delay={140}>
                <div className="cw-glass rounded-3xl p-6">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold uppercase tracking-wide text-ink-faint">
                      {t("jobDetails.rubricGlance")}
                    </p>
                    <IconSpark className="h-4 w-4 text-primary-600" />
                  </div>
                  <ul className="mt-4 space-y-3">
                    {job.rubric.map((r) => (
                      <li key={r.name}>
                        <div className="flex items-center justify-between text-[13px]">
                          <span className="font-medium text-ink">{r.name}</span>
                          <span className="font-semibold text-primary-700">
                            {r.weight > 0 ? `${r.weight}%` : t("jobDetails.weighted")}
                          </span>
                        </div>
                        <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-lilac-200">
                          <div
                            className="h-full rounded-full bg-gradient-to-r from-primary-500 to-indigo-400"
                            style={{ width: `${Math.min(100, r.weight * 2.4)}%` }}
                          />
                        </div>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-4 text-[12px] leading-relaxed text-ink-faint">
                    {t("jobDetails.publicByDesign")}
                  </p>
                </div>
              </Reveal>
            )}

            <Reveal delay={200}>
              <div className="cw-glass rounded-3xl p-6">
                <p className="text-xs font-semibold uppercase tracking-wide text-ink-faint">
                  {t("jobDetails.hiringTeam")}
                </p>
                <div className="mt-4 flex items-center gap-3">
                  <span
                    className={cn(
                      "grid h-12 w-12 place-items-center rounded-full bg-gradient-to-br text-sm font-bold text-white",
                      job.manager.gradient
                    )}
                  >
                    {job.manager.initials}
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-ink">{job.manager.name}</p>
                    {job.manager.role && (
                      <p className="text-[12px] text-ink-faint">{job.manager.role}</p>
                    )}
                  </div>
                </div>
                {job.companyWebsite && (
                  <a
                    href={job.companyWebsite}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-4 flex items-center justify-center gap-2 rounded-xl border border-primary-200/70 bg-white/70 px-3 py-2.5 text-[13px] font-semibold text-primary-700 transition-colors hover:bg-white"
                  >
                    {t("jobDetails.visitCompany").replace("{company}", job.company)}
                    <IconArrowRight className="h-3.5 w-3.5" />
                  </a>
                )}
                <div className="mt-4 flex items-center gap-2 rounded-xl bg-primary-500/8 px-3 py-2.5">
                  <IconMail className="h-4 w-4 shrink-0 text-primary-700" />
                  <p className="text-[12px] font-medium text-primary-800">
                    {t("jobDetails.questions")}
                  </p>
                </div>
              </div>
            </Reveal>

            <Reveal delay={260}>
              <div className="flex items-center gap-2.5 rounded-2xl border border-emerald-500/20 bg-emerald-500/8 px-4 py-3.5">
                <IconLock className="h-4.5 w-4.5 shrink-0 text-emerald-600" />
                <p className="text-[12px] font-medium leading-relaxed text-emerald-800">
                  {t("jobDetails.ruleNote")}
                </p>
              </div>
            </Reveal>
          </div>
        </div>
      </section>
    </CareersShell>
  );
}