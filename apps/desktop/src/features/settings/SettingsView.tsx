import React, { useState, useEffect } from 'react';
import {
  Settings as SettingsIcon,
  Shield,
  HardDrive,
  Trash2,
  Plus,
  RefreshCw,
  Sparkles,
  Bot,
  AlertTriangle,
  FolderOpen,
  Mail,
  Server,
  Key,
  ExternalLink
} from 'lucide-react';
import { api } from '../../api/client';
import { Account, AppSettings, ProtectionRule } from '../../types/api';
import { Button } from '../../components/Button';
import { Modal } from '../../components/Modal';

export const SettingsView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'accounts' | 'privacy' | 'protection' | 'ai'>('accounts');

  // Accounts state
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loadingAccounts, setLoadingAccounts] = useState<boolean>(true);
  const [addAccountModal, setAddAccountModal] = useState<boolean>(false);
  const [selectedProvider, setSelectedProvider] = useState<'gmail' | 'imap' | 'synthetic' | 'mbox'>('gmail');
  const [syntheticCount, setSyntheticCount] = useState<number>(50);
  const [mboxPath, setMboxPath] = useState<string>('');
  const [loadingCreate, setLoadingCreate] = useState<boolean>(false);

  // Gmail / IMAP state
  const [imapEmail, setImapEmail] = useState<string>('');
  const [imapPassword, setImapPassword] = useState<string>('');
  const [imapHost, setImapHost] = useState<string>('imap.gmail.com');
  const [imapPort, setImapPort] = useState<number>(993);
  const [imapScanLimit, setImapScanLimit] = useState<number>(100);

  // Settings state
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [protectionRules, setProtectionRules] = useState<ProtectionRule[]>([]);
  const [newRuleType, setNewRuleType] = useState<string>('sender');
  const [newRuleValue, setNewRuleValue] = useState<string>('');
  const [newRuleReason, setNewRuleReason] = useState<string>('');

  // AI status
  const [aiStatus, setAiStatus] = useState<any>(null);
  const [checkingAi, setCheckingAi] = useState<boolean>(false);

  // Wipe data modal
  const [wipeModalOpen, setWipeModalOpen] = useState<boolean>(false);
  const [wiping, setWiping] = useState<boolean>(false);

  const fetchData = async () => {
    try {
      const [accs, sets, rules] = await Promise.all([
        api.getAccounts(),
        api.getSettings(),
        api.getProtectionRules(),
      ]);
      setAccounts(accs);
      setSettings(sets);
      setProtectionRules(rules);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingAccounts(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCheckAi = async () => {
    setCheckingAi(true);
    try {
      const res = await api.getAiStatus();
      setAiStatus(res);
    } catch (err) {
      console.error(err);
    } finally {
      setCheckingAi(false);
    }
  };

  const handleCreateAccount = async () => {
    setLoadingCreate(true);
    try {
      if (selectedProvider === 'gmail') {
        if (!imapEmail.trim()) {
          alert('Please enter your Gmail address.');
          return;
        }
        if (!imapPassword.trim()) {
          alert('Please enter your 16-character Google App Password.');
          return;
        }
        const cleanPassword = imapPassword.trim().replace(/\s+/g, '');
        const res = await api.connectImap({
          display_name: `Gmail (${imapEmail.trim()})`,
          email_address: imapEmail.trim(),
          host: 'imap.gmail.com',
          username: imapEmail.trim(),
          password: cleanPassword,
          port: 993,
          use_ssl: true,
          initial_scan_limit: imapScanLimit,
        });
        alert(`Successfully connected ${res.email_address}! Scanned and indexed ${res.inserted_count} messages locally.`);
      } else if (selectedProvider === 'imap') {
        if (!imapEmail.trim() || !imapPassword.trim() || !imapHost.trim()) {
          alert('Please fill in server host, email address, and password.');
          return;
        }
        const res = await api.connectImap({
          display_name: `IMAP (${imapEmail.trim()})`,
          email_address: imapEmail.trim(),
          host: imapHost.trim(),
          username: imapEmail.trim(),
          password: imapPassword.trim(),
          port: imapPort || 993,
          use_ssl: true,
          initial_scan_limit: imapScanLimit,
        });
        alert(`Successfully connected ${res.email_address}! Scanned and indexed ${res.inserted_count} messages locally.`);
      } else if (selectedProvider === 'synthetic') {
        await api.generateSynthetic({
          display_name: 'Demo Mailbox',
          email_address: `demo_${Date.now()}@mailgraph.local`,
          message_count: syntheticCount,
        });
      } else if (selectedProvider === 'mbox') {
        if (!mboxPath) {
          alert('Please enter or select a valid MBOX file path.');
          return;
        }
        const acc = await api.createAccount({
          provider: 'mbox',
          display_name: 'MBOX Archive',
          email_address: 'archive@mbox.local',
        });
        await api.importMbox(acc.id, mboxPath);
      }
      setAddAccountModal(false);
      await fetchData();
    } catch (err: any) {
      alert(err.message || 'Failed to initialize account');
    } finally {
      setLoadingCreate(false);
    }
  };

  const handleDeleteAccount = async (id: number) => {
    if (!confirm('Are you sure you want to disconnect this account and purge its local index?')) return;
    try {
      await api.deleteAccount(id);
      await fetchData();
    } catch (err: any) {
      alert(err.message || 'Error deleting account');
    }
  };

  const handleAddProtectionRule = async () => {
    if (!newRuleValue.trim()) return;
    try {
      await api.createProtectionRule({
        rule_type: newRuleType,
        rule_value: newRuleValue.trim(),
        reason: newRuleReason.trim() || undefined,
      });
      setNewRuleValue('');
      setNewRuleReason('');
      const updated = await api.getProtectionRules();
      setProtectionRules(updated);
    } catch (err: any) {
      alert(err.message || 'Error adding rule');
    }
  };

  const handleDeleteRule = async (id: number) => {
    try {
      await api.deleteProtectionRule(id);
      setProtectionRules((prev) => prev.filter((r) => r.id !== id));
    } catch (err: any) {
      alert(err.message || 'Error deleting rule');
    }
  };

  const handleWipeData = async () => {
    setWiping(true);
    try {
      await api.wipeData();
      setWipeModalOpen(false);
      alert('All local database records and search indexes have been purged.');
      await fetchData();
    } catch (err: any) {
      alert(err.message || 'Error wiping data');
    } finally {
      setWiping(false);
    }
  };

  // Handle native file selection if in Electron
  const handleSelectNativeMbox = async () => {
    if ((window as any).electronAPI?.selectMboxFile) {
      const selected = await (window as any).electronAPI.selectMboxFile();
      if (selected) setMboxPath(selected);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-bg-deep overflow-hidden select-none">
      {/* Top Nav Sub-tabs */}
      <div className="px-6 py-3 bg-bg-surface border-b border-border-subtle flex items-center justify-between">
        <div className="flex items-center gap-1 bg-bg-deep p-0.5 rounded border border-border-muted text-xs">
          <button
            onClick={() => setActiveTab('accounts')}
            className={`px-3 py-1 rounded font-medium transition-colors ${
              activeTab === 'accounts' ? 'bg-brand text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Accounts & Data Sources
          </button>
          <button
            onClick={() => setActiveTab('protection')}
            className={`px-3 py-1 rounded font-medium transition-colors ${
              activeTab === 'protection' ? 'bg-brand text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Protection Rules
          </button>
          <button
            onClick={() => setActiveTab('privacy')}
            className={`px-3 py-1 rounded font-medium transition-colors ${
              activeTab === 'privacy' ? 'bg-brand text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Privacy & Local Storage
          </button>
          <button
            onClick={() => {
              setActiveTab('ai');
              handleCheckAi();
            }}
            className={`px-3 py-1 rounded font-medium transition-colors ${
              activeTab === 'ai' ? 'bg-brand text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Optional Local AI
          </button>
        </div>
      </div>

      {/* Tab 1: Accounts */}
      {activeTab === 'accounts' && (
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-100 tracking-tight">Connected Accounts & Sources</h3>
              <p className="text-xs text-slate-400 mt-0.5">Manage mailbox sources indexed in your local SQLite store.</p>
            </div>
            <Button
              size="sm"
              variant="primary"
              icon={<Plus className="w-3.5 h-3.5" />}
              onClick={() => setAddAccountModal(true)}
            >
              Add Mailbox Source
            </Button>
          </div>

          <div className="border border-border-subtle rounded divide-y divide-border-subtle bg-bg-surface text-xs font-mono">
            {accounts.length === 0 ? (
              <div className="py-8 text-center text-slate-500 font-sans">
                No accounts connected yet. Click "Add Mailbox Source" above to begin.
              </div>
            ) : (
              accounts.map((acc) => (
                <div key={acc.id} className="p-4 flex items-center justify-between hover:bg-bg-elevated transition-colors">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-slate-200">{acc.display_name}</span>
                      <span className="text-[11px] px-2 py-0.5 rounded bg-bg-deep border border-border-subtle uppercase text-slate-400 font-mono">
                        {acc.provider}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-400 mt-1">{acc.email_address}</div>
                    <div className="text-[10px] text-slate-500 mt-0.5">
                      Last Scanned: {acc.last_sync_at || 'Never'} • Created: {acc.created_at?.slice(0, 10)}
                    </div>
                  </div>

                  <Button
                    size="xs"
                    variant="danger"
                    onClick={() => handleDeleteAccount(acc.id)}
                    icon={<Trash2 className="w-3.5 h-3.5" />}
                  >
                    Disconnect
                  </Button>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Tab 2: Protection Rules */}
      {activeTab === 'protection' && (
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="bg-bg-surface border border-border-subtle rounded-lg p-5 shadow-sm space-y-4">
            <h3 className="text-sm font-semibold text-slate-100 tracking-tight flex items-center gap-2">
              <Shield className="w-4 h-4 text-emerald-400" />
              Add Protected Sender or Domain
            </h3>
            <p className="text-xs text-slate-400">
              Protected entities are strictly shielded from cleanup simulation and bulk execution queries.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
              <div>
                <label className="block text-slate-400 font-mono text-[11px] mb-1">RULE TYPE</label>
                <select
                  value={newRuleType}
                  onChange={(e) => setNewRuleType(e.target.value)}
                  className="w-full bg-bg-deep border border-border-muted rounded px-3 py-1.5 text-slate-200 focus:outline-none"
                >
                  <option value="sender">Specific Sender (e.g. boss@corp.com)</option>
                  <option value="domain">Entire Domain (e.g. mybank.com)</option>
                </select>
              </div>

              <div className="md:col-span-2">
                <label className="block text-slate-400 font-mono text-[11px] mb-1">RULE VALUE</label>
                <input
                  type="text"
                  value={newRuleValue}
                  onChange={(e) => setNewRuleValue(e.target.value)}
                  placeholder={newRuleType === 'sender' ? 'address@example.com' : 'example.com'}
                  className="w-full bg-bg-deep border border-border-muted rounded px-3 py-1.5 text-slate-200 focus:outline-none font-mono"
                />
              </div>

              <div>
                <label className="block text-slate-400 font-mono text-[11px] mb-1">REASON / NOTES</label>
                <input
                  type="text"
                  value={newRuleReason}
                  onChange={(e) => setNewRuleReason(e.target.value)}
                  placeholder="e.g. Primary financial alerts"
                  className="w-full bg-bg-deep border border-border-muted rounded px-3 py-1.5 text-slate-200 focus:outline-none"
                />
              </div>
            </div>

            <div className="flex justify-end pt-1">
              <Button size="sm" variant="primary" onClick={handleAddProtectionRule}>
                Add Protection Rule
              </Button>
            </div>
          </div>

          <div className="space-y-3">
            <h4 className="text-xs font-mono uppercase tracking-wider text-slate-400">
              Active Protection Rules ({protectionRules.length})
            </h4>

            <div className="border border-border-subtle rounded divide-y divide-border-subtle bg-bg-surface text-xs font-mono">
              {protectionRules.map((r) => (
                <div key={r.id} className="p-3.5 flex items-center justify-between hover:bg-bg-elevated">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-emerald-400">{r.rule_value}</span>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-bg-deep border border-border-subtle text-slate-400">
                        {r.rule_type}
                      </span>
                    </div>
                    {r.reason && <div className="text-[11px] text-slate-500 font-sans mt-0.5">{r.reason}</div>}
                  </div>

                  <Button size="xs" variant="ghost" onClick={() => handleDeleteRule(r.id)}>
                    Remove
                  </Button>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Tab 3: Privacy & Local Storage */}
      {activeTab === 'privacy' && (
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="bg-bg-surface border border-border-subtle rounded-lg p-5 shadow-sm space-y-4">
            <h3 className="text-sm font-semibold text-slate-100 tracking-tight flex items-center gap-2">
              <HardDrive className="w-4 h-4 text-brand-light" />
              Local Storage Architecture & Privacy Controls
            </h3>

            <div className="p-3 bg-bg-deep rounded border border-border-subtle text-xs font-mono space-y-1.5">
              <div className="text-slate-400">Local SQLite Store Path:</div>
              <div className="text-brand-light font-bold truncate">{settings?.db_path}</div>
              <div className="text-[11px] text-slate-500 pt-1">
                Zero cloud syncing. Zero telemetry. Zero external servers. All data remains exclusively on your machine.
              </div>
            </div>

            <div className="space-y-3 pt-2 text-xs">
              <label className="flex items-center justify-between p-3 rounded bg-bg-deep border border-border-subtle cursor-pointer">
                <div>
                  <div className="font-semibold text-slate-200">Index Message Bodies in FTS5</div>
                  <div className="text-[11px] text-slate-400">
                    When enabled, email body text is indexed in SQLite FTS5 for full-text search.
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={settings?.index_message_bodies || false}
                  onChange={async (e) => {
                    const updated = await api.updateSettings({ index_message_bodies: e.target.checked });
                    setSettings(updated);
                  }}
                  className="rounded text-brand focus:ring-0"
                />
              </label>

              <label className="flex items-center justify-between p-3 rounded bg-bg-deep border border-border-subtle cursor-pointer">
                <div>
                  <div className="font-semibold text-slate-200">Default Deletion Mode</div>
                  <div className="text-[11px] text-slate-400">
                    Always prefer moving messages to the provider's Trash folder instead of permanent deletion.
                  </div>
                </div>
                <span className="font-mono text-emerald-400 text-xs uppercase">TRASH (RECOVERABLE)</span>
              </label>
            </div>
          </div>

          {/* Secure Wipe Button */}
          <div className="bg-bg-surface border border-red-950 rounded-lg p-5 shadow-sm flex items-center justify-between">
            <div>
              <h4 className="text-sm font-semibold text-red-300 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-red-400" />
                Secure Local Data Wipe
              </h4>
              <p className="text-xs text-slate-400 mt-0.5">
                Permanently purge all imported messages, indexes, senders, and operation logs from this machine.
              </p>
            </div>
            <Button size="sm" variant="danger" onClick={() => setWipeModalOpen(true)}>
              Wipe Local Database
            </Button>
          </div>
        </div>
      )}

      {/* Tab 4: Optional Local AI */}
      {activeTab === 'ai' && (
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="bg-bg-surface border border-border-subtle rounded-lg p-5 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-slate-100 tracking-tight flex items-center gap-2">
                  <Bot className="w-4 h-4 text-purple-400" />
                  Optional Local AI Assistant (Ollama)
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  MailGraph works 100% deterministically without AI. If you have Ollama running locally on loopback, it can propose structured search queries.
                </p>
              </div>
              <Button size="xs" variant="outline" onClick={handleCheckAi} loading={checkingAi}>
                Check Status
              </Button>
            </div>

            <div className="p-3 bg-bg-deep rounded border border-border-subtle text-xs font-mono space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Loopback Endpoint:</span>
                <span className="text-slate-200">http://127.0.0.1:11434</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Connection Status:</span>
                <span className={aiStatus?.is_available ? 'text-emerald-400' : 'text-slate-500'}>
                  {aiStatus?.status || 'Checking...'}
                </span>
              </div>
              {aiStatus?.installed_models && aiStatus.installed_models.length > 0 && (
                <div className="flex items-center justify-between pt-1 border-t border-border-subtle">
                  <span className="text-slate-400">Installed Local Models:</span>
                  <span className="text-brand-light">{aiStatus.installed_models.join(', ')}</span>
                </div>
              )}
            </div>

            <div className="p-3 bg-purple-950/20 border border-purple-800/40 rounded text-xs text-purple-200 space-y-1">
              <span className="font-semibold">Safety & Autonomy Guarantee:</span>
              <p className="text-[11px] text-purple-300/80 leading-relaxed">
                Even when local AI is active, models are strictly prohibited from independently authorizing or executing delete, archive, or move operations. All AI output is translated into an inspectable structured query that you must review before any action.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Add Account Modal */}
      <Modal
        isOpen={addAccountModal}
        onClose={() => setAddAccountModal(false)}
        title="Add Mailbox Data Source"
        subtitle="Choose an ingestion source to index locally"
        maxWidth="lg"
      >
        <div className="space-y-4 text-xs">
          {/* Source Selector */}
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => setSelectedProvider('gmail')}
              className={`p-3 rounded border text-left transition-colors ${
                selectedProvider === 'gmail'
                  ? 'bg-brand/15 border-brand text-brand-light'
                  : 'bg-bg-deep border-border-muted text-slate-400 hover:text-slate-200'
              }`}
            >
              <div className="font-semibold text-slate-100 flex items-center gap-1.5">
                <Mail className="w-4 h-4 text-emerald-400" /> Gmail (Direct Link)
              </div>
              <div className="text-[11px] text-slate-400 mt-1">
                Connect via Google App Password in 15 seconds. No cloud APIs or console setup needed.
              </div>
            </button>

            <button
              onClick={() => setSelectedProvider('imap')}
              className={`p-3 rounded border text-left transition-colors ${
                selectedProvider === 'imap'
                  ? 'bg-brand/15 border-brand text-brand-light'
                  : 'bg-bg-deep border-border-muted text-slate-400 hover:text-slate-200'
              }`}
            >
              <div className="font-semibold text-slate-100 flex items-center gap-1.5">
                <Server className="w-4 h-4 text-cyan-400" /> Standard IMAP
              </div>
              <div className="text-[11px] text-slate-400 mt-1">
                Connect to Outlook, Yahoo, iCloud, Fastmail, or custom mail servers.
              </div>
            </button>

            <button
              onClick={() => setSelectedProvider('synthetic')}
              className={`p-3 rounded border text-left transition-colors ${
                selectedProvider === 'synthetic'
                  ? 'bg-brand/15 border-brand text-brand-light'
                  : 'bg-bg-deep border-border-muted text-slate-400 hover:text-slate-200'
              }`}
            >
              <div className="font-semibold text-slate-100 flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-amber-400" /> Synthetic Demo Box
              </div>
              <div className="text-[11px] text-slate-400 mt-1">
                Instantly generate realistic multi-domain emails with zero credentials needed.
              </div>
            </button>

            <button
              onClick={() => setSelectedProvider('mbox')}
              className={`p-3 rounded border text-left transition-colors ${
                selectedProvider === 'mbox'
                  ? 'bg-brand/15 border-brand text-brand-light'
                  : 'bg-bg-deep border-border-muted text-slate-400 hover:text-slate-200'
              }`}
            >
              <div className="font-semibold text-slate-100 flex items-center gap-1.5">
                <FolderOpen className="w-4 h-4 text-blue-400" /> Offline MBOX File
              </div>
              <div className="text-[11px] text-slate-400 mt-1">
                Import Google Takeout, Thunderbird, or Apple Mail .mbox archives.
              </div>
            </button>
          </div>

          {/* Form details per provider */}
          {selectedProvider === 'gmail' && (
            <div className="space-y-3 pt-2">
              <div className="p-2.5 bg-emerald-950/20 border border-emerald-800/40 rounded text-xs text-emerald-200 space-y-1">
                <div className="font-semibold flex items-center gap-1 text-[11px]">
                  <Key className="w-3.5 h-3.5" /> Direct Google Account Setup (30 Seconds):
                </div>
                <ol className="text-[11px] text-emerald-300/80 list-decimal list-inside space-y-0.5">
                  <li>Visit <span className="font-mono text-emerald-100">myaccount.google.com/apppasswords</span></li>
                  <li>Enter app name <strong>MailGraph</strong> and click Create</li>
                  <li>Copy the 16-letter password and paste it below. Credentials stay safely in your OS Keyring.</li>
                </ol>
              </div>

              <div>
                <label className="block text-slate-400 font-mono text-[11px] mb-1">GMAIL ADDRESS</label>
                <input
                  type="email"
                  value={imapEmail}
                  onChange={(e) => setImapEmail(e.target.value)}
                  placeholder="yourname@gmail.com"
                  className="w-full bg-bg-deep border border-border-muted rounded px-3 py-1.5 text-slate-200 focus:outline-none font-mono"
                />
              </div>

              <div>
                <label className="block text-slate-400 font-mono text-[11px] mb-1">GOOGLE APP PASSWORD (16 CHARACTERS)</label>
                <input
                  type="password"
                  value={imapPassword}
                  onChange={(e) => setImapPassword(e.target.value)}
                  placeholder="xxxx xxxx xxxx xxxx"
                  className="w-full bg-bg-deep border border-border-muted rounded px-3 py-1.5 text-slate-200 focus:outline-none font-mono"
                />
              </div>

              <div>
                <label className="block text-slate-400 font-mono text-[11px] mb-1">INITIAL MESSAGES TO SCAN & INDEX</label>
                <select
                  value={imapScanLimit}
                  onChange={(e) => setImapScanLimit(Number(e.target.value))}
                  className="w-full bg-bg-deep border border-border-muted rounded px-3 py-1.5 text-slate-200 focus:outline-none"
                >
                  <option value={50}>50 most recent messages (Fastest)</option>
                  <option value={100}>100 most recent messages (Recommended)</option>
                  <option value={250}>250 most recent messages</option>
                  <option value={500}>500 most recent messages</option>
                </select>
              </div>
            </div>
          )}

          {selectedProvider === 'imap' && (
            <div className="space-y-3 pt-2">
              <div className="grid grid-cols-3 gap-2">
                <div className="col-span-2">
                  <label className="block text-slate-400 font-mono text-[11px] mb-1">IMAP HOST</label>
                  <input
                    type="text"
                    value={imapHost}
                    onChange={(e) => setImapHost(e.target.value)}
                    placeholder="imap.mail.me.com"
                    className="w-full bg-bg-deep border border-border-muted rounded px-3 py-1.5 text-slate-200 focus:outline-none font-mono"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 font-mono text-[11px] mb-1">PORT (SSL)</label>
                  <input
                    type="number"
                    value={imapPort}
                    onChange={(e) => setImapPort(Number(e.target.value))}
                    className="w-full bg-bg-deep border border-border-muted rounded px-3 py-1.5 text-slate-200 focus:outline-none font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-400 font-mono text-[11px] mb-1">EMAIL ADDRESS / USERNAME</label>
                <input
                  type="text"
                  value={imapEmail}
                  onChange={(e) => setImapEmail(e.target.value)}
                  placeholder="user@domain.com"
                  className="w-full bg-bg-deep border border-border-muted rounded px-3 py-1.5 text-slate-200 focus:outline-none font-mono"
                />
              </div>

              <div>
                <label className="block text-slate-400 font-mono text-[11px] mb-1">PASSWORD / APP PASSWORD</label>
                <input
                  type="password"
                  value={imapPassword}
                  onChange={(e) => setImapPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full bg-bg-deep border border-border-muted rounded px-3 py-1.5 text-slate-200 focus:outline-none font-mono"
                />
              </div>

              <div>
                <label className="block text-slate-400 font-mono text-[11px] mb-1">INITIAL MESSAGES TO SCAN</label>
                <select
                  value={imapScanLimit}
                  onChange={(e) => setImapScanLimit(Number(e.target.value))}
                  className="w-full bg-bg-deep border border-border-muted rounded px-3 py-1.5 text-slate-200 focus:outline-none"
                >
                  <option value={50}>50 messages</option>
                  <option value={100}>100 messages (Recommended)</option>
                  <option value={250}>250 messages</option>
                  <option value={500}>500 messages</option>
                </select>
              </div>
            </div>
          )}

          {selectedProvider === 'synthetic' && (
            <div className="space-y-2 pt-2">
              <label className="block text-slate-400 font-mono text-[11px]">NUMBER OF MESSAGES TO SIMULATE</label>
              <select
                value={syntheticCount}
                onChange={(e) => setSyntheticCount(Number(e.target.value))}
                className="w-full bg-bg-deep border border-border-muted rounded px-3 py-1.5 text-slate-200 focus:outline-none"
              >
                <option value={25}>25 messages (Fast test)</option>
                <option value={75}>75 messages (Recommended demo)</option>
                <option value={200}>200 messages (Rich multi-domain graph)</option>
                <option value={500}>500 messages (Benchmark)</option>
              </select>
            </div>
          )}

          {selectedProvider === 'mbox' && (
            <div className="space-y-2 pt-2">
              <label className="block text-slate-400 font-mono text-[11px]">MBOX ARCHIVE FILE PATH</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={mboxPath}
                  onChange={(e) => setMboxPath(e.target.value)}
                  placeholder="C:\Users\...\archive.mbox"
                  className="flex-1 bg-bg-deep border border-border-muted rounded px-3 py-1.5 text-slate-200 focus:outline-none font-mono"
                />
                <Button size="sm" variant="outline" onClick={handleSelectNativeMbox}>
                  Browse...
                </Button>
              </div>
            </div>
          )}

          <div className="pt-3 border-t border-border-subtle flex justify-end gap-2">
            <Button size="sm" variant="ghost" onClick={() => setAddAccountModal(false)}>
              Cancel
            </Button>
            <Button size="sm" variant="primary" loading={loadingCreate} onClick={handleCreateAccount}>
              {selectedProvider === 'gmail' || selectedProvider === 'imap' ? 'Connect & Ingest' : 'Start Ingestion'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Wipe Confirmation Modal */}
      <Modal
        isOpen={wipeModalOpen}
        onClose={() => setWipeModalOpen(false)}
        title="Confirm Local Database Wipe"
        subtitle="This action will permanently delete all local index tables."
        maxWidth="md"
      >
        <div className="space-y-4 text-xs">
          <p className="text-slate-300 leading-relaxed font-sans">
            This will purge all messages, senders, threads, attachments, and operation history from your local SQLite database.
          </p>
          <div className="pt-3 border-t border-border-subtle flex justify-end gap-2">
            <Button size="sm" variant="ghost" onClick={() => setWipeModalOpen(false)}>
              Cancel
            </Button>
            <Button size="sm" variant="danger" loading={wiping} onClick={handleWipeData}>
              Permanently Wipe Data
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
