import { useState } from 'react';
import { cn } from '@/utils/cn';

const GRADIENTS = [
  'from-purple-600 to-indigo-600',
  'from-indigo-500 to-cyan-500',
  'from-fuchsia-500 to-purple-600',
  'from-amber-500 to-orange-600',
  'from-emerald-500 to-teal-600',
  'from-rose-500 to-pink-600',
  'from-sky-500 to-blue-600',
];

interface CompanyLogoProps {
  name?: string | null;
  src?: string | null;
  size?: number;
  rounded?: string;
  className?: string;
}

export default function CompanyLogo({
  name,
  src,
  size = 12,
  rounded = 'rounded-xl',
  className,
}: CompanyLogoProps) {
  const [failed, setFailed] = useState(false);
  const base = name || 'Company';
  const initials = base
    .split(/\s+/)
    .map((word) => word.charAt(0))
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase();
  const gradient = GRADIENTS[(base.length || 0) % GRADIENTS.length];
  const showImage = !!src && !failed;

  return (
    <div
      className={cn('relative flex shrink-0 select-none items-center justify-center overflow-hidden', rounded, className)}
      style={{ width: size * 4, height: size * 4 }}
    >
      {showImage ? (
        <img
          src={src}
          alt={base}
          loading="lazy"
          onError={() => setFailed(true)}
          className="h-full w-full object-cover"
        />
      ) : (
        <div
          className={cn('flex h-full w-full items-center justify-center bg-gradient-to-tr font-bold text-white', gradient)}
          style={{ fontSize: Math.max(10, size * 1.5) }}
        >
          {initials || '?'}
        </div>
      )}
    </div>
  );
}
