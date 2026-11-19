import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Plus, Watch, Search, Edit2, Trash2 } from 'lucide-react';
import {
  listDevices,
  createDevice,
  updateDevice,
  deleteDevice,
} from '../api/endpoints';
import { PageHeader, LoadingSpinner, EmptyState, ErrorBanner } from '../components/common/UIFeedback';
import { Modal, ConfirmDialog } from '../components/common/Modal';
import { StatusBadge } from '../components/common/StatusBadge';
import { Device } from '../api/types';
import { getErrorMessage } from '../api/client';
import toast from 'react-hot-toast';

export const DevicesPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [registerModalOpen, setRegisterModalOpen] = useState(false);
  const [editingDevice, setEditingDevice] = useState<Device | null>(null);
  const [deletingDeviceId, setDeletingDeviceId] = useState<string | null>(null);

  // Form states
  const [deviceId, setDeviceId] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [guardianRef, setGuardianRef] = useState('');
  const [status, setStatus] = useState('ACTIVE');
  const [metadataJson, setMetadataJson] = useState('{}');

  const { data: devices, isLoading, error } = useQuery({
    queryKey: ['devices'],
    queryFn: listDevices,
  });

  const createMutation = useMutation({
    mutationFn: createDevice,
    onSuccess: (dev) => {
      toast.success(`Device "${dev.device_id}" registered!`);
      queryClient.invalidateQueries({ queryKey: ['devices'] });
      setRegisterModalOpen(false);
      resetForm();
    },
    onError: (err) => {
      toast.error(`Registration failed: ${getErrorMessage(err)}`);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => updateDevice(id, data),
    onSuccess: (dev) => {
      toast.success(`Device "${dev.device_id}" updated!`);
      queryClient.invalidateQueries({ queryKey: ['devices'] });
      setEditingDevice(null);
    },
    onError: (err) => {
      toast.error(`Update failed: ${getErrorMessage(err)}`);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteDevice,
    onSuccess: () => {
      toast.success('Device removed (soft-deleted)');
      queryClient.invalidateQueries({ queryKey: ['devices'] });
      setDeletingDeviceId(null);
    },
    onError: (err) => {
      toast.error(`Delete failed: ${getErrorMessage(err)}`);
    },
  });

  const resetForm = () => {
    setDeviceId('');
    setDisplayName('');
    setGuardianRef('');
    setStatus('ACTIVE');
    setMetadataJson('{}');
  };

  const openEdit = (d: Device) => {
    setDeviceId(d.device_id);
    setDisplayName(d.display_name || '');
    setGuardianRef(d.guardian_ref || '');
    setStatus(d.status);
    setMetadataJson(JSON.stringify(d.metadata_json || {}, null, 2));
    setEditingDevice(d);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    let meta = {};
    try {
      meta = JSON.parse(metadataJson);
    } catch {
      toast.error('Invalid JSON for metadata');
      return;
    }

    if (editingDevice) {
      updateMutation.mutate({
        id: editingDevice.device_id,
        data: {
          display_name: displayName.trim() || null,
          guardian_ref: guardianRef.trim() || null,
          status,
          metadata_json: meta,
        },
      });
    } else {
      if (!deviceId.trim()) {
        toast.error('Device ID is required');
        return;
      }
      createMutation.mutate({
        device_id: deviceId.trim(),
        display_name: displayName.trim() || null,
        guardian_ref: guardianRef.trim() || null,
        status,
        metadata_json: meta,
      });
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Wearable Device Registry"
        description="Register and track BLE wearable wristbands, beacons, and companion mobile devices."
      >
        <button
          onClick={() => {
            resetForm();
            setRegisterModalOpen(true);
          }}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 shadow-sm transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span>Register Device</span>
        </button>
      </PageHeader>

      {error && <ErrorBanner message={getErrorMessage(error)} />}

      {isLoading ? (
        <LoadingSpinner message="Loading wearable devices..." />
      ) : !devices || devices.length === 0 ? (
        <EmptyState
          title="No Devices Registered"
          description="Register Bluetooth wearable device IDs to track them across venue zones."
          actionText="Register First Device"
          onAction={() => {
            resetForm();
            setRegisterModalOpen(true);
          }}
        />
      ) : (
        <div className="bg-white border border-slate-200/80 rounded-xl shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3">Device ID</th>
                  <th className="px-4 py-3">Display Name</th>
                  <th className="px-4 py-3">Guardian Ref</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Registered At</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {devices.map((d) => (
                  <tr key={d.device_id} className="hover:bg-slate-50/50">
                    <td className="px-4 py-3 font-mono font-semibold text-slate-900 flex items-center gap-2">
                      <Watch className="w-4 h-4 text-amber-500 shrink-0" />
                      <span>{d.device_id}</span>
                    </td>
                    <td className="px-4 py-3 font-medium text-slate-800">
                      {d.display_name || <span className="text-slate-400 italic">None</span>}
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-600 font-mono">
                      {d.guardian_ref || <span className="text-slate-400 italic">None</span>}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={d.status} />
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500">
                      {new Date(d.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="inline-flex items-center gap-2">
                        <Link
                          to={`/search?device_id=${encodeURIComponent(d.device_id)}`}
                          title="Locate device now"
                          className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded transition-colors"
                        >
                          <Search className="w-3.5 h-3.5" />
                          <span>Locate</span>
                        </Link>
                        <button
                          onClick={() => openEdit(d)}
                          title="Edit device"
                          className="p-1 text-slate-600 hover:text-indigo-600 hover:bg-indigo-50 rounded"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => setDeletingDeviceId(d.device_id)}
                          title="Delete device"
                          className="p-1 text-slate-600 hover:text-rose-600 hover:bg-rose-50 rounded"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Register/Edit Device Modal */}
      <Modal
        isOpen={registerModalOpen || !!editingDevice}
        onClose={() => {
          setRegisterModalOpen(false);
          setEditingDevice(null);
        }}
        title={editingDevice ? `Edit Device: ${editingDevice.device_id}` : 'Register New Device'}
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
              Device ID *
            </label>
            <input
              type="text"
              required
              disabled={!!editingDevice}
              value={deviceId}
              onChange={(e) => setDeviceId(e.target.value)}
              placeholder="e.g. KINBEACON-PHONE1 or kb-phone1"
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg font-mono focus:ring-2 focus:ring-indigo-500 disabled:bg-slate-100"
            />
            <p className="text-[11px] text-slate-500 mt-1">
              Exact BLE advertisement identifier or simulated beacon name.
            </p>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
              Display Name (Optional)
            </label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="e.g. Alice's Wristband"
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
              Guardian Reference (Optional)
            </label>
            <input
              type="text"
              value={guardianRef}
              onChange={(e) => setGuardianRef(e.target.value)}
              placeholder="e.g. Parent Contact / Guardian Ref"
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 font-mono"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
              Status
            </label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            >
              <option value="ACTIVE">ACTIVE</option>
              <option value="INACTIVE">INACTIVE</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
              Metadata JSON (Optional)
            </label>
            <textarea
              rows={3}
              value={metadataJson}
              onChange={(e) => setMetadataJson(e.target.value)}
              className="w-full p-2 font-mono text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => {
                setRegisterModalOpen(false);
                setEditingDevice(null);
              }}
              className="px-3 py-2 text-sm text-slate-600 hover:text-slate-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending || updateMutation.isPending}
              className="px-4 py-2 text-sm font-semibold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              {createMutation.isPending || updateMutation.isPending ? 'Saving...' : 'Save Device'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Delete Confirmation */}
      <ConfirmDialog
        isOpen={!!deletingDeviceId}
        title="Remove Wearable Device"
        message={`Are you sure you want to remove device "${deletingDeviceId}"? It will be marked INACTIVE.`}
        confirmText="Remove Device"
        isDestructive={true}
        onConfirm={() => deletingDeviceId && deleteMutation.mutate(deletingDeviceId)}
        onCancel={() => setDeletingDeviceId(null)}
      />
    </div>
  );
};
