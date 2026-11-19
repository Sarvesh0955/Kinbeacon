import React from 'react';

interface Props {
  status: string;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<Props> = ({ status, size = 'sm' }) => {
  const s = (status || '').toUpperCase();

  let colorClasses = 'bg-slate-100 text-slate-700 border-slate-200';

  if (s === 'UP' || s === 'ACTIVE' || s === 'COMPLETED' || s === 'OK') {
    colorClasses = 'bg-emerald-50 text-emerald-700 border-emerald-200';
  } else if (s === 'DEGRADED' || s === 'PARTIAL' || s === 'MEDIUM') {
    colorClasses = 'bg-amber-50 text-amber-700 border-amber-200';
  } else if (s === 'DOWN' || s === 'FAILED' || s === 'INACTIVE' || s === 'TIMEOUT' || s === 'ERROR') {
    colorClasses = 'bg-rose-50 text-rose-700 border-rose-200';
  } else if (s === 'RUNNING') {
    colorClasses = 'bg-sky-50 text-sky-700 border-sky-200 animate-pulse';
  }

  const px = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm';

  return (
    <span className={`inline-flex items-center font-medium rounded-full border ${px} ${colorClasses}`}>
      <span className="w-1.5 h-1.5 rounded-full mr-1.5 bg-current opacity-70"></span>
      {s}
    </span>
  );
};
