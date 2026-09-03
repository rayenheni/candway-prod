import { useEffect, useMemo } from "react";
import { useNavigate, useParams } from "react-router";
import { cn } from "../../../utils/cn";
import { useLanguage } from "../../../contexts/language-context";
import { CareersShell, IconArrowLeft, IconClock } from "./public-jobs";
import {
  IconArrowRight,
  IconCheck,
  IconMail,
  IconSpark,
  Reveal,
} from "./candway-landing";
import { CATEGORY_STYLE, POSTS, type Block, type Cover, type Post } from "../data/blog-content";

/* ------------------------------------------------------------------ */
/*  Block renderer                                                     */
/* ------------------------------------------------------------------ */

function CalloutIcon() {
  return <IconSpark className="h-5 w-5 shrink-0 text-primary-600" />;
}

function BlockView({ block }: { block: Block }) {
  switch (block.k) {
    case "p":
      return <p className="text-[16px] leading-[1.85] text-ink-soft">{block.t}</p>;
    case "h2":
      return (
        <h2 className="pt-4 text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
          {block.t}
        </h2>
      );
    case "h3":
      return <h3 className="pt-2 text-lg font-semibold tracking-tight text-ink">{block.t}</h3>;
    case "ul":
      return (
        <ul className="space-y-2.5">
          {block.items.map((item, i) => (
            <li key={i} className="flex items-start gap-3 text-[15px] leading-relaxed text-ink-soft">
              <span className="mt-1.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-primary-500/12 text-primary-700">
                <IconCheck className="h-3 w-3" />
              </span>
              {item}
            </li>
          ))}
        </ul>
      );
    case "ol":
      return (
        <ol className="space-y-3">
          {block.items.map((item, i) => (
            <li key={i} className="flex items-start gap-3 text-[15px] leading-relaxed text-ink-soft">
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-gradient-to-br from-primary-500 to-indigo-500 text-xs font-bold text-white">
                {i + 1}
              </span>
              {item}
            </li>
          ))}
        </ol>
      );
    case "quote":
      return (
        <blockquote className="relative rounded-2xl border-l-4 border-primary-400 bg-white/80 px-6 py-5 pl-7 italic text-ink shadow-sm">
          <span
            className="absolute -left-2 -top-3 select-none text-6xl font-serif text-primary-300"
            aria-hidden
          >
            “
          </span>
          {block.t}
        </blockquote>
      );
    case "callout":
      return (
        <div className="flex gap-4 rounded-2xl border border-primary-200/70 bg-gradient-to-br from-primary-50 to-lilac-100/60 px-6 py-5">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white text-primary-600 shadow-sm">
            <CalloutIcon />
          </span>
          <div>
            <p className="text-sm font-semibold text-ink">{block.title}</p>
            <p className="mt-1 text-sm leading-relaxed text-ink-soft">{block.t}</p>
          </div>
        </div>
      );
    case "rubric": {
      const max = Math.max(...block.rows.map(([, w]) => w));
      return (
        <div className="overflow-hidden rounded-2xl border border-ink/10 bg-white/85 shadow-sm">
          <p className="border-b border-ink/8 bg-white/70 px-5 py-3 text-sm font-semibold text-ink">
            {block.title}
          </p>
          <div className="divide-y divide-ink/6">
            {block.rows.map(([label, weight]) => (
              <div key={label} className="flex items-center gap-4 px-5 py-3.5">
                <span className="w-48 shrink-0 text-sm font-medium text-ink">{label}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-ink/8">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-primary-500 to-indigo-500"
                    style={{ width: `${Math.round((weight / max) * 100)}%` }}
                  />
                </div>
                <span className="w-10 shrink-0 text-right text-sm font-bold text-primary-700">
                  {weight}%
                </span>
              </div>
            ))}
          </div>
        </div>
      );
    }
    case "compare": {
      const [left, right] = [block.left, block.right];
      return (
        <div className="grid gap-4 sm:grid-cols-2">
          {[
            { title: left[0], items: left[1], tone: "border-ink/10 bg-white/70" },
            {
              title: right[0],
              items: right[1],
              tone: "border-primary-300/60 bg-gradient-to-br from-primary-50 to-lilac-100/70",
            },
          ].map(({ title, items, tone }, i) => (
            <div key={title} className={cn("rounded-2xl border p-5", tone)}>
              <p className="text-sm font-semibold text-ink">{i === 0 ? "✕" : "✓"} {title}</p>
              <ul className="mt-3 space-y-2">
                {items.map((item, j) => (
                  <li
                    key={j}
                    className={cn(
                      "flex items-start gap-2 text-[13px] leading-relaxed",
                      i === 0 ? "text-ink-soft" : "text-ink"
                    )}
                  >
                    <span className="mt-1 text-xs">{i === 0 ? "—" : "•"}</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      );
    }
    default:
      return null;
  }
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

const careersBtn =
  "inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-primary-600/30 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-xl hover:shadow-primary-600/35 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600";

const COVER_GRADIENT: Record<Cover, string> = {
  score: "from-violet-500 to-fuchsia-400",
  lock: "from-sky-500 to-indigo-400",
  rubric: "from-emerald-500 to-teal-400",
  candidate: "from-amber-500 to-orange-400",
  campaign: "from-rose-500 to-primary-500",
  report: "from-primary-500 to-indigo-500",
};

const COVER_MARK: Record<Cover, string> = {
  score: "∑",
  lock: "§",
  rubric: "✓",
  candidate: "◆",
  campaign: "✉",
  report: "≡",
};

export default function BlogDetailPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const { slug = "" } = useParams<{ slug: string }>();

  const post = useMemo<Post | undefined>(() => POSTS.find((p) => p.slug === slug), [slug]);

  useEffect(() => {
    if (post) document.title = `${post.title} · Candway Blog`;
  }, [post]);

  const related = useMemo(
    () => (post ? POSTS.filter((p) => p.slug !== post.slug && p.category === post.category).slice(0, 3) : []),
    [post]
  );

  const goBack = () => navigate("/blogs");

  if (!post) {
    return (
      <CareersShell onBack={goBack} title={t("blogs.backToBlog")} badge={t("blogs.badge")}>
        <div className="mx-auto max-w-xl px-5 py-20 text-center">
          <h1 className="text-3xl font-semibold tracking-tight text-ink">{t("blogs.notFoundTitle")}</h1>
          <p className="mt-3 text-sm text-ink-soft">{t("blogs.notAvailable")}</p>
          <button
            type="button"
            onClick={goBack}
            className="mt-6 inline-flex items-center gap-2 rounded-xl border border-ink/10 bg-white/75 px-5 py-3 text-sm font-semibold text-ink transition-all hover:-translate-y-0.5 hover:border-primary-300 hover:text-primary-700"
          >
            <IconArrowLeft className="h-4 w-4" />
            {t("blogs.backToBlog")}
          </button>
        </div>
      </CareersShell>
    );
  }

  const author = post.author;

  return (
    <CareersShell onBack={goBack} title={t("blogs.backToBlog")} badge={t("blogs.badge")}>
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
        <div className="relative mx-auto max-w-6xl px-5 pb-10 pt-12 sm:px-8 md:pt-16">
          <div className="mx-auto max-w-3xl">
            <button
              type="button"
              onClick={goBack}
              className="flex items-center gap-1.5 text-sm font-semibold text-ink-soft transition-colors hover:text-ink"
            >
              <IconArrowLeft className="h-4 w-4" />
              {t("blogs.backToBlog")}
            </button>

            <span
              className={cn(
                "mt-6 inline-flex rounded-full border px-3 py-1.5 text-[12px] font-semibold",
                CATEGORY_STYLE[post.category]
              )}
            >
              {post.category}
            </span>

            <h1 className="mt-4 text-4xl font-semibold leading-[1.06] tracking-[-0.025em] text-ink sm:text-5xl">
              {post.title}
            </h1>
            <p className="mt-4 text-base leading-relaxed text-ink-soft sm:text-lg">{post.dek}</p>

            <div className="mt-6 flex flex-wrap items-center gap-4 text-[13px] font-medium text-ink-soft">
              <span className="flex items-center gap-2">
                <span
                  className={cn(
                    "grid h-9 w-9 place-items-center rounded-full bg-gradient-to-br text-xs font-bold text-white",
                    author.gradient
                  )}
                >
                  {author.initials}
                </span>
                <span className="flex flex-col">
                  <span className="text-sm font-semibold text-ink">{author.name}</span>
                  <span className="text-[12px] text-ink-faint">{author.role}</span>
                </span>
              </span>
              <span className="flex items-center gap-1.5">
                <IconClock className="h-3.5 w-3.5 text-primary-600" />
                {post.read} min · {post.date}
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* body */}
      <section className="mx-auto max-w-6xl px-5 pb-20 sm:px-8">
        <div className="mx-auto max-w-3xl">
          <Reveal>
            <div className="mb-10 overflow-hidden rounded-3xl shadow-[0_30px_70px_-30px_rgba(108,57,232,0.4)]">
              <div className="relative h-64 sm:h-80">
                <div className="absolute inset-0">
                  {/* decorative cover background */}
                  <div className="absolute inset-0 bg-gradient-to-br from-primary-500 via-indigo-500 to-violet-600" />
                  <div className="cw-dots absolute inset-0 opacity-15 invert" aria-hidden />
                  <div className="absolute -right-10 -top-14 h-56 w-56 rounded-full bg-white/15 blur-3xl" aria-hidden />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="flex items-center gap-3 rounded-2xl bg-white/15 px-5 py-3 text-white backdrop-blur-md">
                      <IconSpark className="h-5 w-5" />
                      <span className="text-sm font-bold tracking-wide">{post.category}</span>
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </Reveal>

          <div className="space-y-6">
            {post.body.map((block, i) => (
              <Reveal key={i} delay={i * 30}>
                <BlockView block={block} />
              </Reveal>
            ))}
          </div>

          {/* author card */}
          <Reveal>
            <div className="cw-glass-strong mt-10 flex items-center gap-4 rounded-3xl p-6">
              <span
                className={cn(
                  "grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-gradient-to-br text-base font-bold text-white",
                  author.gradient
                )}
              >
                {author.initials}
              </span>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
                  {t("blogs.writtenBy")}
                </p>
                <p className="text-sm font-semibold text-ink">{author.name}</p>
                <p className="text-[13px] text-ink-soft">{author.role}</p>
              </div>
            </div>
          </Reveal>

          {/* CTA */}
          <Reveal delay={80}>
            <div className="mt-10 flex flex-col items-center justify-between gap-4 rounded-3xl border border-primary-200/60 bg-gradient-to-br from-white via-primary-50 to-lilac-100 px-6 py-7 text-center sm:flex-row sm:text-left">
              <div>
                <p className="text-base font-semibold text-ink">{t("blogs.ctaTitle")}</p>
                <p className="mt-1 text-sm text-ink-soft">{t("blogs.ctaBody")}</p>
              </div>
              <a href="mailto:hello@candway.tn" className={cn(careersBtn, "shrink-0")}>
                {t("blogs.ctaBtn")}
                <IconMail className="h-4 w-4" />
              </a>
            </div>
          </Reveal>
        </div>
      </section>

      {/* related */}
      {related.length > 0 && (
        <section className="border-t border-ink/8 bg-white/50 py-14">
          <div className="mx-auto max-w-6xl px-5 sm:px-8">
            <h2 className="text-xl font-semibold tracking-tight text-ink">{t("blogs.relatedTitle")}</h2>
            <div className="mt-6 grid gap-5 md:grid-cols-3">
              {related.map((p) => (
                <button
                  key={p.slug}
                  type="button"
                  onClick={() => navigate(`/blog/${p.slug}`)}
                  className="cw-glass cw-lift group flex flex-col overflow-hidden rounded-3xl text-left"
                >
                  <div className="h-32 overflow-hidden">
                    <div className={cn("relative h-full w-full bg-gradient-to-br", COVER_GRADIENT[p.cover])}>
                      <div className="cw-dots absolute inset-0 opacity-20 invert" aria-hidden />
                      <span className="absolute inset-0 flex items-center justify-center text-2xl font-bold text-white/80">
                        {COVER_MARK[p.cover]}
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-1 flex-col p-5">
                    <span className={cn("inline-flex w-fit rounded-full border px-2 py-0.5 text-[10px] font-semibold", CATEGORY_STYLE[p.category])}>
                      {p.category}
                    </span>
                    <h3 className="mt-2.5 text-[15px] font-semibold leading-snug tracking-tight text-ink line-clamp-2 group-hover:text-primary-700">
                      {p.title}
                    </h3>
                    <span className="mt-3 flex items-center gap-1.5 text-[13px] font-semibold text-primary-700">
                      {t("blogs.readArticle")}
                      <IconArrowRight className="h-3.5 w-3.5 transition-transform duration-300 group-hover:translate-x-1" />
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </section>
      )}
    </CareersShell>
  );
}