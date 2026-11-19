import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  MapPin,
  Radio,
  Watch,
  Search,
  History,
  Activity,
  KeyRound,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { getServerHealth } from '../../api/endpoints';

interface Props {
  onOpenSettings: () => void;
}

export const Sidebar: React.FC<Props> = ({ onOpenSettings }) => {
  const { data: serverHealth } = useQuery({
    queryKey: ['server-health'],
    queryFn: getServerHealth,
    refetchInterval: 15000,
    retry: false,
  });

  const isOnline = serverHealth?.status === 'ok';

  const navItems = [
    { to: '/', label: 'Overview', icon: LayoutDashboard },
    { to: '/search', label: 'Device Search', icon: Search },
    { to: '/zones', label: 'Zones', icon: MapPin },
    { to: '/anchors', label: 'Anchors', icon: Radio },
    { to: '/devices', label: 'Devices', icon: Watch },
    { to: '/history', label: 'Search History', icon: History },
    { to: '/fleet', label: 'Fleet Health', icon: Activity },
  ];

  return (
    <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col shrink-0 h-screen sticky top-0 border-r border-slate-800">
      {/* Brand Header */}
      <div className="h-16 px-6 flex items-center justify-between border-b border-slate-800">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-lg shadow-md shadow-indigo-500/20">
            K
          </div>
          <div>
            <div className="font-bold text-slate-100 tracking-tight leading-none text-base">KinBeacon</div>
            <div className="text-[10px] text-slate-400 font-mono tracking-wider uppercase mt-0.5">Central Server</div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <div className="px-3 pb-2 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
          Navigation
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-indigo-600 text-white font-semibold shadow-sm'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60'
                }`
              }
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Footer / Server Status */}
      <div className="p-4 border-t border-slate-800 bg-slate-900/50">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                isOnline ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'
              }`}
            />
            <span className="text-xs font-medium text-slate-300">
              {isOnline ? 'Server Online' : 'Server Offline'}
            </span>
          </div>
          <button
            onClick={onOpenSettings}
            title="Configure API Key"
            className="text-slate-400 hover:text-slate-200 transition-colors p-1"
          >
            <KeyRound className="w-4 h-4" />
          </button>
        </div>
        <div className="text-[11px] text-slate-400 truncate">
          {serverHealth?.app || 'KinBeacon Central'} {serverHealth?.version ? `v${serverHealth.version}` : ''}
        </div>
      </div>
    </aside>
  );
};
