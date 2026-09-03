import { useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { cn } from "../../../utils/cn";
import { useLanguage } from "../../../contexts/language-context";
import { CareersShell, IconClock, IconSearch } from "./public-jobs";
import {
  DotCluster,
  DotHalo,
  DottedArrow,
  IconArrowRight,
  IconBriefcase,
  IconCheck,
  IconLock,
  IconMail,
  IconSpark,
  LogoMark,
  Reveal,
  TunisiaDots,
} from "./candway-landing";
import { CATEGORY_STYLE, POSTS, type Category, type Cover, type Post } from "../data/blog-content";

/* ------------------------------------------------------------------ */
/*  Cover art                                                          */
/* ------------------------------------------------------------------ */

const COVER_META: Record<Cover, { label: string; gradient: string; Icon: (p: { className?: string }) => React.JSX.Element }> = {
  score: { label: "Score", gradient: "from-violet-500 to-fuchsia-400", Icon: IconSpark },
  lock: { label: "Confidentialité", gradient: "from-sky-500 to-indigo-400", Icon: IconLock },
  rubric: { label: "Grille", gradient: "from-emerald-500 to-teal-400", Icon: IconCheck },
  candidate: { label: "Candidat", gradient: "from-amber-500 to-orange-400", Icon: IconBriefcase },
  campaign: { label: "Campagne", gradient: "from-rose-500 to-primary-500", Icon: IconMail },
  report: { label: "Rapport", gradient: "from-primary-500 to-indigo-500", Icon: LogoMark },
};

const CATEGORIES = Object.keys(CATEGORY_STYLE) as Category[];

const careersBtn =
  "inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-primary-600/30 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-xl hover:shadow-primary-600/35 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600";

/* ------------------------------------------------------------------ */
/*  Cover                                                              */
/* ------------------------------------------------------------------ */

function CoverArt({ post, className }: { post: Post; className?: string }) {
  const meta = COVER_META[post.cover];
  return (
    <div className={cn("relative overflow-hidden bg-gradient-to-br", meta.gradient, className)}>
      <div className="cw-dots pointer-events-none absolute inset-0 opacity-20 invert" aria-hidden />
      <div
        className="pointer-events-none absolute -right-8 -top-10 h-32 w-32 rounded-full bg-white/20 blur-2xl"
        aria-hidden
      />
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="grid h-14 w-14 place-items-center rounded-2xl bg-white/20 text-white shadow-inner backdrop-blur-sm">
          <meta.Icon className="h-6 w-6" />
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Card                                                               */
/* ------------------------------------------------------------------ */

function BlogCard({ post, onOpen, delay, wide }: { post: Post; onOpen: () => void; delay: number; wide?: boolean }) {
  const { t } = useLanguage();
  const author = post.author;
  return (
    <Reveal delay={delay} className="h-full">
      <button
        type="button"
        onClick={onOpen}
        className="cw-glass cw-lift group flex h-full w-full flex-col overflow-hidden rounded-3xl text-left"
      >
        <div className={cn("relative", wide ? "h-52" : "h-40")}>
          <CoverArt post={post} className="h-full w-full" />
          <span
            className={cn(
              "absolute left-4 top-4 rounded-full border bg-white/80 px-2.5 py-1 text-[11px] font-semibold backdrop-blur",
              CATEGORY_STYLE[post.category]
            )}
          >
            {post.category}
          </span>
        </div>

        <div className="flex flex-1 flex-col p-6">
          <div className="flex items-center gap-3 text-xs font-medium text-ink-faint">
            <span className="flex items-center gap-1.5">
              <IconClock className="h-3.5 w-3.5" />
              {post.date}
            </span>
            <span className="flex items-center gap-1.5">
              <span className={cn("grid h-5 w-5 place-items-center rounded-full bg-gradient-to-br text-[9px] font-bold text-white", author.gradient)}>
                {author.initials}
              </span>
              {author.name}
            </span>
          </div>

          <h3 className={cn("mt-3 font-semibold leading-snug tracking-tight text-ink transition-colors group-hover:text-primary-700 line-clamp-2", wide ? "text-xl" : "text-lg")}>
            {post.title}
          </h3>
          <p className="mt-2 text-sm leading-relaxed text-ink-soft line-clamp-3">{post.dek}</p>

          <div className="mt-5 flex items-center justify-between border-t border-ink/8 pt-4">
            <span className="text-xs font-medium text-ink-faint">
              {post.read} min · {t("blogs.readTime").replace(" min", "")}
            </span>
            <span className="flex items-center gap-1.5 text-sm font-semibold text-primary-700">
              {t("blogs.readArticle")}
              <IconArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1" />
            </span>
          </div>
        </div>
      </button>
    </Reveal>
  );
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function BlogsPage() {
  const navigate = useNavigate();
  const { t } = useLanguage();
  const [query, setQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState<Category | "">("");

  const featured = POSTS.find((p) => p.featured);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return POSTS.filter((p) => {
      const okCat = !activeCategory || p.category === activeCategory;
      const okQuery =
        !q ||
        p.title.toLowerCase().includes(q) ||
        p.dek.toLowerCase().includes(q) ||
        p.category.toLowerCase().includes(q) ||
        p.author.name.toLowerCase().includes(q);
      return okCat && okQuery;
    });
  }, [query, activeCategory]);

  const resetFilters = () => {
    setQuery("");
    setActiveCategory("");
  };

  const shownFeatured: Post | undefined = featured && !activeCategory && !query.trim() ? featured : undefined;

  return (
    <CareersShell onBack={() => (window.location.hash = "#top")} title={t("blogs.backToSite")} badge={t("blogs.badge")}>
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
              {t("blogs.heroEyebrow")}
            </span>
            <h1 className="mt-6 text-4xl font-semibold leading-[1.05] tracking-[-0.03em] text-ink sm:text-5xl lg:text-6xl">
              {t("blogs.heroTitlePrefix")}{" "}
              <span className="font-accent font-medium italic text-primary-600">
                {t("blogs.heroTitleHighlight")}
              </span>
            </h1>
            <p className="mx-auto mt-5 max-w-xl text-base leading-relaxed text-ink-soft sm:text-lg">
              {t("blogs.heroSubtitle")}
            </p>
          </div>

          {/* category filter pills */}
          <div className="mx-auto mt-9 max-w-3xl">
            <div className="flex items-center gap-3 rounded-2xl border border-ink/10 bg-white/85 px-4 py-3.5 shadow-[0_18px_44px_-20px_rgba(108,57,232,0.35)] backdrop-blur transition focus-within:border-primary-400 focus-within:ring-4 focus-within:ring-primary-500/10">
              <IconSearch className="h-4.5 w-4.5 shrink-0 text-ink-faint" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t("blogs.searchPlaceholder")}
                className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink-faint/70"
              />
            </div>
            <div className="mt-3.5 flex flex-wrap items-center justify-center gap-2">
              {(["" as const, ...CATEGORIES] as const).map((cat) => (
                <button
                  key={cat || "all"}
                  type="button"
                  onClick={() => setActiveCategory(cat as Category | "")}
                  className={cn(
                    "rounded-full px-4 py-1.5 text-[13px] font-semibold transition-all",
                    activeCategory === cat
                      ? "bg-ink text-white shadow-md"
                      : cat
                        ? cn("border bg-white/70 hover:bg-white", CATEGORY_STYLE[cat])
                        : "bg-white/70 text-ink-soft hover:bg-white hover:text-ink"
                  )}
                >
                  {cat || t("blogs.allTopics")}
                </button>
              ))}
            </div>
          </div>

          <p className="mt-6 text-center text-[13px] font-medium text-ink-faint">
            {t("blogs.showingArticles")
              .replace("{x}", String(filtered.length))
              .replace("{y}", String(POSTS.length))}
          </p>
        </div>
      </section>

      {/* articles */}
      <section className="mx-auto max-w-6xl px-5 pb-20 sm:px-8">
        {filtered.length === 0 ? (
          <Reveal>
            <div className="cw-glass mx-auto max-w-md rounded-3xl p-10 text-center">
              <p className="text-lg font-semibold text-ink">{t("blogs.noMatchTitle")}</p>
              <p className="mt-2 text-sm text-ink-soft">{t("blogs.noMatchBody")}</p>
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
          <div className="space-y-8">
            {shownFeatured && (
              <BlogCard post={shownFeatured} wide onOpen={() => navigate(`/blog/${shownFeatured.slug}`)} delay={0} />
            )}
            <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
              {filtered.map((post, i) => (
                <BlogCard
                  key={post.slug}
                  post={post}
                  onOpen={() => navigate(`/blog/${post.slug}`)}
                  delay={(shownFeatured ? i + 1 : i) * 70}
                />
              ))}
            </div>
          </div>
        )}
      </section>

      {/* how we write — candidate-friendly */}
      <section className="border-y border-ink/6 bg-white/50 py-14">
        <div className="mx-auto max-w-6xl px-5 sm:px-8">
          <Reveal className="text-center">
            <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-primary-700">
              {t("blogs.howTitle")}
            </p>
            <h2 className="mt-3 text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
              {t("blogs.howHead1")}{" "}
              <span className="font-accent font-medium italic text-primary-600">
                {t("blogs.howHead2")}
              </span>
            </h2>
          </Reveal>
          <Reveal delay={100}>
            <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
              {[
                { Icon: IconSpark, label: t("blogs.value1") },
                { Icon: IconLock, label: t("blogs.value2") },
                { Icon: LogoMark, label: t("blogs.value3") },
              ].map(({ Icon, label }, i) => (
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
                  {i < 2 && (
                    <DottedArrow className="hidden h-2.5 w-9 shrink-0 text-primary-500/50 md:block" />
                  )}
                </div>
              ))}
            </div>
            <p className="mt-6 flex items-center justify-center gap-2 text-[13px] font-medium text-ink-soft">
              <IconLock className="h-3.5 w-3.5 text-primary-600" />
              {t("blogs.howNote")}
            </p>
          </Reveal>
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-6xl px-5 py-16 sm:px-8">
        <Reveal delay={150}>
          <div className="flex flex-col items-center justify-between gap-4 rounded-3xl border border-primary-200/60 bg-gradient-to-br from-white via-primary-50 to-lilac-100 px-6 py-7 text-center sm:flex-row sm:text-left">
            <div>
              <p className="text-base font-semibold text-ink">{t("blogs.ctaTitle")}</p>
              <p className="mt-1 text-sm text-ink-soft">{t("blogs.ctaBody")}</p>
            </div>
            <a href="mailto:hello@candway.tn" className={cn(careersBtn, "shrink-0")}>
              {t("blogs.ctaBtn")}
              <IconArrowRight className="h-4 w-4" />
            </a>
          </div>
        </Reveal>
      </section>
    </CareersShell>
  );
}