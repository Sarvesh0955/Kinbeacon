import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Modal } from '../common/Modal';
import { getApiKey, setApiKey } from '../../api/client';
import toast from 'react-hot-toast';

export const Layout: React.FC = () => {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState(getApiKey() || '');

  const handleSaveApiKey = (e: React.FormEvent) => {
    e.preventDefault();
    setApiKey(apiKeyInput.trim() || null);
    toast.success('API Key configuration updated');
    setSettingsOpen(false);
  };

  return (
    <div className="flex min-h-screen bg-slate-100/70 text-slate-900">
      <Sidebar onOpenSettings={() => setSettingsOpen(true)} />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <main className="flex-1 p-6 md:p-8 max-w-7xl w-full mx-auto overflow-y-auto">
          <Outlet />
        </main>
      </div>

      <Modal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        title="Settings & Authentication"
      >
        <form onSubmit={handleSaveApiKey} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
              X-API-Key Header (Optional)
            </label>
            <input
              type="text"
              value={apiKeyInput}
              onChange={(e) => setApiKeyInput(e.target.value)}
              placeholder="Leave blank for development mode"
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono"
            />
            <p className="text-xs text-slate-500 mt-1.5">
              Only required if backend is configured with <code>API_KEY</code> environment variable.
            </p>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setSettingsOpen(false)}
              className="px-3 py-2 text-sm text-slate-600 hover:text-slate-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 shadow-sm"
            >
              Save Key
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
