// ============================================================
// SVG Flag Components for UK (GB) and France (FR)
// Windows Chrome does not render emoji flags natively.
// ============================================================

interface FlagProps {
  className?: string;
}

export function GBFlag({ className = "w-5 h-3.5" }: FlagProps) {
  return (
    <svg className={`inline-block rounded-xs shadow-xs border border-black/10 dark:border-white/20 shrink-0 ${className}`} viewBox="0 0 640 480" xmlns="http://www.w3.org/2000/svg">
      <path fill="#012169" d="M0 0h640v480H0z"/>
      <path fill="#fff" d="m75 0 245 180L565 0h75v55L415 240l225 185v55h-75L320 300 75 480H0v-55l225-185L0 55V0h75z"/>
      <path fill="#C8102E" d="m424 288 216 177h-47L396 303l28-15zm-208-96L0 15h47l197 162-28 15zM0 465l216-177 28 15L28 480H0v-15zm640-450L424 192l-28-15L612 0h28v15z"/>
      <path fill="#fff" d="M240 0v480h160V0H240zM0 160v160h640V160H0z"/>
      <path fill="#C8102E" d="M0 192v96h640v-96H0zM272 0v480h96V0h-96z"/>
    </svg>
  );
}

export function FRFlag({ className = "w-5 h-3.5" }: FlagProps) {
  return (
    <svg className={`inline-block rounded-xs shadow-xs border border-black/10 dark:border-white/20 shrink-0 ${className}`} viewBox="0 0 640 480" xmlns="http://www.w3.org/2000/svg">
      <g fillRule="evenodd" strokeWidth="1pt">
        <path fill="#fff" d="M0 0h640v480H0z"/>
        <path fill="#051440" d="M0 0h213.3v480H0z"/>
        <path fill="#e41b13" d="M426.7 0H640v480H426.7z"/>
      </g>
    </svg>
  );
}
