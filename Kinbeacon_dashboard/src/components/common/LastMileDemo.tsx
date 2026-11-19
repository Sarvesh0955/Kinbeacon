import { useQuery } from '@tanstack/react-query';

type DemoState = {
  incident: {
    incident_id: number;
    mode: 'lan' | 'ble';
    status: 'searching' | 'located' | 'timed_out' | 'reunited';
    zone: string;
    result: { landmark: string; radius_m: number; source: 'simulated' | 'ble' } | null;
  } | null;
  anchor_sighting: { rssi: number; seen_at: number } | null;
};

const labels = {
  searching: 'Searching',
  located: 'Located',
  timed_out: 'No BLE result',
  reunited: 'Reunited',
};

export function LastMileDemo() {
  const { data, isError, isPending } = useQuery({
    queryKey: ['last-mile-demo'],
    refetchInterval: 1000,
    retry: false,
    queryFn: async ({ signal }): Promise<DemoState> => {
      const response = await fetch('/api/v1/demo/state', { signal, cache: 'no-store' });
      if (!response.ok) throw new Error('Demo server unavailable');
      return response.json();
    },
  });
  const incident = data?.incident;
  const result = incident?.result;
  const sighting = data?.anchor_sighting;

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-600">
      <h2 className="mb-2 text-base font-semibold text-slate-900">Last-Mile Demo</h2>
      {isError ? <p>Demo server unavailable</p> : (
        <>
          <p>{incident
            ? `${labels[incident.status]} · ${incident.mode === 'lan' ? 'LAN rehearsal' : 'Live BLE'} · ${incident.zone} · #${incident.incident_id}`
            : isPending ? 'Checking demo state…' : 'No active demo incident'}</p>
          {result && (
            <p>{result.landmark} · {result.radius_m} m radius · {result.source === 'simulated' ? 'Simulated' : 'BLE uplink'}</p>
          )}
          <p className="mt-2 text-slate-500">{sighting
            ? `Anchor heard wearable at ${new Date(sighting.seen_at * 1000).toLocaleTimeString()} · ${sighting.rssi} dBm`
            : 'No recent anchor sighting'}</p>
        </>
      )}
    </section>
  );
}
