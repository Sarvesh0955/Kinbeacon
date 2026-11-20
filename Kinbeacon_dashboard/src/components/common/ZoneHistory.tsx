import { ChevronRight } from 'lucide-react';
import type { ZoneHistoryEntry } from '../../api/types';

export function ZoneHistory({ entries = [] }: { entries?: ZoneHistoryEntry[] }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-slate-50 p-4" aria-label="Zone history">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-600">
        Zone history · Last 15 minutes
      </h3>
      {entries.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">No zone history available.</p>
      ) : (
        <ol className="mt-3 flex flex-wrap gap-x-2 gap-y-2" role="list">
          {entries.map((entry, index) => (
            <li key={`${entry.id}-${entry.minute_start}`} className="flex min-w-0 items-center gap-2">
              {index > 0 && <ChevronRight aria-hidden="true" className="h-4 w-4 shrink-0 text-slate-400" />}
              <div className="min-w-0 rounded-md border border-indigo-100 bg-white px-3 py-1.5">
                <span className="block break-words text-sm font-semibold text-slate-800">{entry.name}</span>
                <time dateTime={entry.minute_start} className="block text-xs text-slate-500">
                  {new Date(entry.minute_start).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}
                </time>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
