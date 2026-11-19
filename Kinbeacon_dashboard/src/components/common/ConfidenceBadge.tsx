import React from 'react';

interface Props {
  confidence: number;
  label?: string;
}

export const ConfidenceBadge: React.FC<Props> = ({ confidence, label }) => {
  const score = Math.round(confidence * 100);
  const lbl = (label || (confidence >= 0.7 ? 'HIGH' : confidence >= 0.4 ? 'MEDIUM' : 'LOW')).toUpperCase();

  let colorClasses = 'bg-rose-50 text-rose-700 border-rose-200';
  if (lbl === 'HIGH' || confidence >= 0.7) {
    colorClasses = 'bg-emerald-50 text-emerald-700 border-emerald-200';
  } else if (lbl === 'MEDIUM' || confidence >= 0.4) {
    colorClasses = 'bg-amber-50 text-amber-700 border-amber-200';
  }

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-full border ${colorClasses}`}>
      <span>{lbl}</span>
      <span className="opacity-70 font-mono">({score}%)</span>
    </span>
  );
};
