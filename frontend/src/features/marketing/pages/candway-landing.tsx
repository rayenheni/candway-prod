import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { Link, useLocation } from "react-router";
import { cn } from "../../../utils/cn";
import { useLanguage } from "../../../contexts/language-context";
import firasPhoto from "../../../assets/avatars/firas.jpg";
import samiPhoto from "../../../assets/avatars/sami.jpg";
import rayenPhoto from "../../../assets/avatars/rayen.jpg";
import leaPhoto from "../../../assets/avatars/lea.jpg";
import { appAuthUrl } from "../utils/auth-url";
import { getApiBaseUrl } from "../../../utils/domain-routing";

/* ------------------------------------------------------------------ */
/*  Data                                                               */
/* ------------------------------------------------------------------ */

const DEMO_EMAIL = "hello@candway.tn";

function navLinks(t: (key: string) => string) {
  return [
    { label: t("landing.nav.product"), href: "#product" },
    { label: t("landing.nav.howItWorks"), href: "#how" },
    { label: t("landing.nav.candidates"), href: "#candidates" },
    { label: t("landing.nav.blogs"), href: "/blogs" },
    { label: t("landing.nav.careers"), href: "/careers" },
  ];
}

function stripItems(t: (key: string) => string) {
  return [
    t("landing.strip.1"),
    t("landing.strip.2"),
    t("landing.strip.3"),
    t("landing.strip.4"),
    t("landing.strip.5"),
    t("landing.strip.6"),
    t("landing.strip.7"),
    t("landing.strip.8"),
  ];
}

type TourId = "score" | "invite" | "interview" | "portal" | "report";

const TOUR: {
  id: TourId;
  step: string;
  title: string;
  body: string;
}[] = [
  {
    id: "score",
    step: "01",
    title: "Score every CV against the role",
    body: "Public applications and bulk uploads land in the same campaign. Candway reads each CV against your rubric and ranks the pile by evidence — not keywords.",
  },
  {
    id: "invite",
    step: "02",
    title: "You choose who gets interviewed",
    body: "Interviews stay locked until you send an invite. Candidates can never start one on their own.",
  },
  {
    id: "interview",
    step: "03",
    title: "Collect evidence, not vibes",
    body: "Invited candidates complete a structured AI interview. Candway maps answers back to the same rubric so the interview can be compared, not just replayed.",
  },
  {
    id: "portal",
    step: "04",
    title: "Give candidates a real status",
    body: "Applicants see the job, their match, and whether an invite has arrived — no ghosting, no mystery portal.",
  },
  {
    id: "report",
    step: "05",
    title: "Leave with a shortlist you can send",
    body: "The campaign ends in a recruiter report: ranked names, rubric evidence, interview notes. Ready for a hiring manager, a client, or a debrief.",
  },
];

const TOUR_IDS = TOUR.map((t) => t.id);

function getCandidateRows(t: (key: string) => string) {
  return [
    {
      initials: "FR",
      name: "Firas Ray",
      role: t("landing.roles.marketingLead"),
      match: 82,
      status: t("landing.stage.statusInvite"),
      tone: "go" as const,
      source: t("landing.stage.sourcePublicApply"),
      avatar: "from-violet-500 to-fuchsia-400",
      photo: firasPhoto,
    },
    {
      initials: "SK",
      name: "Sami Kallel",
      role: t("landing.roles.projectManager"),
      match: 79,
      status: t("landing.stage.statusReview"),
      tone: "wait" as const,
      source: t("landing.stage.sourceCampaignUpload"),
      avatar: "from-sky-500 to-indigo-400",
      photo: samiPhoto,
    },
    {
      initials: "RH",
      name: "Rayen Heni",
      role: t("landing.roles.seoLead"),
      match: 77,
      status: t("landing.stage.statusShortlist"),
      tone: "done" as const,
      source: t("landing.stage.sourcePublicApply"),
      avatar: "from-emerald-500 to-teal-400",
      photo: rayenPhoto,
    },
    {
      initials: "LB",
      name: "Lea Ben Salah",
      role: t("landing.roles.contentLead"),
      match: 71,
      status: t("landing.stage.statusLocked"),
      tone: "lock" as const,
      source: t("landing.stage.sourceCampaignUpload"),
      avatar: "from-amber-500 to-orange-400",
      photo: leaPhoto,
    },
  ];
}

function getRubric(t: (key: string) => string) {
  return [
    { name: t("landing.rubric.1"), score: 88, note: t("landing.rubric.note1") },
    { name: t("landing.rubric.2"), score: 84, note: t("landing.rubric.note2") },
    { name: t("landing.rubric.3"), score: 79, note: t("landing.rubric.note3") },
    { name: t("landing.rubric.4"), score: 76, note: t("landing.rubric.note4") },
  ];
}

function getPaths(t: (key: string) => string) {
  return [
    {
      kicker: t("landing.how.pathA.kicker"),
      title: t("landing.how.pathA.title"),
      forWho: t("landing.how.pathA.forWho"),
      Icon: IconBriefcase,
      steps: [
        t("landing.how.pathA.s1"),
        t("landing.how.pathA.s2"),
        t("landing.how.pathA.s3"),
        t("landing.how.pathA.s4"),
      ],
    },
    {
      kicker: t("landing.how.pathB.kicker"),
      title: t("landing.how.pathB.title"),
      forWho: t("landing.how.pathB.forWho"),
      Icon: IconFile,
      steps: [
        t("landing.how.pathB.s1"),
        t("landing.how.pathB.s2"),
        t("landing.how.pathB.s3"),
        t("landing.how.pathB.s4"),
      ],
    },
  ];
}

function getRecruiterPoints(t: (key: string) => string) {
  return [
    { title: t("landing.audience.r1_title"), body: t("landing.audience.r1_body") },
    { title: t("landing.audience.r2_title"), body: t("landing.audience.r2_body") },
    { title: t("landing.audience.r3_title"), body: t("landing.audience.r3_body") },
  ];
}

function getCandidatePoints(t: (key: string) => string) {
  return [
    { title: t("landing.audience.c1_title"), body: t("landing.audience.c1_body") },
    { title: t("landing.audience.c2_title"), body: t("landing.audience.c2_body") },
    { title: t("landing.audience.c3_title"), body: t("landing.audience.c3_body") },
  ];
}

function getCandidateSteps(t: (key: string) => string) {
  return [
    { label: t("landing.steps.applied"), sub: t("landing.steps.appliedSub"), state: "done" as const },
    { label: t("landing.steps.scored"), sub: t("landing.steps.scoredSub"), state: "done" as const },
    { label: t("landing.steps.invite"), sub: t("landing.steps.inviteSub"), state: "done" as const },
    { label: t("landing.steps.aiInterview"), sub: t("landing.steps.aiInterviewSub"), state: "active" as const },
  ];
}

function getDiff(t: (key: string) => string) {
  return [
    {
      kicker: t("landing.diff.d1_kicker"),
      title: t("landing.diff.d1_title"),
      body: t("landing.diff.d1_body"),
    },
    {
      kicker: t("landing.diff.d2_kicker"),
      title: t("landing.diff.d2_title"),
      body: t("landing.diff.d2_body"),
    },
    {
      kicker: t("landing.diff.d3_kicker"),
      title: t("landing.diff.d3_title"),
      body: t("landing.diff.d3_body"),
    },
  ];
}

type Tier = {
  id: string;
  name: string;
  price: string;
  unit: string;
  blurb: string;
  features: string[];
  cta: string;
  featured?: boolean;
  perks?: string[];
};

function getTiers(t: (key: string) => string): Tier[] {
  return [
    {
      id: "shortlist",
      name: t("landing.pricing.shortlist.name"),
      price: "99",
      unit: "TND",
      blurb: t("landing.pricing.shortlist.blurb"),
      features: [
        t("landing.pricing.shortlist.f1"),
        t("landing.pricing.shortlist.f2"),
        t("landing.pricing.shortlist.f3"),
        t("landing.pricing.shortlist.f4"),
      ],
      cta: t("landing.pricing.shortlist.cta"),
    },
    {
      id: "campaign",
      name: t("landing.pricing.campaign.name"),
      price: "199",
      unit: "TND",
      blurb: t("landing.pricing.campaign.blurb"),
      featured: true,
      perks: [t("landing.pricing.campaign.p1"), t("landing.pricing.campaign.p2")],
      features: [
        t("landing.pricing.campaign.f1"),
        t("landing.pricing.campaign.f2"),
        t("landing.pricing.campaign.f3"),
        t("landing.pricing.campaign.f4"),
      ],
      cta: t("landing.pricing.campaign.cta"),
    },
    {
      id: "agency",
      name: t("landing.pricing.agency.name"),
      price: "499+",
      unit: "TND",
      blurb: t("landing.pricing.agency.blurb"),
      features: [
        t("landing.pricing.agency.f1"),
        t("landing.pricing.agency.f2"),
        t("landing.pricing.agency.f3"),
        t("landing.pricing.agency.f4"),
      ],
      cta: t("landing.pricing.agency.cta"),
    },
  ];
}

/* ------------------------------------------------------------------ */
/*  Icons                                                              */
/* ------------------------------------------------------------------ */

