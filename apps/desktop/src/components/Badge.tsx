import React from 'react';
import clsx from 'clsx';

interface BadgeProps {
  label: string;
  color?: string;
  variant?: 'solid' | 'subtle' | 'outline';
  className?: string;
  icon?: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({
  label,
  color,
  variant = 'subtle',
  className,
  icon,
}) => {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 px-2 py-0.5 text-xs font-mono font-medium rounded-none border',
        variant === 'subtle' && 'bg-bg-elevated text-slate-300 border-border-muted',
        variant === 'outline' && 'border-border-muted text-slate-400 bg-transparent',
        className
      )}
      style={color ? { borderColor: `${color}60`, color: color } : undefined}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      <span className="truncate">{label}</span>
    </span>
  );
};
