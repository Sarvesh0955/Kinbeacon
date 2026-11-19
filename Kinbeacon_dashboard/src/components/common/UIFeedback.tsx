import React from 'react';
import { AlertCircle, Loader2 } from 'lucide-react';

export const LoadingSpinner: React.FC<{ message?: string }> = ({ message = 'Loading...' }) => (
  <div className="flex flex-col items-center justify-center p-8 text-slate-500">
    <Loader2 className="w-8 h-8 animate-spin text-indigo-600 mb-2" />
    <span className="text-sm font-medium">{message}</span>
  </div>
);

export const ErrorBanner: React.FC<{ message: string; onRetry?: () => void }> = ({
  message,
  onRetry,
}) => (
  <div className="flex items-center justify-between p-4 mb-4 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-sm">
    <div className="flex items-center gap-2">
      <AlertCircle className="w-5 h-5 text-rose-600 shrink-0" />
      <span>{message}</span>
    </div>
    {onRetry && (
      <button
        onClick={onRetry}
        className="px-3 py-1 bg-white border border-rose-300 rounded shadow-sm text-xs font-semibold text-rose-700 hover:bg-rose-50"
      >
        Retry
      </button>
    )}
  </div>
);

export const EmptyState: React.FC<{
  title: string;
  description: string;
  actionText?: string;
  onAction?: () => void;
}> = ({ title, description, actionText, onAction }) => (
  <div className="text-center py-12 px-4 border-2 border-dashed border-slate-200 rounded-xl bg-white">
    <h3 className="text-base font-semibold text-slate-800">{title}</h3>
    <p className="text-sm text-slate-500 mt-1 max-w-sm mx-auto">{description}</p>
    {actionText && onAction && (
      <button
        onClick={onAction}
        className="mt-4 inline-flex items-center px-3.5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-medium shadow-sm transition-colors"
      >
        {actionText}
      </button>
    )}
  </div>
);

export const PageHeader: React.FC<{
  title: string;
  description?: string;
  children?: React.ReactNode;
}> = ({ title, description, children }) => (
  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-slate-200 mb-6">
    <div>
      <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{title}</h1>
      {description && <p className="text-sm text-slate-500 mt-1">{description}</p>}
    </div>
    {children && <div className="flex items-center gap-3">{children}</div>}
  </div>
);