function svgProps(className?: string) {
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

export function IconCheck({ className }: { className?: string }) {
  return (
    <svg {...svgProps(className)}>
      <path d="m4.5 12.5 5 5 10-11" />
    </svg>
  );
}

export function IconArrowRight({ className }: { className?: string }) {
  return (
    <svg {...svgProps(className)}>
      <path d="M4 12h16" />
      <path d="m13 5 7 7-7 7" />
    </svg>
  );
}

function IconArrowDown({ className }: { className?: string }) {
  return (
    <svg {...svgProps(className)}>
      <path d="M12 4v16" />
      <path d="m5 13 7 7 7-7" />
    </svg>
  );
}

export function IconLock({ className }: { className?: string }) {
  return (
    <svg {...svgProps(className)}>
      <rect x="5" y="10.5" width="14" height="10" rx="2.5" />
      <path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" />
    </svg>
  );
}

export function IconUnlock({ className }: { className?: string }) {
  return (
    <svg {...svgProps(className)}>
      <rect x="5" y="10.5" width="14" height="10" rx="2.5" />
      <path d="M8 10.5V8a4 4 0 0 1 7.5-2" />
    </svg>
  );
}

function IconSend({ className }: { className?: string }) {
  return (
    <svg {...svgProps(className)}>
      <path d="M21 3 10.5 13.5" />
      <path d="M21 3 14 21l-3.5-7.5L3 10l18-7Z" />
    </svg>
  );
}

export function IconMail({ className }: { className?: string }) {
  return (
    <svg {...svgProps(className)}>
      <rect x="3" y="5.5" width="18" height="13" rx="2.5" />
      <path d="m3.5 7 8.5 6 8.5-6" />
    </svg>
  );
}

function IconPlus({ className }: { className?: string }) {
  return (
    <svg {...svgProps(className)}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

function IconChevronDown({ className }: { className?: string }) {
  return (
    <svg {...svgProps(className)}>
      <path d="m5 9 7 7 7-7" />
    </svg>
  );
}

export function IconMic({ className }: { className?: string }) {
  return (
    <svg {...svgProps(className)}>
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0" />
      <path d="M12 18v3" />
    </svg>
  );
}

function IconUsers({ className }: { className?: string }) {
  return (
    <svg {...svgProps(className)}>
      <circle cx="9" cy="8.5" r="3.2" />
      <path d="M3.5 20c.6-3.2 2.8-5 5.5-5s4.9 1.8 5.5 5" />
      <path d="M15.5 5.6a3.2 3.2 0 0 1 0 5.8" />
      <path d="M17.8 15.4c1.5.8 2.5 2.4 2.8 4.6" />
    </svg>
  );
}

export function IconBriefcase({ className }: { className?: string }) {
  return (
    <svg {...svgProps(className)}>
      <rect x="3.5" y="7.5" width="17" height="12" rx="2.5" />
      <path d="M9 7.5V6a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v1.5" />
      <path d="M3.5 12.5h17" />
    </svg>
  );
}

function IconFile({ className }: { className?: string }) {
  return (
    <svg {...svgProps(className)}>
      <path d="M7 3h7l4 4v14H7V3Z" />
      <path d="M14 3v4h4" />
    </svg>
  );
}

export function IconSpark({ className }: { className?: string }) {
  return (
    <svg {...svgProps(className)}>
      <path d="M12 3c.6 4.8 2.4 6.6 7.2 7.2-4.8.6-6.6 2.4-7.2 7.2-.6-4.8-2.4-6.6-7.2-7.2C9.6 9.6 11.4 7.8 12 3Z" />
    </svg>
  );
}

export function LogoMark({ className }: { className?: string }) {
  const [failed, setFailed] = useState(false);
  return (
    <span
      className={cn(
        "relative inline-grid place-items-center rounded-xl bg-gradient-to-br from-primary-500 via-primary-600 to-indigo-600 text-white shadow-lg shadow-primary-600/30",
        className
      )}
    >
      {failed ? (
        <svg viewBox="0 0 32 32" fill="none" className="h-[62%] w-[62%]" aria-hidden>
          <path
            d="M10 10.5 16 21.5 22 10.5"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle cx="10" cy="10.5" r="2.4" fill="currentColor" />
          <circle cx="22" cy="10.5" r="2.4" fill="currentColor" opacity="0.75" />
          <circle cx="16" cy="21.5" r="2.9" fill="currentColor" />
        </svg>
      ) : (
        <img
          src="/candway_logo.png"
          alt="Candway"
          loading="lazy"
          onError={() => setFailed(true)}
          className="h-full w-full object-contain p-0.5"
        />
      )}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  Motion                                                             */
/* ------------------------------------------------------------------ */

function usePrefersReducedMotion(): boolean {
  const [reduced] = useState(
    () =>
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
  return reduced;
}

function useReveal<T extends HTMLElement>(threshold = 0.14) {
  const ref = useRef<T | null>(null);
  const [visible, setVisible] = useState(false);
  const reduced = usePrefersReducedMotion();

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (reduced || typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setVisible(true);
          io.disconnect();
        }
      },
      { threshold, rootMargin: "0px 0px -8% 0px" }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [reduced, threshold]);

  return { ref, visible };
}

export function Reveal({
  children,
  className,
  delay = 0,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  const { ref, visible } = useReveal<HTMLDivElement>();
  return (
    <div
      ref={ref}
      style={{ transitionDelay: `${delay}ms` }}
      className={cn(
        "transition-all duration-700 ease-out",
        visible ? "translate-y-0 opacity-100" : "translate-y-7 opacity-0",
        className
      )}
    >
      {children}
    </div>
  );
}

function useCountUp(target: number, active: boolean, duration = 1200) {
  const [value, setValue] = useState(0);
  const reduced = usePrefersReducedMotion();

  useEffect(() => {
    if (!active) return;
    if (reduced) {
      setValue(target);
      return;
    }
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / duration);
      setValue(Math.round(target * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [active, target, duration, reduced]);

  return value;
}

/* ------------------------------------------------------------------ */
/*  Shared                                                             */
/* ------------------------------------------------------------------ */

const btnPrimary =
  "cw-shine inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-primary-600/30 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-xl hover:shadow-primary-600/35 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600";

const btnGhost =
  "inline-flex items-center justify-center gap-2 rounded-xl border border-ink/10 bg-white/75 px-5 py-3 text-sm font-semibold text-ink shadow-sm backdrop-blur transition-all duration-300 hover:-translate-y-0.5 hover:border-primary-300 hover:text-primary-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600";

function Overline({ children }: { children: ReactNode }) {
  return (
    <p className="flex items-center gap-2.5 text-[13px] font-semibold tracking-[0.14em] uppercase text-primary-700">
      <span className="h-px w-6 bg-gradient-to-r from-primary-500 to-primary-300" />
      {children}
    </p>
  );
}

function SectionHead({
  overline,
  title,
  sub,
}: {
  overline: string;
  title: ReactNode;
  sub?: string;
}) {
  return (
    <Reveal className="mx-auto mb-12 flex max-w-2xl flex-col items-center gap-4 text-center md:mb-16">
      <Overline>{overline}</Overline>
      <h2 className="text-3xl font-semibold leading-[1.12] tracking-tight text-ink md:text-[2.55rem]">
        {title}
      </h2>
      {sub ? (
        <p className="text-base leading-relaxed text-ink-soft">{sub}</p>
      ) : null}
    </Reveal>
  );
}

function Chrome({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-between border-b border-ink/8 px-4 py-3">
      <span className="flex gap-1.5" aria-hidden>
        <span className="h-2 w-2 rounded-full bg-ink/12" />
        <span className="h-2 w-2 rounded-full bg-ink/12" />
        <span className="h-2 w-2 rounded-full bg-ink/12" />
      </span>
      <span className="rounded-full bg-ink/4 px-2.5 py-1 text-[10px] font-semibold tracking-wide text-ink-faint">
        {label}
      </span>
    </div>
  );
}

function Avatar({
  photo,
  initials,
  gradient,
  className,
}: {
  photo: string;
  initials: string;
  gradient: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "relative shrink-0 overflow-hidden rounded-full bg-gradient-to-br ring-1 ring-ink/8",
        gradient,
        className
      )}
    >
      <span
        className="absolute inset-0 grid place-items-center text-[10px] font-bold text-white"
        aria-hidden
      >
        {initials}
      </span>
      <img
        src={photo}
        alt=""
        loading="lazy"
        decoding="async"
        className="relative h-full w-full object-cover"
      />
    </span>
  );
}

function MatchBar({ value, good }: { value: number; good?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-lilac-200">
        <div
          className={cn(
            "h-full rounded-full",
            good
              ? "bg-gradient-to-r from-primary-500 to-emerald-400"
              : "bg-gradient-to-r from-primary-500 to-primary-400"
          )}
          style={{ width: `${value}%` }}
        />
      </div>
      <span
        className={cn(
          "w-9 shrink-0 text-right text-xs font-semibold",
          good ? "text-emerald-600" : "text-primary-700"
        )}
      >
        {value}%
      </span>
    </div>
  );
}

const TONE = {
  go: "bg-primary-600 text-white",
  wait: "border border-ink/12 bg-white text-ink-soft",
  done: "bg-emerald-500/12 text-emerald-700 border border-emerald-500/20",
  lock: "border border-ink/10 bg-ink/4 text-ink-faint",
} as const;

/* ------------------------------------------------------------------ */
/*  Nav                                                                */
/* ------------------------------------------------------------------ */

function MobileMenu({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useLanguage();
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Menu"
      className="fixed inset-0 z-[70] overflow-y-auto bg-[linear-gradient(170deg,rgba(26,17,54,0.99)_0%,rgba(43,26,90,0.98)_45%,rgba(66,40,138,0.97)_100%)] lg:hidden"
    >
      <div
        className="cw-drift pointer-events-none absolute -top-40 left-1/2 h-96 w-[620px] -translate-x-1/2 rounded-full bg-primary-500/40 blur-3xl"
        aria-hidden
      />
      <div
        className="cw-dots pointer-events-none absolute inset-0 opacity-20 invert [mask-image:radial-gradient(75%_40%_at_50%_0%,black,transparent)]"
        aria-hidden
      />
      <DotHalo className="pointer-events-none absolute -right-24 bottom-8 h-80 w-80 text-primary-300/25" />
      <DotCluster className="pointer-events-none absolute right-6 top-24 h-10 w-10 text-white/25" />
      <DotCluster className="pointer-events-none absolute left-6 bottom-24 h-9 w-9 text-white/25" />

      <div className="relative flex min-h-full flex-col px-6 pb-10 pt-6">
        <div className="flex items-center justify-between">
          <a href="#top" onClick={onClose} className="flex items-center gap-2.5">
            <LogoMark className="h-9 w-9" />
            <span className="text-[17px] font-semibold tracking-tight text-white">
              Candway
            </span>
            <span className="rounded-full border border-white/20 bg-white/10 px-2 py-0.5 text-[10px] font-bold tracking-wide text-primary-200">
              BETA
            </span>
          </a>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("landing.mobile.closeMenu")}
            className="grid h-10 w-10 place-items-center rounded-xl border border-white/20 bg-white/10 text-white transition-colors hover:bg-white/20"
          >
            <IconPlus className="h-4 w-4 rotate-45" />
          </button>
        </div>

        <nav aria-label="Mobile" className="mt-8 flex flex-col sm:mt-12">
          {navLinks(t).map((l, i) => {
            const isPage = l.href.startsWith("/");
            const navCls =
              "cw-fade-in group flex items-center gap-4 border-b border-white/10 py-4 sm:py-5";
            const navStyle = { animationDelay: `${80 + i * 70}ms` };
            const inner = (
              <>
                <span className="font-accent text-sm italic text-primary-300">
                  0{i + 1}
                </span>
                <span className="text-[1.65rem] font-semibold tracking-tight text-white/90 transition-all duration-300 group-hover:translate-x-1.5 group-hover:text-white sm:text-3xl">
                  {l.label}
                </span>
                <IconArrowRight className="ml-auto h-5 w-5 -translate-x-2 text-primary-300 opacity-0 transition-all duration-300 group-hover:translate-x-0 group-hover:opacity-100" />
              </>
            );
            return isPage ? (
              <Link
                key={l.href}
                to={l.href}
                onClick={onClose}
                className={navCls}
                style={navStyle}
              >
                {inner}
              </Link>
            ) : (
              <a
                key={l.href}
                href={l.href}
                onClick={onClose}
                className={navCls}
                style={navStyle}
              >
                {inner}
              </a>
            );
          })}
        </nav>

        <div className="cw-fade-in mt-auto pt-12" style={{ animationDelay: "450ms" }}>
          <div className="flex items-center justify-between gap-3">
            <Link
              to="/auth/login"
              onClick={onClose}
              className="flex-1 rounded-full border border-white/25 bg-white/10 px-4 py-2.5 text-center text-sm font-semibold text-white transition-colors hover:bg-white/20"
            >
              Sign in
            </Link>
            <Link
              to="/auth/register"
              onClick={onClose}
              className="flex-1 rounded-full bg-gradient-to-br from-primary-500 to-primary-700 px-4 py-2.5 text-center text-sm font-semibold text-white shadow-md shadow-primary-600/30"
            >
              Sign up
            </Link>
          </div>
          <a
            href={appAuthUrl("/auth/login")}
            onClick={onClose}
            className="mt-3 block text-center text-xs font-semibold text-primary-200 hover:text-white hover:underline"
          >
            For Employers &rarr;
          </a>
          <p className="mt-4 text-center text-xs font-medium text-white/50">
            {t("landing.mobile.trust")}
          </p>
        </div>
      </div>
    </div>
  );
}

function Nav() {
  const { t, language, setLanguage } = useLanguage();
  const [scrolled, setScrolled] = useState(false);
  const [active, setActive] = useState("");
  const [open, setOpen] = useState(false);
  const location = useLocation();

  const navLinks = [
    { label: "Home", href: "#top" },
    { label: t("landing.nav.howItWorks"), href: "#how" },
    { label: t("landing.nav.blogs"), href: "/blogs" },
    { label: t("landing.nav.careers"), href: "/careers" },
  ];

  useEffect(() => {
    const ids = ["top", "product", "how", "candidates", "pricing", "demo", "faq"];
    const onScroll = () => {
      setScrolled(window.scrollY > 12);
      let cur = "";
      for (const id of ids) {
        const el = document.getElementById(id);
        if (el && el.getBoundingClientRect().top - 160 <= 0) cur = id;
      }
      setActive(cur);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, []);

  return (
    <>
      <MobileMenu open={open} onClose={() => setOpen(false)} />

      <header className="fixed inset-x-0 top-0 z-50 px-3 sm:px-5">
        <div className="flex items-center justify-between gap-2 pt-3 sm:pt-4">
          {/* mobile — brand pill */}
          <a
            href="#top"
            className={cn(
              "flex items-center gap-2 rounded-full border py-1.5 pl-1.5 pr-3.5 backdrop-blur-xl transition-all duration-500 lg:hidden",
              scrolled
                ? "border-white/80 bg-white/85 shadow-[0_16px_44px_-18px_rgba(108,57,232,0.45),inset_0_1px_0_rgba(255,255,255,0.6)]"
                : "border-white/20 bg-white/12 shadow-[inset_0_1px_0_rgba(255,255,255,0.18)]"
            )}
          >
            <LogoMark className="h-8 w-8" />
            <span
              className={cn(
                "text-[16px] font-semibold tracking-tight transition-colors duration-500",
                scrolled ? "text-ink" : "text-white"
              )}
            >
              Candway
            </span>
          </a>

          {/* desktop — one centered glass pill: brand · links · CTA */}
          <div className="hidden flex-1 lg:block">
            <div
              className={cn(
                "mx-auto flex w-fit items-center rounded-full border px-2.5 backdrop-blur-xl transition-all duration-500",
                scrolled
                  ? "border-white/80 bg-white/85 py-1.5 shadow-[0_16px_44px_-18px_rgba(108,57,232,0.45),inset_0_1px_0_rgba(255,255,255,0.6)]"
                  : "border-white/20 bg-white/12 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.18)]"
              )}
            >
              <a href="#top" className="flex items-center gap-2.5 pl-1.5 pr-3.5">
                <LogoMark className="h-8 w-8" />
                <span
                  className={cn(
                    "text-[16px] font-semibold tracking-tight transition-colors duration-500",
                    scrolled ? "text-ink" : "text-white"
                  )}
                >
                  Candway
                </span>
                <span
                  className={cn(
                    "hidden rounded-full px-2 py-0.5 text-[10px] font-bold tracking-wide transition-colors duration-500 xl:inline-block",
                    scrolled
                      ? "bg-primary-500/12 text-primary-700"
                      : "bg-white/15 text-primary-200"
                  )}
                >
                  BETA
                </span>
              </a>

              <span
                className={cn("h-6 w-px", scrolled ? "bg-ink/10" : "bg-white/25")}
                aria-hidden
              />

              <nav aria-label="Main" className="flex items-center">
                {navLinks.map((l) => {
                  const isPage = l.href.startsWith("/");
                  const isActive = isPage
                    ? location.pathname === l.href
                    : active === l.href.slice(1);
                  const navCls = cn(
                    "rounded-full px-3.5 py-1.5 text-sm font-medium transition-all duration-300",
                    isActive
                      ? scrolled
                        ? "bg-ink text-white shadow-sm"
                        : "bg-white text-ink shadow-sm"
                      : scrolled
                        ? "text-ink-soft hover:bg-ink/5 hover:text-ink"
                        : "text-white/70 hover:bg-white/10 hover:text-white"
                  );
                  return isPage ? (
                    <Link key={l.href} to={l.href} className={navCls}>
                      {l.label}
                    </Link>
                  ) : (
                    <a key={l.href} href={l.href} className={navCls}>
                      {l.label}
                    </a>
                  );
                })}
              </nav>

              <span
                className={cn("mx-1 h-6 w-px", scrolled ? "bg-ink/10" : "bg-white/25")}
                aria-hidden
              />

              <div className="mx-1 flex items-center gap-1 rounded-full border border-white/20 bg-white/10 p-0.5 text-xs font-semibold backdrop-blur">
                <button
                  type="button"
                  onClick={() => setLanguage("en")}
                  className={cn(
                    "rounded-full px-2 py-0.5 transition-colors",
                    language === "en"
                      ? scrolled ? "bg-ink text-white" : "bg-white text-ink shadow-sm"
                      : scrolled ? "text-ink-soft hover:text-ink" : "text-white/70 hover:text-white"
                  )}
                >
                  EN
                </button>
                <button
                  type="button"
                  onClick={() => setLanguage("fr")}
                  className={cn(
                    "rounded-full px-2 py-0.5 transition-colors",
                    language === "fr"
                      ? scrolled ? "bg-ink text-white" : "bg-white text-ink shadow-sm"
                      : scrolled ? "text-ink-soft hover:text-ink" : "text-white/70 hover:text-white"
                  )}
                >
                  FR
                </button>
              </div>

              <div className="ml-1 flex items-center gap-1.5">
                <a
                  href={appAuthUrl("/auth/login")}
                  className="rounded-full px-3 py-1.5 text-xs font-semibold text-purple-400 hover:text-purple-300 hover:underline"
                >
                  For Employers
                </a>
                <Link
                  to="/auth/login"
                  className={cn(
                    "rounded-full px-3.5 py-1.5 text-sm font-medium transition-all duration-300",
                    scrolled
                      ? "text-ink-soft hover:bg-ink/5 hover:text-ink"
                      : "text-white/70 hover:bg-white/10 hover:text-white"
                  )}
                >
                  Sign in
                </Link>
                <Link
                  to="/auth/register"
                  className="cw-shine inline-flex items-center rounded-full bg-gradient-to-br from-primary-500 to-primary-700 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-primary-600/30 transition-transform duration-300 hover:-translate-y-0.5"
                >
                  Sign up
                </Link>
              </div>
            </div>
          </div>

          {/* mobile — CTA + burger */}
          <div className="flex items-center gap-2 lg:hidden">
            <button
              type="button"
              aria-label={open ? t("landing.mobile.closeMenu") : t("landing.mobile.openMenu")}
              aria-expanded={open}
              onClick={() => setOpen((o) => !o)}
              className={cn(
                "grid h-11 w-11 place-items-center rounded-full border backdrop-blur-xl transition-all duration-500",
                scrolled
                  ? "border-white/80 bg-white/85 shadow-[0_16px_44px_-18px_rgba(108,57,232,0.45),inset_0_1px_0_rgba(255,255,255,0.6)]"
                  : "border-white/20 bg-white/12 shadow-[inset_0_1px_0_rgba(255,255,255,0.18)]"
              )}
            >
              <span className="relative block h-3.5 w-5" aria-hidden>
                <span
                  className={cn(
                    "absolute left-0 top-0 h-[2px] w-full rounded-full transition-all duration-300",
                    scrolled ? "bg-ink" : "bg-white",
                    open && "top-1/2 -translate-y-1/2 rotate-45"
                  )}
                />
                <span
                  className={cn(
                    "absolute bottom-0 left-0 h-[2px] rounded-full transition-all duration-300",
                    scrolled ? "bg-ink" : "bg-white",
                    open ? "bottom-auto top-1/2 w-full -translate-y-1/2 -rotate-45" : "w-3/5"
                  )}
                />
              </span>
            </button>
          </div>
        </div>
      </header>
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  Product stage (hero + tour)                                        */
/* ------------------------------------------------------------------ */

function StageScore({
  selected,
  onSelect,
  live,
}: {
  selected: number;
  onSelect: (i: number) => void;
  live?: boolean;
}) {
  const { t } = useLanguage();
  const person = getCandidateRows(t)[selected] ?? getCandidateRows(t)[0];

  return (
    <div className="grid min-h-[420px] lg:grid-cols-[1fr_280px]">
      <div className="p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-ink-faint">
                {t("landing.stage.campaign")}
              </p>
              {live && (
                <span className="flex items-center gap-1 rounded-full bg-emerald-500/12 px-1.5 py-0.5 text-[9px] font-bold tracking-wide text-emerald-700">
                  <span className="cw-blink h-1 w-1 rounded-full bg-emerald-500" />
                  {t("landing.stage.live")}
                </span>
              )}
            </div>
            <h3 className="mt-0.5 text-base font-semibold tracking-tight text-ink">
              {t("landing.roles.marketingLead")}
            </h3>
          </div>
          <div className="flex gap-4 text-center">
            {[
              ["33", t("landing.stage.statApplied")],
              ["12", t("landing.stage.statScored")],
              ["7", t("landing.stage.statReady")],
            ].map(([n, l]) => (
              <div key={l}>
                <p className="text-lg font-semibold leading-none text-ink">{n}</p>
                <p className="mt-1 text-[10px] font-medium text-ink-faint">{l}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="relative mt-4 space-y-1 overflow-hidden">
          {live && (
            <span
              className="cw-scan-x pointer-events-none absolute inset-y-0 left-0 z-10 w-1/3 bg-gradient-to-r from-transparent via-primary-500/10 to-transparent"
              aria-hidden
            />
          )}
          {getCandidateRows(t).map((row, i) => (
            <button
              key={row.name}
              type="button"
              onClick={() => onSelect(i)}
              className={cn(
                "flex w-full items-center gap-3 rounded-xl px-2.5 py-2.5 text-left transition-colors",
                selected === i ? "bg-primary-500/8" : "hover:bg-ink/3"
              )}
            >
              <Avatar
                photo={row.photo}
                initials={row.initials}
                gradient={row.avatar}
                className="h-8 w-8"
              />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-semibold text-ink">
                  {row.name}
                </span>
                <span className="block truncate text-[11px] text-ink-faint">
                  {row.source}
                </span>
              </span>
              <span className="hidden w-24 sm:block">
                <MatchBar value={row.match} good={row.match >= 80} />
              </span>
              <span className="w-8 text-right text-[13px] font-semibold text-primary-700 sm:hidden">
                {row.match}%
              </span>
              <span
                className={cn(
                  "w-[72px] shrink-0 rounded-md py-1 text-center text-[10px] font-semibold",
                  TONE[row.tone]
                )}
              >
                {row.status}
              </span>
            </button>
          ))}
        </div>
      </div>

      <aside className="border-t border-ink/8 bg-lilac-50/70 p-5 lg:border-l lg:border-t-0">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-faint">
          {t("landing.stage.rubricEvidence")}
        </p>
        <p className="mt-1 text-sm font-semibold text-ink">{person.name}</p>
        <p className="text-xs text-ink-faint">{person.role} · {person.match}% {t("landing.stage.match")}</p>

        <ul className="mt-4 space-y-3">
          {getRubric(t).map((r) => (
            <li key={r.name}>
              <div className="flex items-center justify-between text-[12px] font-medium">
                <span className="text-ink">{r.name}</span>
                <span className="text-primary-700">{r.score}</span>
              </div>
              <div className="mt-1 h-1 overflow-hidden rounded-full bg-lilac-200">
                <div
                  className="h-full rounded-full bg-primary-500"
                  style={{ width: `${r.score}%` }}
                />
              </div>
              <p className="mt-1 text-[11px] text-ink-faint">{r.note}</p>
            </li>
          ))}
        </ul>

        <div
          className={cn(
            "mt-5 flex items-center gap-2 rounded-xl bg-primary-600 px-3 py-2.5 text-[12px] font-semibold text-white",
            live && "cw-pulse-soft"
          )}
        >
          <IconUnlock className="h-3.5 w-3.5" />
          {t("landing.stage.inviteCta")}
        </div>
      </aside>
    </div>
  );
}

function StageInvite() {
  const { t } = useLanguage();
  return (
    <div className="p-5 sm:p-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-faint">
            {t("landing.stage.inviteQueue")}
          </p>
          <h3 className="mt-0.5 text-base font-semibold text-ink">
            {t("landing.stage.unlockOneByOne")}
          </h3>
        </div>
        <span className="flex items-center gap-1.5 rounded-full bg-primary-500/10 px-3 py-1 text-[11px] font-semibold text-primary-700">
          <IconLock className="h-3 w-3" />
          {t("landing.stage.defaultLocked")}
        </span>
      </div>

      <div className="mt-5 space-y-2.5">
        {getCandidateRows(t).slice(0, 3).map((row, i) => (
          <div
            key={row.name}
            className="flex items-center gap-3 rounded-2xl border border-ink/8 bg-white/70 px-3.5 py-3"
          >
            <Avatar
              photo={row.photo}
              initials={row.initials}
              gradient={row.avatar}
              className="h-9 w-9"
            />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-ink">{row.name}</p>
              <p className="text-xs text-ink-faint">{row.match}% {t("landing.stage.cvMatchLabel")}</p>
            </div>
            {i === 0 ? (
              <span className="rounded-lg bg-emerald-500/12 px-3 py-1.5 text-[11px] font-semibold text-emerald-700">
                {t("landing.stage.inviteSent")}
              </span>
            ) : (
              <span className="rounded-lg bg-primary-600 px-3 py-1.5 text-[11px] font-semibold text-white">
                {t("landing.stage.sendInvite")}
              </span>
            )}
          </div>
        ))}
      </div>

      <p className="mt-4 flex items-start gap-2 text-[12px] leading-relaxed text-ink-soft">
        <IconLock className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary-600" />
        {t("landing.stage.lockedNote")}
      </p>
    </div>
  );
}

function StageInterview() {
  const { t } = useLanguage();
  return (
    <div className="grid min-h-[400px] lg:grid-cols-2">
      <div className="border-b border-ink/8 p-5 lg:border-b-0 lg:border-r">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-faint">
          {t("landing.stage.aiInterviewInvited")}
        </p>
        <p className="mt-1 text-sm font-semibold text-ink">{getCandidateRows(t)[0].name} · {getCandidateRows(t)[0].role}</p>
        <div className="mt-4 space-y-3">
          {[
            ["Candway", t("landing.stage.q1")],
            ["Firas", t("landing.stage.a1")],
          ].map(([who, text]) => (
            <div
              key={who}
              className={cn(
                "rounded-2xl px-3.5 py-3 text-[13px] leading-relaxed",
                who === "Candway"
                  ? "bg-primary-500/8 text-ink-soft"
                  : "bg-white text-ink shadow-sm"
              )}
            >
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-primary-700">
                {who}
              </p>
              {text}
            </div>
          ))}
        </div>
      </div>
      <div className="bg-lilac-50/70 p-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-faint">
          {t("landing.stage.mappedToRubric")}
        </p>
        <ul className="mt-4 space-y-3">
          {[
            [t("landing.stage.m1_k"), t("landing.stage.m1_v")],
            [t("landing.stage.m2_k"), t("landing.stage.m2_v")],
            [t("landing.stage.m3_k"), t("landing.stage.m3_v")],
          ].map(([k, v]) => (
            <li key={k} className="flex gap-3">
              <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-emerald-500 text-white">
                <IconCheck className="h-3 w-3" />
              </span>
              <div>
                <p className="text-[13px] font-semibold text-ink">{k}</p>
                <p className="text-[12px] text-ink-soft">{v}</p>
              </div>
            </li>
          ))}
        </ul>
        <p className="mt-6 text-[12px] text-ink-faint">
          {t("landing.stage.interviewNote")}
        </p>
      </div>
    </div>
  );
}

function StagePortal() {
  const { t } = useLanguage();
  const steps = getCandidateSteps(t);
  return (
    <div className="p-5 sm:p-6">
      <div className="flex items-center gap-3">
        <Avatar
          photo={leaPhoto}
          initials="LB"
          gradient="from-fuchsia-500 to-primary-500"
          className="h-10 w-10"
        />
        <div>
          <p className="text-sm font-semibold text-ink">{t("landing.stage.candidatePortal")}</p>
          <p className="text-xs text-ink-faint">{t("landing.stage.leaSub")}</p>
        </div>
      </div>

      <div className="mt-5 rounded-2xl border border-ink/8 bg-white/75 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-primary-500/10 text-primary-700">
              <IconBriefcase className="h-4.5 w-4.5" />
            </span>
            <div>
              <p className="text-sm font-semibold text-ink">{t("landing.roles.marketingLead")}</p>
              <p className="text-xs text-ink-faint">{t("landing.stage.publicRoleRemote")}</p>
            </div>
          </div>
          <span className="rounded-full bg-emerald-500/12 px-2.5 py-1 text-[11px] font-semibold text-emerald-700">
            {t("landing.steps.applied")}
          </span>
        </div>

        <ol className="mt-5">
          {steps.map((s, i) => (
            <li key={s.label} className="relative flex gap-3 pb-3.5 last:pb-0">
              {i < steps.length - 1 && (
                <span className="absolute left-[11px] top-6 h-[calc(100%-12px)] w-px bg-ink/10" />
              )}
              <span
                className={cn(
                  "relative z-10 grid h-6 w-6 shrink-0 place-items-center rounded-full",
                  s.state === "done"
                    ? "bg-emerald-500 text-white"
                    : "border-2 border-primary-500 bg-white"
                )}
              >
                {s.state === "done" ? (
                  <IconCheck className="h-3 w-3" />
                ) : (
                  <span className="cw-blink h-1.5 w-1.5 rounded-full bg-primary-500" />
                )}
              </span>
              <div className="flex flex-1 items-center justify-between gap-2">
                <div>
                  <p className="text-[13px] font-semibold text-ink">{s.label}</p>
                  <p className="text-[11px] text-ink-faint">{s.sub}</p>
                </div>
                {s.state === "active" && (
                  <span className="rounded-full bg-primary-500/10 px-2 py-0.5 text-[10px] font-semibold text-primary-700">
                    {t("landing.stage.yourTurn")}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}

function StageReport() {
  const { t } = useLanguage();
  const advance = t("landing.stage.decisionAdvance");
  return (
    <div className="p-5 sm:p-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-faint">
            {t("landing.stage.recruiterReport")}
          </p>
          <h3 className="mt-0.5 text-base font-semibold text-ink">
            {t("landing.stage.shortlistTitle")}
          </h3>
        </div>
        <span className="rounded-full bg-emerald-500/12 px-3 py-1 text-[11px] font-semibold text-emerald-700">
          {t("landing.stage.readyToSend")}
        </span>
      </div>

      <div className="mt-5 overflow-hidden rounded-2xl border border-ink/8">
        <div className="grid grid-cols-[1fr_70px_90px] bg-lilac-50/80 px-4 py-2 text-[10px] font-semibold uppercase tracking-wide text-ink-faint">
          <span>{t("landing.stage.colCandidate")}</span>
          <span>{t("landing.stage.colMatch")}</span>
          <span>{t("landing.stage.colDecision")}</span>
        </div>
        {[
          ["Firas Ray", "82%", t("landing.stage.decisionAdvance")],
          ["Sami Kallel", "79%", t("landing.stage.decisionAdvance")],
          ["Rayen Heni", "77%", t("landing.stage.decisionHold")],
        ].map(([n, m, d]) => (
          <div
            key={n}
            className="grid grid-cols-[1fr_70px_90px] items-center border-t border-ink/6 px-4 py-3 text-[13px]"
          >
            <span className="font-semibold text-ink">{n}</span>
            <span className="font-semibold text-primary-700">{m}</span>
            <span
              className={cn(
                "text-[11px] font-semibold",
                d === advance ? "text-emerald-700" : "text-ink-faint"
              )}
            >
              {d}
            </span>
          </div>
        ))}
      </div>
      <p className="mt-4 text-[12px] text-ink-soft">
        {t("landing.stage.reportNote")}
      </p>
    </div>
  );
}

function ProductFrame({
  label,
  children,
  className,
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("cw-stage overflow-hidden rounded-[1.6rem]", className)}>
      <Chrome label={label} />
      {children}
    </div>
  );
}

function HeroStage() {
  const { t } = useLanguage();
  const [selected, setSelected] = useState(0);
  const reduced = usePrefersReducedMotion();
  const rowCount = getCandidateRows(t).length;

  useEffect(() => {
    if (reduced) return;
    const id = window.setInterval(() => {
      setSelected((s) => (s + 1) % rowCount);
    }, 2800);
    return () => window.clearInterval(id);
  }, [reduced, rowCount]);

  return (
    <ProductFrame label={t("landing.frame.campaign")}>
      <StageScore selected={selected} onSelect={setSelected} live />
    </ProductFrame>
  );
}

/* ------------------------------------------------------------------ */
/*  Hero                                                               */
/* ------------------------------------------------------------------ */

function MiniRing() {
  const C = 2 * Math.PI * 10;
  return (
    <svg viewBox="0 0 24 24" className="h-7 w-7 shrink-0 -rotate-90" aria-hidden>
      <circle cx="12" cy="12" r="10" stroke="#e4dbff" strokeWidth="3.5" fill="none" />
      <circle
        cx="12"
        cy="12"
        r="10"
        stroke="#7c4dff"
        strokeWidth="3.5"
        strokeLinecap="round"
        fill="none"
        strokeDasharray={C}
        strokeDashoffset={C * 0.18}
      />
    </svg>
  );
}

function Hero() {
  const { t } = useLanguage();
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    const tTimer = window.setTimeout(() => setMounted(true), 40);
    return () => window.clearTimeout(tTimer);
  }, []);

  return (
    <section id="top" className="relative">
      <div className="relative overflow-hidden bg-[linear-gradient(168deg,rgba(26,17,54,0.97)_0%,rgba(43,26,90,0.95)_45%,rgba(66,40,138,0.93)_100%)] shadow-[0_60px_140px_-50px_rgba(50,25,120,0.55)] backdrop-blur-2xl">
        <div
          className="cw-drift pointer-events-none absolute -top-40 left-1/2 -z-10 h-96 w-[620px] -translate-x-1/2 rounded-full bg-primary-500/40 blur-3xl"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute -right-28 top-1/3 -z-10 h-80 w-80 rounded-full bg-sky-400/25 blur-3xl"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute -bottom-32 -left-24 -z-10 h-72 w-72 rounded-full bg-fuchsia-500/25 blur-3xl"
          aria-hidden
        />
        <div
          className="cw-dots pointer-events-none absolute inset-0 -z-10 opacity-25 invert [mask-image:radial-gradient(75%_50%_at_50%_0%,black,transparent)]"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute inset-x-16 top-0 h-px bg-gradient-to-r from-transparent via-white/40 to-transparent"
          aria-hidden
        />

        <div className="relative mx-auto max-w-6xl px-5 pb-16 pt-28 sm:px-8 sm:pb-20 sm:pt-32">
          <div className="relative mx-auto max-w-3xl text-center">
          <span
            className={cn(
              "inline-flex items-center gap-2 rounded-full border border-white/25 bg-white/10 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm backdrop-blur transition-all duration-700",
              mounted ? "translate-y-0 opacity-100" : "translate-y-3 opacity-0"
            )}
          >
            <span className="cw-blink h-1.5 w-1.5 rounded-full bg-emerald-500" />
            {t("landing.hero.eyebrow")}
          </span>

          <h1 className="mt-6 text-[2.55rem] font-semibold leading-[1.02] tracking-[-0.03em] text-white sm:text-6xl lg:text-[4.15rem]">
            <span className="block overflow-hidden pb-1">
              <span
                className={cn(
                  "block transition-transform duration-1000 ease-[cubic-bezier(0.22,1,0.36,1)]",
                  mounted ? "translate-y-0" : "translate-y-[110%]"
                )}
              >
                {t("landing.hero.titleLine1")}
              </span>
            </span>
            <span className="block overflow-hidden">
              <span
                className={cn(
                  "block font-accent font-medium italic text-primary-300 transition-transform duration-1000 ease-[cubic-bezier(0.22,1,0.36,1)] delay-150",
                  mounted ? "translate-y-0" : "translate-y-[110%]"
                )}
              >
                {t("landing.hero.titleLine2")}
              </span>
            </span>
          </h1>

          <p
            className={cn(
              "mx-auto mt-6 max-w-xl text-base leading-relaxed text-white/70 transition-all delay-300 duration-700 sm:text-lg",
              mounted ? "translate-y-0 opacity-100" : "translate-y-3 opacity-0"
            )}
          >
            {t("landing.hero.subtitleText")}
          </p>

          <div
            className={cn(
              "mt-8 flex flex-col items-center justify-center gap-3 transition-all delay-500 duration-700 sm:flex-row",
              mounted ? "translate-y-0 opacity-100" : "translate-y-3 opacity-0"
            )}
          >
            <a href="#demo" className={btnPrimary}>
              {t("landing.hero.btnPrimary")}
              <IconArrowRight className="h-4 w-4" />
            </a>
            <a
              href="#how"
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/25 bg-white/10 px-5 py-3 text-sm font-semibold text-white backdrop-blur transition-all duration-300 hover:-translate-y-0.5 hover:border-white/40 hover:bg-white/15 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-300"
            >
              {t("landing.hero.btnSecondary")}
              <IconArrowDown className="h-4 w-4" />
            </a>
          </div>

          <p
            className={cn(
              "mx-auto mt-6 inline-flex items-center gap-2 rounded-full border border-white/25 bg-white/10 px-4 py-2 text-[13px] font-semibold text-white shadow-sm backdrop-blur transition-all delay-700 duration-700",
              mounted ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0"
            )}
          >
            <IconLock className="h-3.5 w-3.5 shrink-0 text-primary-300" />
            {t("landing.hero.trustNote")}
          </p>
        </div>

          <div
            className={cn(
              "relative mx-auto mt-12 max-w-4xl transition-all delay-200 duration-1000 sm:mt-14",
              mounted ? "translate-y-0 opacity-100" : "translate-y-8 opacity-0"
            )}
          >
          <div
            className="pointer-events-none absolute -inset-8 -z-10 rounded-[2.5rem] opacity-80 blur-3xl"
            style={{
              background:
                "radial-gradient(60% 80% at 50% 40%, rgba(157,114,255,0.35), transparent 70%)",
            }}
            aria-hidden
          />
          <DotHalo className="pointer-events-none absolute -right-28 -top-24 -z-10 h-80 w-80 text-primary-300/40" />
          <DotHalo className="pointer-events-none absolute -bottom-28 -left-24 -z-10 h-72 w-72 text-sky-300/40" />
          <DotCluster className="pointer-events-none absolute -left-10 bottom-16 z-10 hidden h-11 w-11 text-primary-200/70 lg:block" />
          <DotCluster className="pointer-events-none absolute -right-12 top-24 z-10 hidden h-9 w-9 text-sky-200/60 lg:block" />

          <div
            className="cw-float absolute -left-5 -top-7 z-10 hidden items-center gap-2.5 rounded-2xl border border-white/80 bg-white/90 px-3.5 py-2.5 shadow-[0_18px_44px_-16px_rgba(108,57,232,0.5)] backdrop-blur md:flex"
            style={{ animationDuration: "7s" }}
          >
            <Avatar
              photo={firasPhoto}
              initials="FR"
              gradient="from-violet-500 to-fuchsia-400"
              className="h-8 w-8"
            />
            <MiniRing />
            <span className="text-left">
              <span className="block text-[12px] font-bold leading-none text-ink">
                {t("landing.hero.floatCvMatch")}
              </span>
              <span className="mt-1 block text-[10px] font-medium text-ink-faint">
                {t("landing.outcomes.c1_label")}
              </span>
            </span>
          </div>

          <div
            className="cw-float absolute -right-5 top-8 z-10 hidden items-center gap-2 rounded-2xl border border-white/80 bg-white/90 px-3.5 py-2.5 shadow-[0_18px_44px_-16px_rgba(108,57,232,0.5)] backdrop-blur lg:flex"
            style={{ animationDuration: "8.5s", animationDelay: "0.8s" }}
          >
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-sky-500/12 text-sky-600">
              <IconLock className="h-3.5 w-3.5" />
            </span>
            <span className="text-[12px] font-bold leading-none text-ink">
              {t("landing.hero.floatLocked")}
            </span>
          </div>

          <div
            className="cw-float absolute -bottom-6 -right-4 z-10 hidden items-center gap-2.5 rounded-2xl border border-white/80 bg-white/90 px-3.5 py-2.5 shadow-[0_18px_44px_-16px_rgba(16,120,80,0.4)] backdrop-blur md:flex"
            style={{ animationDuration: "7.6s", animationDelay: "1.5s" }}
          >
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-emerald-500/15 text-emerald-600">
              <IconCheck className="h-3.5 w-3.5" />
            </span>
            <span className="text-left">
              <span className="block text-[12px] font-bold leading-none text-ink">
                {t("landing.outcomes.c3_hint")}
              </span>
              <span className="mt-1 block text-[10px] font-medium text-ink-faint">
                {t("landing.hero.floatQualified")}
              </span>
            </span>
          </div>

          <HeroStage />
        </div>
        </div>
      </div>

      <div className="cw-fade-x relative mt-16 border-y border-ink/6 py-4">
        <div className="cw-marquee flex w-max gap-10 pr-10 text-[13px] font-medium text-ink-faint">
          {[...stripItems(t), ...stripItems(t)].map((item, i) => (
            <span key={`${item}-${i}`} className="flex items-center gap-10">
              {item}
              <span className="h-1 w-1 rounded-full bg-primary-400/70" />
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Proof                                                              */
/* ------------------------------------------------------------------ */

function Proof() {
  const { t } = useLanguage();
  const personas = [
    {
      Icon: IconBriefcase,
      k: t("landing.proof.p1_k"),
      body: t("landing.proof.p1_b"),
    },
    {
      Icon: IconUsers,
      k: t("landing.proof.p2_k"),
      body: t("landing.proof.p2_b"),
    },
    {
      Icon: IconSpark,
      k: t("landing.proof.p3_k"),
      body: t("landing.proof.p3_b"),
    },
  ];

  return (
    <section className="relative overflow-hidden border-b border-ink/5 py-14 md:py-16">
      <DotCluster className="pointer-events-none absolute -top-1 left-8 h-10 w-10 text-primary-400/40" />
      <DotCluster className="pointer-events-none absolute bottom-4 right-8 h-10 w-10 text-primary-400/40" />
      <DotHalo className="pointer-events-none absolute -right-28 top-1/2 h-72 w-72 -translate-y-1/2 text-primary-400/15" />
      <div className="mx-auto max-w-6xl px-5 sm:px-8">
        <Reveal className="text-center">
          <p className="mx-auto max-w-3xl font-accent text-xl italic leading-snug text-primary-700 sm:text-2xl">
            {t("landing.proof.quote")}
          </p>
          <p className="mt-3 text-sm text-ink-soft">
            {t("landing.proof.sub")}
          </p>
        </Reveal>
        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          {personas.map(({ Icon, k, body }, i) => (
            <Reveal key={k} delay={i * 80}>
              <div className="cw-glass flex h-full items-start gap-3.5 rounded-2xl p-5">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-primary-500 to-indigo-500 text-white shadow-md shadow-primary-500/25">
                  <Icon className="h-5 w-5" />
                </span>
                <div>
                  <p className="text-sm font-semibold text-ink">{k}</p>
                  <p className="mt-1 text-[13px] leading-relaxed text-ink-soft">{body}</p>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Problem + outcome                                                  */
/* ------------------------------------------------------------------ */

function Problem() {
  const { t } = useLanguage();
  const pain = [
    { title: t("landing.pain.p1_title"), body: t("landing.pain.p1_body") },
    { title: t("landing.pain.p2_title"), body: t("landing.pain.p2_body") },
    { title: t("landing.pain.p3_title"), body: t("landing.pain.p3_body") },
  ];
  const outcomes = [
    { value: "100+", label: t("landing.outcomes.c1_label"), hint: t("landing.outcomes.c1_hint") },
    { value: "1", label: t("landing.outcomes.c2_label"), hint: t("landing.outcomes.c2_hint") },
    { value: "5", label: t("landing.outcomes.c3_label"), hint: t("landing.outcomes.c3_hint") },
  ];

  return (
    <section className="py-20 md:py-28">
      <div className="mx-auto max-w-6xl px-5 sm:px-8">
        <SectionHead
          overline={t("landing.pain.eyebrow")}
          title={
            <>
              {t("landing.pain.title")}
            </>
          }
        />

        <div className="grid gap-4 md:grid-cols-3">
          {pain.map((p, i) => (
            <Reveal key={p.title} delay={i * 90}>
              <article className="cw-glass cw-lift h-full rounded-3xl p-6">
                <p className="text-xs font-semibold text-primary-600">0{i + 1}</p>
                <h3 className="mt-2 text-lg font-semibold tracking-tight text-ink">
                  {p.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-ink-soft">{p.body}</p>
              </article>
            </Reveal>
          ))}
        </div>

        <Reveal>
          <div className="relative mt-6 grid items-center gap-3 overflow-hidden rounded-[1.6rem] bg-gradient-to-br from-primary-600 via-[#6d45ea] to-indigo-600 p-6 text-white shadow-[0_30px_70px_-28px_rgba(108,57,232,0.55)] sm:grid-cols-[1fr_auto_1fr_auto_1fr] sm:p-8">
            <div className="cw-dots pointer-events-none absolute inset-0 opacity-20 invert" aria-hidden />
            <div className="pointer-events-none absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-white/60 to-transparent" aria-hidden />
            {outcomes.map((o, i) => (
              <div key={o.label} className="contents">
                <div className="relative text-center sm:text-left">
                  <p className="font-accent text-5xl italic leading-none drop-shadow-sm">{o.value}</p>
                  <p className="mt-2 text-sm font-semibold">{o.label}</p>
                  <p className="mt-1 text-xs text-white/70">{o.hint}</p>
                </div>
                {i < outcomes.length - 1 && (
                  <span className="hidden h-10 w-px bg-white/20 sm:block" />
                )}
              </div>
            ))}
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Product tour                                                       */
/* ------------------------------------------------------------------ */

function TourCanvas({ id }: { id: TourId }) {
  const [selected, setSelected] = useState(0);
  if (id === "score") return <StageScore selected={selected} onSelect={setSelected} />;
  if (id === "invite") return <StageInvite />;
  if (id === "interview") return <StageInterview />;
  if (id === "portal") return <StagePortal />;
  return <StageReport />;
}

function ProductTour() {
  const { t } = useLanguage();
  const tour = [
    { id: "score" as const, step: "01", title: t("landing.tour.s1_title"), body: t("landing.tour.s1_body") },
    { id: "invite" as const, step: "02", title: t("landing.tour.s2_title"), body: t("landing.tour.s2_body") },
    { id: "interview" as const, step: "03", title: t("landing.tour.s3_title"), body: t("landing.tour.s3_body") },
    { id: "portal" as const, step: "04", title: t("landing.tour.s4_title"), body: t("landing.tour.s4_body") },
    { id: "report" as const, step: "05", title: t("landing.tour.s5_title"), body: t("landing.tour.s5_body") },
  ];
  const [active, setActive] = useState<TourId>("score");
  const [auto, setAuto] = useState(true);
  const [inView, setInView] = useState(false);
  const secRef = useRef<HTMLDivElement | null>(null);
  const reduced = usePrefersReducedMotion();
  const current = tour.find((item) => item.id === active) ?? tour[0];

  useEffect(() => {
    const el = secRef.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }
    const io = new IntersectionObserver(([e]) => setInView(!!e?.isIntersecting), {
      threshold: 0.2,
    });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    if (!auto || !inView || reduced) return;
    const id = window.setInterval(() => {
      setActive((prev) => {
        const i = TOUR_IDS.indexOf(prev);
        return TOUR_IDS[(i + 1) % TOUR_IDS.length];
      });
    }, 4500);
    return () => window.clearInterval(id);
  }, [auto, inView, reduced]);

  const pick = (id: TourId) => {
    setActive(id);
    setAuto(false);
  };

  return (
    <section id="product" className="scroll-mt-28 py-20 md:py-28">
      <div ref={secRef} className="mx-auto max-w-6xl px-5 sm:px-8">
        <SectionHead
          overline={t("landing.nav.product")}
          title={
            <>
              {t("landing.product.title1")}{" "}
              <span className="font-accent font-medium italic text-primary-600">
                {t("landing.product.title2")}
              </span>
            </>
          }
          sub={t("landing.product.sub")}
        />

        <div className="flex items-center gap-3">
          <div className="flex flex-1 gap-2 overflow-x-auto pb-2 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {tour.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => pick(item.id)}
                className={cn(
                  "shrink-0 rounded-full px-4 py-2 text-sm font-semibold transition-all",
                  active === item.id
                    ? "bg-ink text-white shadow-md"
                    : "bg-white/70 text-ink-soft hover:bg-white hover:text-ink"
                )}
              >
                {item.step} {item.title.split(" ").slice(0, 2).join(" ")}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => setAuto((a) => !a)}
            className={cn(
              "hidden shrink-0 items-center gap-2 rounded-full border px-3.5 py-2 text-xs font-semibold transition-colors sm:inline-flex",
              auto
                ? "border-primary-300 bg-primary-500/10 text-primary-700"
                : "border-ink/12 bg-white text-ink-soft"
            )}
          >
            <span className={cn("h-1.5 w-1.5 rounded-full", auto ? "cw-blink bg-primary-500" : "bg-ink/30")} />
            {auto ? t("landing.product.autoOn") : t("landing.product.paused")}
          </button>
        </div>

        <div className="mt-8 grid items-start gap-8 lg:grid-cols-[0.9fr_1.2fr]">
          <Reveal>
            <p className="text-xs font-semibold text-primary-600">{current.step}</p>
            <h3 className="mt-2 text-2xl font-semibold tracking-tight text-ink md:text-[1.75rem]">
              {current.title}
            </h3>
            <p className="mt-3 text-[15px] leading-relaxed text-ink-soft">
              {current.body}
            </p>
            <ul className="mt-6 space-y-3">
              {tour.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => pick(item.id)}
                    className={cn(
                      "flex w-full items-start gap-3 rounded-xl px-3 py-2.5 text-left transition-colors",
                      active === item.id ? "bg-primary-500/8" : "hover:bg-ink/3"
                    )}
                  >
                    <span
                      className={cn(
                        "mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full text-[11px] font-bold",
                        active === item.id
                          ? "bg-primary-600 text-white"
                          : "bg-ink/6 text-ink-soft"
                      )}
                    >
                      {item.step}
                    </span>
                    <div>
                      <p className="text-sm font-semibold text-ink">{item.title}</p>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </Reveal>

          <Reveal delay={80}>
            <ProductFrame
              label={
                active === "portal"
                  ? t("landing.frame.candidate")
                  : active === "report"
                    ? t("landing.frame.report")
                    : t("landing.frame.campaign")
              }
            >
              <div key={active} className="cw-fade-in">
                <TourCanvas id={active} />
              </div>
            </ProductFrame>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Tunisia dot map (simplified outline rasterized into dots)          */
/* ------------------------------------------------------------------ */

const TUNISIA_OUTLINE: [number, number][] = [
  [25, 7.4],
  [41.7, 9.2],
  [52, 14.7],
  [66.7, 16.6],
  [85.4, 13.9],
  [79, 22.1],
  [69.8, 31.3],
  [68.8, 53.7],
  [56.3, 68.4],
  [70.8, 95.8],
  [77.1, 112.1],
  [86.5, 123.2],
  [64.6, 140],
  [43.8, 138.1],
  [18.8, 136.2],
  [19.8, 130.5],
  [21.9, 112.1],
  [15.6, 101.3],
  [21.9, 90.5],
  [16.7, 78.9],
  [25, 70.5],
  [16.7, 60.8],
  [21.9, 51.8],
  [16.7, 38.7],
  [24, 29.5],
  [25, 18.4],
];

function inTunisia(x: number, y: number): boolean {
  let inside = false;
  for (let i = 0, j = TUNISIA_OUTLINE.length - 1; i < TUNISIA_OUTLINE.length; j = i++) {
    const [xi, yi] = TUNISIA_OUTLINE[i];
    const [xj, yj] = TUNISIA_OUTLINE[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

function inDjerba(x: number, y: number): boolean {
  const dx = (x - 70.5) / 7.5;
  const dy = (y - 72) / 3.6;
  return dx * dx + dy * dy < 1;
}

const TUNISIA_DOTS: [number, number][] = (() => {
  const dots: [number, number][] = [];
  const solid = (
    x: number,
    y: number,
    fn: (x: number, y: number) => boolean,
    inset: number
  ) =>
    fn(x, y) &&
    fn(x - inset, y) &&
    fn(x + inset, y) &&
    fn(x, y - inset) &&
    fn(x, y + inset) &&
    fn(x - inset * 0.7, y - inset * 0.7) &&
    fn(x + inset * 0.7, y - inset * 0.7) &&
    fn(x - inset * 0.7, y + inset * 0.7) &&
    fn(x + inset * 0.7, y + inset * 0.7);
  for (let x = 3; x <= 97; x += 6.4) {
    for (let y = 3; y <= 137; y += 6.4) {
      if (solid(x, y, inTunisia, 1.7) || solid(x, y, inDjerba, 1.3)) {
        dots.push([x, y]);
      }
    }
  }
  return dots;
})();

export function TunisiaDots({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 100 140" className={className} aria-hidden>
      {TUNISIA_DOTS.map(([x, y]) => (
        <circle key={`${x}-${y}`} cx={x} cy={y} r="2.1" fill="currentColor" />
      ))}
    </svg>
  );
}

export function DotHalo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 200 200" className={className} aria-hidden>
      <circle cx="100" cy="100" r="30" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="100" cy="100" r="52" fill="none" stroke="currentColor" strokeWidth="1.5" strokeDasharray="3 7" />
      <circle cx="100" cy="100" r="74" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="100" cy="100" r="95" fill="none" stroke="currentColor" strokeWidth="1.5" strokeDasharray="2 8" />
    </svg>
  );
}

export function DotCluster({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 44 44" className={className} aria-hidden>
      {Array.from({ length: 16 }, (_, i) => (
        <circle
          key={i}
          cx={(i % 4) * 11 + 5}
          cy={Math.floor(i / 4) * 11 + 5}
          r="2.2"
          fill="currentColor"
        />
      ))}
    </svg>
  );
}

export function DottedArrow({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 10" className={className} aria-hidden>
      <path d="M1 5h31" stroke="currentColor" strokeWidth="1.8" strokeDasharray="1.5 5" strokeLinecap="round" />
      <path d="m33 1.5 5.5 3.5-5.5 3.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  How it works                                                       */
/* ------------------------------------------------------------------ */

function How() {
  const { t } = useLanguage();
  return (
    <section id="how" className="relative scroll-mt-28 overflow-hidden py-20 md:py-28">
      <div
        className="pointer-events-none absolute inset-0 bg-gradient-to-b from-white via-lilac-100/55 to-white"
        aria-hidden
      />
      <TunisiaDots className="pointer-events-none absolute -right-10 top-1/2 hidden h-[118%] -translate-y-1/2 text-primary-500/[0.16] [mask-image:linear-gradient(to_left,black_50%,transparent)] md:block" />
      <TunisiaDots className="pointer-events-none absolute left-1/2 top-1/2 h-[135%] -translate-x-1/2 -translate-y-1/2 text-primary-500/[0.07] md:hidden" />

      <div className="relative mx-auto max-w-6xl px-5 sm:px-8">
        <SectionHead
          overline={t("landing.how.overline")}
          title={
            <>
              {t("landing.how.title1")}{" "}
              <span className="font-accent font-medium italic text-primary-600">
                {t("landing.how.title2")}
              </span>
            </>
          }
        />

        <div className="grid gap-5 lg:grid-cols-2">
          {getPaths(t).map((path, i) => (
            <Reveal key={path.title} delay={i * 100}>
              <article className="cw-glass cw-lift h-full rounded-3xl p-6 sm:p-7">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <span className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-primary-500 to-indigo-500 text-white shadow-md shadow-primary-500/25">
                      <path.Icon className="h-5 w-5" />
                    </span>
                    <div>
                      <span className="block text-[11px] font-bold uppercase tracking-wide text-primary-700">
                        {path.kicker}
                      </span>
                      <span className="block text-[11px] font-medium text-ink-faint">
                        {path.forWho}
                      </span>
                    </div>
                  </div>
                </div>
                <h3 className="mt-4 text-xl font-semibold tracking-tight text-ink">
                  {path.title}
                </h3>
                <ol className="mt-5 flex flex-wrap items-center gap-y-2.5">
                  {path.steps.map((s, idx) => (
                    <li key={s} className="flex items-center">
                      <span className="flex items-center gap-2 rounded-xl border border-ink/8 bg-white/85 px-3 py-2 text-[13px] font-medium text-ink shadow-sm transition-colors duration-300 hover:border-primary-300">
                        <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-primary-500/12 text-[10px] font-bold text-primary-700">
                          {idx + 1}
                        </span>
                        {s}
                      </span>
                      {idx < path.steps.length - 1 && (
                        <span className="mx-2 h-px w-4 shrink-0 bg-primary-300/70" aria-hidden />
                      )}
                    </li>
                  ))}
                </ol>
              </article>
            </Reveal>
          ))}
        </div>

        <Reveal>
          <div className="relative mt-5 flex flex-col items-center overflow-hidden rounded-3xl bg-ink px-6 py-8 text-center text-white shadow-[0_30px_70px_-30px_rgba(23,18,58,0.6)] sm:px-10">
            <div className="cw-dots pointer-events-none absolute inset-0 opacity-20 invert" aria-hidden />
            <div
              className="pointer-events-none absolute -top-24 left-1/2 h-48 w-96 -translate-x-1/2 rounded-full bg-primary-500/30 blur-3xl"
              aria-hidden
            />
            <p className="relative text-xs font-semibold uppercase tracking-[0.16em] text-white/50">
              {t("landing.how.meet")}
            </p>
            <DotCluster className="pointer-events-none absolute right-5 top-5 h-9 w-9 text-white/20" />
            <DotCluster className="pointer-events-none absolute bottom-5 left-5 h-9 w-9 text-white/20" />
            <div className="relative mt-5 flex flex-wrap items-center justify-center gap-2.5">
              {[
                [t("landing.how.chipInvite"), IconUnlock],
                [t("landing.how.chipInterview"), IconMic],
                [t("landing.how.chipAnalysis"), IconSpark],
                [t("landing.how.chipDecision"), IconFile],
              ].map(([label, Icon], i) => (
                <div key={String(label)} className="flex items-center gap-2">
                  <span className="inline-flex items-center gap-2 rounded-xl bg-white/10 px-3.5 py-2.5 text-sm font-semibold">
                    <Icon className="h-4 w-4 text-primary-300" />
                    {label as string}
                  </span>
                  {i < 3 && <DottedArrow className="hidden h-2.5 w-10 shrink-0 text-white/45 sm:block" />}
                </div>
              ))}
            </div>
            <p className="mt-5 flex items-center justify-center gap-2 text-[13px] text-white/70">
              <IconLock className="h-3.5 w-3.5" />
              {t("landing.how.note")}
            </p>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Trust moment                                                       */
/* ------------------------------------------------------------------ */

function TrustMoment() {
  const { t } = useLanguage();
  return (
    <section className="py-8 md:py-12">
      <div className="mx-auto max-w-5xl px-5 sm:px-8">
        <Reveal>
          <div className="relative overflow-hidden rounded-[2rem] border border-primary-200/60 bg-gradient-to-br from-white via-primary-50 to-lilac-100 px-6 py-10 text-center shadow-[0_30px_70px_-40px_rgba(108,57,232,0.5)] sm:px-12">
            <div
              className="cw-dots pointer-events-none absolute inset-0 opacity-40 [mask-image:radial-gradient(60%_80%_at_50%_0%,black,transparent)]"
              aria-hidden
            />
            <DotHalo className="pointer-events-none absolute left-1/2 top-10 h-64 w-64 -translate-x-1/2 text-primary-400/25" />
            <DotCluster className="pointer-events-none absolute left-6 top-6 h-10 w-10 text-primary-400/50" />
            <DotCluster className="pointer-events-none absolute bottom-6 right-6 h-10 w-10 text-primary-400/50" />
            <div className="relative">
              <span className="inline-flex items-center gap-2 rounded-full border border-primary-200 bg-white/70 px-3.5 py-1.5 text-xs font-semibold text-primary-700 backdrop-blur">
                <IconLock className="h-3.5 w-3.5" />
                {t("landing.trust.rule")}
              </span>
              <h2 className="mx-auto mt-5 max-w-2xl text-2xl font-semibold leading-tight tracking-tight text-ink sm:text-[2.1rem]">
                {t("landing.trust.title1")}{" "}
                <span className="font-accent font-medium italic text-primary-600">
                  {t("landing.trust.title2")}
                </span>
              </h2>
              <div className="mx-auto mt-8 grid max-w-3xl grid-cols-1 gap-4 sm:grid-cols-[1fr_auto_1fr]">
                <div className="rounded-2xl border border-ink/8 bg-white/70 p-5 text-left">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
                    {t("landing.trust.candLabel")}
                  </p>
                  <p className="mt-2 text-sm font-semibold text-ink">
                    {t("landing.trust.candTitle")}
                  </p>
                  <p className="mt-1 text-[13px] text-ink-soft">
                    {t("landing.trust.candBody")}
                  </p>
                </div>
                <span className="hidden place-items-center text-primary-300 sm:grid">
                  <IconLock className="h-6 w-6" />
                </span>
                <div className="rounded-2xl border border-ink/8 bg-white/70 p-5 text-left">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
                    {t("landing.trust.recLabel")}
                  </p>
                  <p className="mt-2 text-sm font-semibold text-ink">
                    {t("landing.trust.recTitle")}
                  </p>
                  <p className="mt-1 text-[13px] text-ink-soft">
                    {t("landing.trust.recBody")}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Dual audience                                                      */
/* ------------------------------------------------------------------ */

function Audience() {
  const { t } = useLanguage();
  const [side, setSide] = useState<"recruiter" | "candidate">("recruiter");
  const points = side === "recruiter" ? getRecruiterPoints(t) : getCandidatePoints(t);

  return (
    <section id="candidates" className="scroll-mt-28 py-20 md:py-28">
      <div className="mx-auto max-w-6xl px-5 sm:px-8">
        <SectionHead
          overline={t("landing.audience.overline")}
          title={
            <>
              {t("landing.audience.title1")}{" "}
              <span className="font-accent font-medium italic text-primary-600">
                {t("landing.audience.title2")}
              </span>
            </>
          }
        />

        <div className="mx-auto mb-10 flex w-fit rounded-full border border-ink/10 bg-white/70 p-1 shadow-sm">
          {(
            [
              ["recruiter", t("landing.audience.forRecruiters"), IconUsers],
              ["candidate", t("landing.audience.forCandidates"), IconBriefcase],
            ] as const
          ).map(([id, label, Icon]) => (
            <button
              key={id}
              type="button"
              onClick={() => setSide(id)}
              className={cn(
                "inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold transition-all",
                side === id
                  ? "bg-gradient-to-br from-ink via-[#2a1f56] to-primary-700 text-white shadow-lg shadow-primary-900/25"
                  : "text-ink-soft hover:text-ink"
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </div>

        <div className="grid items-center gap-8 lg:grid-cols-2">
          <Reveal>
            <ProductFrame
              label={
                side === "recruiter"
                  ? t("landing.frame.recruiter")
                  : t("landing.frame.candidate")
              }
            >
              {side === "recruiter" ? (
                <StageInvite />
              ) : (
                <StagePortal />
              )}
            </ProductFrame>
          </Reveal>

          <Reveal delay={80}>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary-700">
              {side === "recruiter" ? t("landing.audience.recruitCockpit") : t("landing.stage.candidatePortal")}
            </p>
            <h3 className="mt-2 text-2xl font-semibold tracking-tight text-ink">
              {side === "recruiter"
                ? t("landing.audience.recruitTitle")
                : t("landing.audience.candTitle")}
            </h3>
            <ul className="mt-6 space-y-5">
              {points.map((p) => (
                <li key={p.title} className="flex gap-3">
                  <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-primary-500/10 text-primary-700">
                    <IconCheck className="h-3.5 w-3.5" />
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-ink">{p.title}</p>
                    <p className="mt-0.5 text-sm leading-relaxed text-ink-soft">
                      {p.body}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Differentiation                                                    */
/* ------------------------------------------------------------------ */

function Difference() {
  const { t } = useLanguage();
  return (
    <section className="py-20 md:py-28">
      <div className="mx-auto max-w-6xl px-5 sm:px-8">
        <SectionHead
          overline={t("landing.diff.overline")}
          title={
            <>
              {t("landing.diff.title1")}{" "}
              <span className="font-accent font-medium italic text-primary-600">
                {t("landing.diff.title2")}
              </span>
            </>
          }
        />
        <div className="grid gap-5 md:grid-cols-3">
          {getDiff(t).map((d, i) => (
            <Reveal key={d.kicker} delay={i * 90}>
              <article className="cw-glass h-full rounded-3xl p-7">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary-700">
                  {d.kicker}
                </p>
                <h3 className="mt-3 text-xl font-semibold tracking-tight text-ink">
                  {d.title}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-ink-soft">{d.body}</p>
              </article>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Statement band                                                     */
/* ------------------------------------------------------------------ */

function Statement() {
  const { t } = useLanguage();
  return (
    <section className="relative overflow-hidden py-16 md:py-24">
      <DotHalo className="pointer-events-none absolute -left-24 top-1/2 h-80 w-80 -translate-y-1/2 text-primary-400/25" />
      <DotHalo className="pointer-events-none absolute -right-28 top-1/4 h-96 w-96 text-primary-400/20" />
      <DotCluster className="pointer-events-none absolute left-[10%] top-8 h-10 w-10 text-primary-400/45" />
      <DotCluster className="pointer-events-none absolute bottom-8 right-[12%] h-10 w-10 text-primary-400/45" />
      <TunisiaDots className="pointer-events-none absolute left-1/2 top-1/2 h-[130%] -translate-x-1/2 -translate-y-1/2 text-primary-500/[0.06]" />

      <div className="relative mx-auto max-w-5xl px-5 text-center sm:px-8">
        <p className="text-[12px] font-bold uppercase tracking-[0.32em] text-primary-700">
          {t("landing.statement.overline")}
        </p>
        <p className="mt-7 text-4xl font-semibold leading-[1.05] tracking-tight text-ink sm:text-6xl lg:text-7xl">
          {t("landing.statement.line1")}{" "}
          <span className="font-accent font-medium italic text-primary-600">
            {t("landing.statement.skills")}
          </span>
          <br className="hidden sm:block" />
          {t("landing.statement.line2")}
        </p>
        <DottedArrow className="mx-auto mt-10 h-3 w-14 text-primary-500/50" />
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Report showcase                                                    */
/* ------------------------------------------------------------------ */

function ReportShowcase() {
  const { t } = useLanguage();
  const advance = t("landing.stage.decisionAdvance");
  const hold = t("landing.stage.decisionHold");
  const rows = [
    ["Firas Ray", t("landing.roles.marketingLead"), "82%", advance],
    ["Sami Kallel", t("landing.roles.projectManager"), "79%", advance],
    ["Rayen Heni", t("landing.roles.seoLead"), "77%", hold],
    ["Lea Ben Salah", t("landing.roles.contentLead"), "71%", t("landing.report.notInvited")],
  ];
  const rubric = [
    [t("landing.rubric.1"), "88"],
    [t("landing.rubric.2"), "84"],
    [t("landing.rubric.3"), "79"],
    [t("landing.rubric.4"), "76"],
  ];

  return (
    <section className="py-20 md:py-28">
      <div className="mx-auto max-w-6xl px-5 sm:px-8">
        <SectionHead
          overline={t("landing.report.overline")}
          title={
            <>
              {t("landing.report.title1")}{" "}
              <span className="font-accent font-medium italic text-primary-600">
                {t("landing.report.title2")}
              </span>
            </>
          }
        />

        <div className="grid items-center gap-8 lg:grid-cols-[0.85fr_1.15fr]">
          <Reveal>
            <ul className="space-y-5">
              {[
                [
                  t("landing.report.b1_t"),
                  t("landing.report.b1_b"),
                ],
                [
                  t("landing.report.b2_t"),
                  t("landing.report.b2_b"),
                ],
                [
                  t("landing.report.b3_t"),
                  t("landing.report.b3_b"),
                ],
              ].map(([title, b]) => (
                <li key={title} className="flex gap-3">
                  <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-primary-500/10 text-primary-700">
                    <IconCheck className="h-3.5 w-3.5" />
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-ink">{title}</p>
                    <p className="mt-0.5 text-sm leading-relaxed text-ink-soft">{b}</p>
                  </div>
                </li>
              ))}
            </ul>
            <a href="#demo" className={cn(btnPrimary, "mt-7")}>
              {t("landing.report.cta")}
              <IconArrowRight className="h-4 w-4" />
            </a>
          </Reveal>

          <Reveal delay={100}>
            <div className="relative">
              <DotHalo className="pointer-events-none absolute -right-20 -top-20 h-72 w-72 text-primary-400/30" />
              <DotCluster className="pointer-events-none absolute -left-8 bottom-8 h-10 w-10 text-primary-400/40" />
              <div
                className="absolute inset-0 translate-x-3 translate-y-3 rounded-[1.4rem] border border-ink/8 bg-white/50"
                aria-hidden
              />
              <div className="relative overflow-hidden rounded-[1.4rem] border border-ink/10 bg-white p-6 shadow-[0_40px_90px_-40px_rgba(108,57,232,0.5)] sm:p-7">
                <div className="flex items-start justify-between gap-3 border-b border-ink/8 pb-4">
                  <div className="flex items-center gap-2.5">
                    <LogoMark className="h-8 w-8" />
                    <div>
                      <p className="text-sm font-semibold text-ink">{t("landing.report.mockTitle")}</p>
                      <p className="text-xs text-ink-faint">{t("landing.report.mockSub")}</p>
                    </div>
                  </div>
                  <span className="rounded-full bg-emerald-500/12 px-2.5 py-1 text-[11px] font-semibold text-emerald-700">
                    {t("landing.stage.readyToSend")}
                  </span>
                </div>

                <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl bg-lilac-50 px-4 py-3 text-[13px]">
                  <span className="text-ink-soft">
                    <b className="text-ink">33</b> {t("landing.report.applied")}
                  </span>
                  <span className="text-primary-300">→</span>
                  <span className="text-ink-soft">
                    <b className="text-ink">12</b> {t("landing.report.scored")}
                  </span>
                  <span className="text-primary-300">→</span>
                  <span className="text-ink-soft">
                    <b className="text-emerald-700">4</b> {t("landing.report.shortlisted")}
                  </span>
                </div>

                <div className="mt-4 overflow-hidden rounded-xl border border-ink/8">
                  <div className="grid grid-cols-[1fr_60px_84px] bg-ink/4 px-3.5 py-2 text-[10px] font-semibold uppercase tracking-wide text-ink-faint">
                    <span>{t("landing.stage.colCandidate")}</span>
                    <span>{t("landing.stage.colMatch")}</span>
                    <span>{t("landing.stage.colDecision")}</span>
                  </div>
                  {rows.map(([n, r, m, d]) => (
                    <div
                      key={n}
                      className="grid grid-cols-[1fr_60px_84px] items-center gap-2 border-t border-ink/6 px-3.5 py-2.5 text-[13px]"
                    >
                      <span className="min-w-0">
                        <span className="block truncate font-semibold text-ink">{n}</span>
                        <span className="block truncate text-[11px] text-ink-faint">{r}</span>
                      </span>
                      <span className="font-semibold text-primary-700">{m}</span>
                      <span
                        className={cn(
                          "text-[11px] font-semibold",
                          d === advance
                            ? "text-emerald-700"
                            : d === hold
                              ? "text-amber-600"
                              : "text-ink-faint"
                        )}
                      >
                        {d}
                      </span>
                    </div>
                  ))}
                </div>

                <div className="mt-4">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-ink-faint">
                    {t("landing.report.topRubric")}
                  </p>
                  <div className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1.5">
                    {rubric.map(([k, v]) => (
                      <div key={k} className="flex items-center justify-between text-[12px]">
                        <span className="text-ink-soft">{k}</span>
                        <span className="font-semibold text-primary-700">{v}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="mt-5 flex items-center justify-between border-t border-ink/8 pt-3 text-[11px] text-ink-faint">
                  <span>{t("landing.report.generatedBy")}</span>
                  <span>{t("landing.report.privateBeta")}</span>
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Pricing                                                            */
/* ------------------------------------------------------------------ */

function Pricing({ onPickPack }: { onPickPack: (id: string) => void }) {
  const { t } = useLanguage();
  return (
    <section id="pricing" className="scroll-mt-28 py-20 md:py-28">
      <div className="mx-auto max-w-6xl px-5 sm:px-8">
        <SectionHead
          overline={t("landing.pricing.overline")}
          title={
            <>
              {t("landing.pricing.title1")}{" "}
              <span className="font-accent font-medium italic text-primary-600">
                {t("landing.pricing.title2")}
              </span>
            </>
          }
        />

        <div className="grid items-stretch gap-5 md:grid-cols-3">
          {getTiers(t).map((tier, i) => (
            <Reveal key={tier.id} delay={i * 100} className="h-full">
              <article
                className={cn(
                  "relative flex h-full flex-col rounded-3xl p-7 transition-all duration-300",
                  tier.featured
                    ? "border-2 border-primary-500/45 bg-white/90 shadow-[0_30px_70px_-28px_rgba(108,57,232,0.48)] backdrop-blur md:-translate-y-3"
                    : "cw-glass cw-lift"
                )}
              >
                {tier.featured && (
                  <>
                    <span className="absolute -top-3.5 left-1/2 -translate-x-1/2 rounded-full bg-gradient-to-r from-primary-500 to-indigo-600 px-3.5 py-1 text-xs font-semibold text-white shadow-lg shadow-primary-600/30">
                      {t("landing.pricing.mostBooked")}
                    </span>
                    <DotCluster className="pointer-events-none absolute right-5 top-5 h-9 w-9 text-primary-300/60" />
                  </>
                )}
                <h3 className="text-base font-semibold text-ink">{tier.name}</h3>
                <p className="mt-1 text-sm text-ink-faint">{tier.blurb}</p>
                <div className="mt-5 flex items-baseline gap-1.5">
                  <span className="text-[2.5rem] font-semibold leading-none tracking-tight text-ink">
                    {tier.price}
                  </span>
                  <span className="text-sm font-semibold text-ink-soft">{tier.unit}</span>
                </div>
                {tier.perks && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {tier.perks.map((perk) => (
                      <span
                        key={perk}
                        className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1 text-[11px] font-semibold text-emerald-700"
                      >
                        <IconCheck className="h-3 w-3" />
                        {perk}
                      </span>
                    ))}
                  </div>
                )}
                <ul className="mt-6 flex-1 space-y-3 border-t border-ink/8 pt-6">
                  {tier.features.map((f) => (
                    <li key={f} className="flex items-center gap-2.5 text-sm text-ink-soft">
                      <span
                        className={cn(
                          "grid h-4.5 w-4.5 place-items-center rounded-full",
                          tier.featured
                            ? "bg-primary-600 text-white"
                            : "bg-emerald-500/15 text-emerald-600"
                        )}
                      >
                        <IconCheck className="h-2.5 w-2.5" />
                      </span>
                      {f}
                    </li>
                  ))}
                </ul>
                <button
                  type="button"
                  onClick={() => onPickPack(tier.id)}
                  className={cn("mt-7 w-full", tier.featured ? btnPrimary : btnGhost)}
                >
                  {tier.cta}
                  <IconArrowRight className="h-4 w-4" />
                </button>
              </article>
            </Reveal>
          ))}
        </div>
        <p className="mt-8 text-center text-sm text-ink-faint">
          {t("landing.pricing.foot")}
        </p>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Demo                                                               */
/* ------------------------------------------------------------------ */

type DemoPayload = {
  name: string;
  company: string;
  email: string;
  pack: string;
  context: string;
};

function buildMailtoHref(p: DemoPayload): string {
  const subject = `Beta demo request — ${p.pack}`;
  const body = [
    `Name: ${p.name}`,
    `Company / agency: ${p.company}`,
    `Work email: ${p.email}`,
    `Beta pack: ${p.pack}`,
    "",
    "Hiring context:",
    p.context,
  ].join("\n");
  return `mailto:${DEMO_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}

async function submitDemoRequest(payload: DemoPayload): Promise<string> {
  const apiBase = getApiBaseUrl();

  // GET requests are safe and cause the CSRF middleware to issue
  // a fresh token in both the response header and csrf_token cookie.
  const csrfResponse = await fetch(`${apiBase}/config/public`, {
    method: "GET",
    credentials: "include",
    headers: {
      Accept: "application/json",
    },
  });

  if (!csrfResponse.ok) {
    throw new Error("Unable to initialize secure demo request");
  }

  const csrfToken = csrfResponse.headers.get("X-CSRF-Token");

  if (!csrfToken) {
    throw new Error("Missing CSRF token");
  }

  const response = await fetch(`${apiBase}/demo-request`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (response.status === 409) {
    throw new Error("Request already received");
  }

  if (!response.ok) {
    throw new Error("Unable to submit demo request");
  }

  await response.json();

  // The backend stores the lead; the mailto link is the user's
  // follow-up action after successful submission.
  return buildMailtoHref(payload);
}

const inputCls =
  "w-full rounded-xl border border-ink/10 bg-white/80 px-4 py-3 text-sm text-ink shadow-sm outline-none transition placeholder:text-ink-faint/70 focus:border-primary-400 focus:ring-4 focus:ring-primary-500/10";

function OutcomeStat({ value, label, active }: { value: number; label: string; active: boolean }) {
  const n = useCountUp(value, active);
  return (
    <div>
      <p className="text-3xl font-semibold tracking-tight text-ink">{n}</p>
      <p className="mt-1 text-xs font-medium text-ink-faint">{label}</p>
    </div>
  );
}

function DemoSection({
  packId,
  onPackChange,
}: {
  packId: string;
  onPackChange: (v: string) => void;
}) {
  const { t } = useLanguage();
  const pack = t(`landing.pricing.${packId}.name`);
  const { ref, visible } = useReveal<HTMLDivElement>();
  const [form, setForm] = useState({
    name: "",
    company: "",
    email: "",
    context: "",
  });
  const [submitted, setSubmitted] = useState(false);
  const [lastHref, setLastHref] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    try {
      const result = await submitDemoRequest({
        ...form,
        pack,
      });

      setLastHref(result);
      setSubmitted(true);
    } catch (error) {
      console.error("Demo request failed:", error);
      window.alert(
        error instanceof Error
          ? error.message
          : "Unable to submit demo request. Please try again.",
      );
    }
  };

  return (
    <section id="demo" className="relative scroll-mt-28 py-20 md:py-28">
      <div
        className="pointer-events-none absolute inset-0"
        aria-hidden
        style={{
          background:
            "radial-gradient(50% 60% at 85% 20%, rgba(157,114,255,0.12), transparent 60%)",
        }}
      />
      <div className="relative mx-auto max-w-6xl px-5 sm:px-8">
        <div className="grid gap-12 lg:grid-cols-[0.9fr_1.1fr]">
          <Reveal>
            <Overline>{t("landing.demo.overline")}</Overline>
            <h2 className="mt-4 text-3xl font-semibold leading-[1.12] tracking-tight text-ink md:text-[2.55rem]">
              {t("landing.demo.title1")}{" "}
              <span className="font-accent font-medium italic text-primary-600">
                {t("landing.demo.title2")}
              </span>
            </h2>
            <p className="mt-5 max-w-md text-base leading-relaxed text-ink-soft">
              {t("landing.demo.body")}
            </p>

            <div ref={ref} className="mt-8 grid grid-cols-3 gap-4 border-t border-ink/8 pt-6">
              <OutcomeStat value={30} label={t("landing.demo.statMinutes")} active={visible} />
              <OutcomeStat value={1} label={t("landing.demo.statRubric")} active={visible} />
              <OutcomeStat value={5} label={t("landing.demo.statNames")} active={visible} />
            </div>

            <div className="mt-8 flex items-center gap-3 rounded-2xl border border-ink/8 bg-white/65 px-4 py-3.5">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-primary-500 to-indigo-500 text-white">
                <IconMail className="h-5 w-5" />
              </span>
              <div>
                <p className="text-sm font-semibold text-ink">{DEMO_EMAIL}</p>
                <p className="text-xs text-ink-faint">{t("landing.demo.reply")}</p>
              </div>
            </div>
          </Reveal>

          <Reveal delay={100}>
            <div className="cw-glass-strong rounded-3xl p-6 sm:p-8">
              {submitted ? (
                <div className="flex min-h-80 flex-col items-center justify-center gap-4 py-8 text-center">
                  <span className="grid h-14 w-14 place-items-center rounded-full bg-emerald-500/12 text-emerald-600">
                    <IconCheck className="h-7 w-7" />
                  </span>
                  <h3 className="text-xl font-semibold text-ink">{t("landing.demo.submittedTitle")}</h3>
                  <p className="max-w-sm text-sm leading-relaxed text-ink-soft">
                    {t("landing.demo.submittedBody").replace("{email}", DEMO_EMAIL)}
                  </p>
                  <div className="mt-2 flex flex-col gap-3 sm:flex-row">
                    {lastHref && (
                      <a href={lastHref} className={btnPrimary}>
                        <IconSend className="h-4 w-4" />
                        {t("landing.demo.openMail")}
                      </a>
                    )}
                    <button type="button" onClick={() => setSubmitted(false)} className={btnGhost}>
                      {t("landing.demo.editRequest")}
                    </button>
                  </div>
                </div>
              ) : (
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <label htmlFor="demo-name" className="mb-1.5 block text-sm font-medium text-ink">
                        {t("landing.demo.fullName")}
                      </label>
                      <input
                        id="demo-name"
                        required
                        className={inputCls}
                        placeholder={t("landing.demo.namePlaceholder")}
                        value={form.name}
                        onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                      />
                    </div>
                    <div>
                      <label htmlFor="demo-company" className="mb-1.5 block text-sm font-medium text-ink">
                        {t("landing.demo.company")}
                      </label>
                      <input
                        id="demo-company"
                        required
                        className={inputCls}
                        placeholder={t("landing.demo.companyPlaceholder")}
                        value={form.company}
                        onChange={(e) => setForm((f) => ({ ...f, company: e.target.value }))}
                      />
                    </div>
                  </div>
                  <div>
                    <label htmlFor="demo-email" className="mb-1.5 block text-sm font-medium text-ink">
                      {t("landing.demo.workEmail")}
                    </label>
                    <input
                      id="demo-email"
                      required
                      type="email"
                      className={inputCls}
                      placeholder={t("landing.demo.emailPlaceholder")}
                      value={form.email}
                      onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                    />
                  </div>
                  <div>
                    <label htmlFor="demo-pack" className="mb-1.5 block text-sm font-medium text-ink">
                      {t("landing.demo.pack")}
                    </label>
                    <div className="relative">
                      <select
                        id="demo-pack"
                        required
                        className={cn(inputCls, "appearance-none pr-10")}
                        value={packId}
                        onChange={(e) => onPackChange(e.target.value)}
                      >
                        {getTiers(t).map((tier) => (
                          <option key={tier.id} value={tier.id}>
                            {tier.name} — {tier.price} {tier.unit}
                          </option>
                        ))}
                      </select>
                      <IconChevronDown className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
                    </div>
                  </div>
                  <div>
                    <label htmlFor="demo-context" className="mb-1.5 block text-sm font-medium text-ink">
                      {t("landing.demo.context")}
                    </label>
                    <textarea
                      id="demo-context"
                      rows={4}
                      className={cn(inputCls, "resize-none")}
                      placeholder={t("landing.demo.contextPlaceholder")}
                      value={form.context}
                      onChange={(e) => setForm((f) => ({ ...f, context: e.target.value }))}
                    />
                  </div>
                  <button type="submit" className={cn(btnPrimary, "w-full py-3.5")}>
                    <IconSend className="h-4 w-4" />
                    {t("landing.demo.submit")}
                  </button>
                </form>
              )}
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  FAQ + footer                                                       */
/* ------------------------------------------------------------------ */

function Faq() {
  const { t } = useLanguage();
  const faqs = [
    { q: t("landing.faq.q1_title"), a: t("landing.faq.q1_body") },
    { q: t("landing.faq.q2_title"), a: t("landing.faq.q2_body") },
    { q: t("landing.faq.q3_title"), a: t("landing.faq.q3_body") },
    { q: t("landing.faq.q4_title"), a: t("landing.faq.q4_body") },
  ];
  const [open, setOpen] = useState(0);
  return (
    <section id="faq" className="scroll-mt-28 py-20 md:py-28">
      <div className="mx-auto max-w-3xl px-5 sm:px-8">
        <SectionHead overline={t("landing.faq.overline")} title={t("landing.faq.title")} />
        <div className="space-y-3">
          {faqs.map((item, i) => {
            const isOpen = open === i;
            return (
              <Reveal key={item.q} delay={i * 40}>
                <div className={cn("cw-glass overflow-hidden rounded-2xl", isOpen && "shadow-[0_16px_40px_-20px_rgba(108,57,232,0.35)]")}>
                  <button
                    type="button"
                    aria-expanded={isOpen}
                    onClick={() => setOpen(isOpen ? -1 : i)}
                    className="flex w-full items-center justify-between gap-4 px-5 py-4.5 text-left"
                  >
                    <span className="text-[15px] font-semibold text-ink">{item.q}</span>
                    <span
                      className={cn(
                        "grid h-7 w-7 shrink-0 place-items-center rounded-full border transition-all",
                        isOpen
                          ? "rotate-45 border-primary-500 bg-primary-600 text-white"
                          : "border-ink/12 bg-white text-ink-soft"
                      )}
                    >
                      <IconPlus className="h-3.5 w-3.5" />
                    </span>
                  </button>
                  <div className={cn("grid transition-[grid-template-rows] duration-300", isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]")}>
                    <div className="overflow-hidden">
                      <p className="px-5 pb-5 text-sm leading-relaxed text-ink-soft">{item.a}</p>
                    </div>
                  </div>
                </div>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function Footer() {
  const { t } = useLanguage();
  const navLinks = [
    { label: "Home", href: "#top" },
    { label: t("landing.nav.howItWorks"), href: "#how" },
    { label: t("landing.nav.blogs"), href: "/blogs" },
    { label: t("landing.nav.careers"), href: "/careers" },
  ];

  return (
    <footer className="relative overflow-hidden bg-[linear-gradient(168deg,rgba(26,17,54,0.98)_0%,rgba(43,26,90,0.96)_45%,rgba(66,40,138,0.94)_100%)] text-white/70 shadow-[0_-50px_120px_-70px_rgba(50,25,120,0.8)] backdrop-blur-2xl">
      <div
        className="cw-drift pointer-events-none absolute -top-40 left-1/2 h-96 w-[620px] -translate-x-1/2 rounded-full bg-primary-500/35 blur-3xl"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute -right-28 top-1/4 h-80 w-80 rounded-full bg-sky-400/20 blur-3xl"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute -bottom-36 -left-24 h-80 w-80 rounded-full bg-fuchsia-500/20 blur-3xl"
        aria-hidden
      />
      <div
        className="cw-dots pointer-events-none absolute inset-0 opacity-20 invert [mask-image:radial-gradient(75%_70%_at_50%_0%,black,transparent)]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute inset-x-16 top-0 h-px bg-gradient-to-r from-transparent via-white/40 to-transparent"
        aria-hidden
      />

      <div className="relative mx-auto max-w-6xl px-5 py-16 sm:px-8 md:py-20">
        <div className="mb-12 rounded-[2rem] border border-white/15 bg-white/[0.07] p-6 shadow-[0_28px_80px_-45px_rgba(0,0,0,0.65)] backdrop-blur-xl sm:p-8 md:flex md:items-center md:justify-between md:gap-10">
          <div className="max-w-xl">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-primary-200">
              {t("landing.footer.ctaOverline")}
            </p>
            <h2 className="mt-3 text-2xl font-semibold leading-tight tracking-tight text-white sm:text-3xl">
              {t("landing.footer.ctaTitle")}
            </h2>
          </div>
          <Link
            to="/auth/register"
            className="cw-shine mt-6 inline-flex w-fit items-center gap-2 rounded-xl bg-gradient-to-br from-primary-400 to-primary-700 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-primary-900/30 transition-all duration-300 hover:-translate-y-0.5 md:mt-0"
          >
            Sign up
            <IconArrowRight className="h-4 w-4" />
          </Link>
        </div>

        <div className="flex flex-col justify-between gap-10 md:flex-row">
          <div className="max-w-sm">
            <a href="#top" className="flex items-center gap-2.5">
              <LogoMark className="h-9 w-9" />
              <span className="text-lg font-semibold text-white">Candway</span>
            </a>
            <p className="mt-3 text-sm text-white/55">
              {t("landing.footer.tagline")}
            </p>
            <p className="font-accent mt-4 text-lg italic text-white/90">
              {t("landing.statement.line1")} {t("landing.statement.skills")}{t("landing.statement.line2")}
            </p>
          </div>
          <div className="flex flex-col gap-8 sm:flex-row sm:gap-16">
            <nav aria-label="Footer" className="flex flex-col gap-2.5">
              <p className="text-xs font-semibold uppercase tracking-wider text-white/35">
                {t("landing.footer.explore")}
              </p>
{navLinks.map((l) => {
                  const isPage = l.href.startsWith("/");
                  const navCls = "text-sm font-medium hover:text-white";
                  return isPage ? (
                    <Link key={l.href} to={l.href} className={navCls}>
                      {l.label}
                    </Link>
                  ) : (
                    <a key={l.href} href={l.href} className={navCls}>
                      {l.label}
                    </a>
                  );
                })}
            </nav>
            <div className="flex flex-col gap-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-white/35">
                {t("landing.footer.getStarted")}
              </p>
              <Link
                to="/auth/register"
                className="inline-flex w-fit items-center gap-2 rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 px-5 py-3 text-sm font-semibold text-white"
              >
                Sign up
                <IconArrowRight className="h-4 w-4" />
              </Link>
              <a href={`mailto:${DEMO_EMAIL}`} className="text-sm hover:text-white">
                {DEMO_EMAIL}
              </a>
            </div>
          </div>
        </div>
        <div className="mt-12 flex flex-col justify-between gap-2 border-t border-white/10 pt-6 text-xs text-white/35 sm:flex-row">
          <p>{t("landing.footer.copyright")}</p>
          <p>{t("landing.hero.trustNote")}</p>
        </div>
      </div>
    </footer>
  );
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function CandwayLanding() {
  const [packId, setPackId] = useState("campaign");

  const pickPack = (id: string) => {
    setPackId(id);
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    document.getElementById("demo")?.scrollIntoView({
      behavior: reduced ? "auto" : "smooth",
      block: "start",
    });
  };

  return (
    <div className="relative min-h-screen overflow-x-clip bg-[#fbfaff] font-sans text-ink">
      <div className="cw-noise pointer-events-none fixed inset-0 z-40" aria-hidden />
      <Nav />
      <main>
        <Hero />
        <Proof />
        <Problem />
        <ProductTour />
        <How />
        <TrustMoment />
        <Audience />
        <Difference />
        <Statement />
        <ReportShowcase />
        <Pricing onPickPack={pickPack} />
        <DemoSection packId={packId} onPackChange={setPackId} />
        <Faq />
      </main>
      <Footer />
    </div>
  );
}
