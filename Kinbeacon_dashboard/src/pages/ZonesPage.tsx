import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, MapPin, Radio, GitCommit } from 'lucide-react';
import { listZones, createZone, listAnchors } from '../api/endpoints';
import { PageHeader, LoadingSpinner, EmptyState, ErrorBanner } from '../components/common/UIFeedback';
import { Modal } from '../components/common/Modal';
import { Zone } from '../api/types';
import { getErrorMessage } from '../api/client';
import toast from 'react-hot-toast';

export const ZonesPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [selectedZone, setSelectedZone] = useState<Zone | null>(null);

  // Form state
  const [idInput, setIdInput] = useState('');
  const [nameInput, setNameInput] = useState('');
  const [centroidX, setCentroidX] = useState('0.0');
  const [centroidY, setCentroidY] = useState('0.0');
  const [adjacentTo, setAdjacentTo] = useState<number[]>([]);
  const [metadataJson, setMetadataJson] = useState('{}');

  const { data: zones, isLoading, error } = useQuery({
    queryKey: ['zones'],
    queryFn: listZones,
  });

  const { data: anchors } = useQuery({
    queryKey: ['anchors'],
    queryFn: listAnchors,
  });

  const createMutation = useMutation({
    mutationFn: createZone,
    onSuccess: (newZone) => {
      toast.success(`Zone "${newZone.name}" created!`);
      queryClient.invalidateQueries({ queryKey: ['zones'] });
      setCreateModalOpen(false);
      resetForm();
    },
    onError: (err) => {
      toast.error(`Failed to create zone: ${getErrorMessage(err)}`);
    },
  });

  const resetForm = () => {
    setIdInput('');
    setNameInput('');
    setCentroidX('0.0');
    setCentroidY('0.0');
    setAdjacentTo([]);
    setMetadataJson('{}');
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!nameInput.trim()) {
      toast.error('Zone name is required');
      return;
    }

    let meta = {};
    try {
      meta = JSON.parse(metadataJson);
    } catch {
      toast.error('Invalid JSON for metadata');
      return;
    }

    createMutation.mutate({
      id: idInput ? parseInt(idInput, 10) : undefined,
      name: nameInput.trim(),
      centroid_x: parseFloat(centroidX) || 0.0,
      centroid_y: parseFloat(centroidY) || 0.0,
      adjacent_to: adjacentTo,
      metadata_json: meta,
    });
  };

  const toggleAdjacent = (zoneId: number) => {
    setAdjacentTo((prev) =>
      prev.includes(zoneId) ? prev.filter((id) => id !== zoneId) : [...prev, zoneId]
    );
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Venue Zones"
        description="Define physical areas, centroids, and zone adjacency graph for localization and search expansion."
      >
        <button
          onClick={() => {
            resetForm();
            setCreateModalOpen(true);
          }}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 shadow-sm transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span>Add Zone</span>
        </button>
      </PageHeader>

      {error && <ErrorBanner message={getErrorMessage(error)} />}

      {isLoading ? (
        <LoadingSpinner message="Loading venue zones..." />
      ) : !zones || zones.length === 0 ? (
        <EmptyState
          title="No Zones Configured"
          description="Create venue zones to represent physical areas (e.g., Rooms, Corridors, Hallways) where anchors reside."
          actionText="Create First Zone"
          onAction={() => setCreateModalOpen(true)}
        />
      ) : (
        <div className="bg-white border border-slate-200/80 rounded-xl shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3">Zone ID</th>
                  <th className="px-4 py-3">Zone Name</th>
                  <th className="px-4 py-3">Centroid (X, Y)</th>
                  <th className="px-4 py-3">Adjacent Zones</th>
                  <th className="px-4 py-3">Assigned Anchors</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {zones.map((zone) => {
                  const zoneAnchors = anchors?.filter((a) => a.zone_id === zone.id) || [];
                  return (
                    <tr
                      key={zone.id}
                      className="hover:bg-slate-50/60 cursor-pointer transition-colors"
                      onClick={() => setSelectedZone(zone)}
                    >
                      <td className="px-4 py-3 font-mono font-semibold text-slate-900">
                        #{zone.id}
                      </td>
                      <td className="px-4 py-3 font-medium text-slate-900 flex items-center gap-2">
                        <MapPin className="w-4 h-4 text-indigo-500 shrink-0" />
                        <span>{zone.name}</span>
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-600 text-xs">
                        ({zone.centroid_x.toFixed(1)}m, {zone.centroid_y.toFixed(1)}m)
                      </td>
                      <td className="px-4 py-3">
                        {zone.adjacent_zone_ids.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {zone.adjacent_zone_ids.map((adjId) => (
                              <span
                                key={adjId}
                                className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 text-xs font-mono font-medium"
                              >
                                #{adjId}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400 italic">None</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-indigo-50 text-indigo-700">
                          <Radio className="w-3 h-3" />
                          {zoneAnchors.length} anchor{zoneAnchors.length !== 1 ? 's' : ''}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedZone(zone);
                          }}
                          className="text-xs font-semibold text-indigo-600 hover:text-indigo-800"
                        >
                          View Details
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Create Zone Modal */}
      <Modal
        isOpen={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        title="Create New Venue Zone"
        maxWidth="max-w-lg"
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                Zone ID (Optional)
              </label>
              <input
                type="number"
                value={idInput}
                onChange={(e) => setIdInput(e.target.value)}
                placeholder="Auto"
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 font-mono"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                Zone Name *
              </label>
              <input
                type="text"
                required
                value={nameInput}
                onChange={(e) => setNameInput(e.target.value)}
                placeholder="e.g. Zone 1 - East Lobby"
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                Centroid X (meters)
              </label>
              <input
                type="number"
                step="0.1"
                value={centroidX}
                onChange={(e) => setCentroidX(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg font-mono focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                Centroid Y (meters)
              </label>
              <input
                type="number"
                step="0.1"
                value={centroidY}
                onChange={(e) => setCentroidY(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg font-mono focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>

          {/* Adjacency Selection */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
              Adjacent Zones (Graph Topology)
            </label>
            {zones && zones.length > 0 ? (
              <div className="flex flex-wrap gap-2 max-h-28 overflow-y-auto p-2 border border-slate-200 rounded-lg bg-slate-50">
                {zones.map((z) => (
                  <button
                    type="button"
                    key={z.id}
                    onClick={() => toggleAdjacent(z.id)}
                    className={`px-2.5 py-1 rounded text-xs font-medium border transition-colors ${
                      adjacentTo.includes(z.id)
                        ? 'bg-indigo-600 text-white border-indigo-600'
                        : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-100'
                    }`}
                  >
                    #{z.id} {z.name}
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400 italic">No existing zones to link.</p>
            )}
            <p className="text-[11px] text-slate-500 mt-1">
              Used for stale search area expansion and conflict resolution.
            </p>
          </div>

          {/* Metadata JSON */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
              Metadata JSON (Optional)
            </label>
            <textarea
              rows={3}
              value={metadataJson}
              onChange={(e) => setMetadataJson(e.target.value)}
              className="w-full p-2 font-mono text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              placeholder="{}"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setCreateModalOpen(false)}
              className="px-3 py-2 text-sm text-slate-600 hover:text-slate-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="px-4 py-2 text-sm font-semibold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              {createMutation.isPending ? 'Creating...' : 'Create Zone'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Zone Details Modal */}
      {selectedZone && (
        <Modal
          isOpen={!!selectedZone}
          onClose={() => setSelectedZone(null)}
          title={`Zone Details: ${selectedZone.name}`}
          maxWidth="max-w-lg"
        >
          <div className="space-y-4 text-sm">
            <div className="grid grid-cols-2 gap-3 p-3 bg-slate-50 rounded-lg border border-slate-100">
              <div>
                <span className="text-xs text-slate-500 block">Zone ID</span>
                <span className="font-mono font-bold text-slate-900">#{selectedZone.id}</span>
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Centroid Coordinates</span>
                <span className="font-mono text-slate-900">
                  X: {selectedZone.centroid_x}m, Y: {selectedZone.centroid_y}m
                </span>
              </div>
            </div>

            <div>
              <h4 className="text-xs font-bold uppercase text-slate-600 mb-2 flex items-center gap-1.5">
                <GitCommit className="w-3.5 h-3.5 text-indigo-500" />
                Adjacent Zones
              </h4>
              {selectedZone.adjacent_zone_ids.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {selectedZone.adjacent_zone_ids.map((adjId) => {
                    const match = zones?.find((z) => z.id === adjId);
                    return (
                      <span
                        key={adjId}
                        className="px-2.5 py-1 bg-slate-100 text-slate-800 font-mono text-xs rounded border border-slate-200"
                      >
                        #{adjId} {match ? `(${match.name})` : ''}
                      </span>
                    );
                  })}
                </div>
              ) : (
                <p className="text-xs text-slate-400 italic">No adjacent zones configured</p>
              )}
            </div>

            <div>
              <h4 className="text-xs font-bold uppercase text-slate-600 mb-2 flex items-center gap-1.5">
                <Radio className="w-3.5 h-3.5 text-indigo-500" />
                Anchors in this Zone
              </h4>
              {(() => {
                const zoneAnchors = anchors?.filter((a) => a.zone_id === selectedZone.id) || [];
                return zoneAnchors.length > 0 ? (
                  <div className="space-y-1.5">
                    {zoneAnchors.map((a) => (
                      <div
                        key={a.anchor_id}
                        className="p-2 border border-slate-200 rounded-lg flex items-center justify-between text-xs"
                      >
                        <span className="font-mono font-semibold text-slate-800">{a.anchor_id}</span>
                        <span className="text-slate-500 font-mono">{a.base_url}</span>
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                            a.health_state === 'UP'
                              ? 'bg-emerald-100 text-emerald-800'
                              : 'bg-rose-100 text-rose-800'
                          }`}
                        >
                          {a.health_state}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 italic">No anchors assigned to this zone</p>
                );
              })()}
            </div>

            <div>
              <h4 className="text-xs font-bold uppercase text-slate-600 mb-1">Metadata</h4>
              <pre className="p-3 bg-slate-900 text-slate-100 text-xs rounded-lg font-mono overflow-x-auto">
                {JSON.stringify(selectedZone.metadata_json, null, 2)}
              </pre>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
