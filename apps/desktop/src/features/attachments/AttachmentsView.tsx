import React, { useState, useEffect } from 'react';
import { Paperclip, Copy, Download, Search, HardDrive, FileText, Filter } from 'lucide-react';
import { api } from '../../api/client';
import { DuplicateAttachmentGroup } from '../../types/api';
import { Button } from '../../components/Button';
import { Badge } from '../../components/Badge';

export const AttachmentsView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'all' | 'duplicates'>('duplicates');
  const [attachments, setAttachments] = useState<any[]>([]);
  const [duplicates, setDuplicates] = useState<DuplicateAttachmentGroup[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [mimeFilter, setMimeFilter] = useState<string>('');

  const fetchData = async () => {
    setLoading(true);
    try {
      if (activeTab === 'duplicates') {
        const res = await api.getDuplicateAttachments();
        setDuplicates(res.duplicate_groups);
      } else {
        const res = await api.getAttachments({
          search: search || undefined,
          mime_type: mimeFilter || undefined,
          page: 1,
          page_size: 100,
        });
        setAttachments(res.items);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [activeTab, search, mimeFilter]);

  const totalWastedBytes = duplicates.reduce(
    (acc, d) => acc + d.file_size * (d.duplicate_count - 1),
    0
  );
  const totalWastedMb = (totalWastedBytes / (1024 * 1024)).toFixed(2);

  return (
    <div className="flex-1 flex flex-col h-full bg-bg-deep overflow-hidden select-none">
      {/* Top Controls Bar */}
      <div className="p-4 bg-bg-surface border-b border-border-subtle flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 bg-bg-deep p-0.5 rounded border border-border-muted text-xs">
          <button
            onClick={() => setActiveTab('duplicates')}
            className={`px-3 py-1 rounded font-medium transition-colors ${
              activeTab === 'duplicates'
                ? 'bg-brand text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Duplicate Files ({duplicates.length} groups)
          </button>
          <button
            onClick={() => setActiveTab('all')}
            className={`px-3 py-1 rounded font-medium transition-colors ${
              activeTab === 'all'
                ? 'bg-brand text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            All Attachments Directory
          </button>
        </div>

        {activeTab === 'all' && (
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search filenames..."
                className="pl-8 pr-3 py-1 bg-bg-deep border border-border-muted rounded text-xs text-slate-100 placeholder-slate-500 focus:outline-none"
              />
            </div>
            <select
              value={mimeFilter}
              onChange={(e) => setMimeFilter(e.target.value)}
              className="bg-bg-deep border border-border-muted rounded px-2.5 py-1 text-xs text-slate-200 focus:outline-none"
            >
              <option value="">All File Types</option>
              <option value="pdf">PDF Documents</option>
              <option value="image">Images (PNG/JPEG)</option>
              <option value="spreadsheet">Spreadsheets (Excel/CSV)</option>
              <option value="zip">Archives (ZIP/GZ)</option>
            </select>
          </div>
        )}
      </div>

      {activeTab === 'duplicates' ? (
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {/* Summary Box */}
          <div className="p-4 rounded-lg bg-bg-surface border border-border-subtle shadow-sm flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400">
                <Copy className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-100">
                  Exact Duplicate Content Intelligence
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Cryptographically identical files attached across multiple independent emails.
                </p>
              </div>
            </div>

            <div className="text-right font-mono text-xs">
              <div className="text-slate-400">Potential Redundant Space</div>
              <div className="text-base font-bold text-amber-400">~{totalWastedMb} MB</div>
            </div>
          </div>

          {/* Duplicate Groups List */}
          <div className="space-y-3">
            {loading ? (
              <div className="py-12 text-center text-xs text-slate-400 font-mono">
                Scanning attachments for cryptographic hash matches...
              </div>
            ) : duplicates.length === 0 ? (
              <div className="py-12 text-center text-xs text-slate-500 font-sans">
                No duplicate attachments found in your local mailbox.
              </div>
            ) : (
              duplicates.map((group) => (
                <div
                  key={group.content_hash}
                  className="bg-bg-surface border border-border-subtle rounded-lg p-4 space-y-3 shadow-sm"
                >
                  <div className="flex items-center justify-between border-b border-border-subtle pb-2.5">
                    <div className="flex items-center gap-2 truncate">
                      <FileText className="w-4 h-4 text-brand-light shrink-0" />
                      <span className="font-semibold text-xs text-slate-200 truncate">
                        {group.filename}
                      </span>
                      <span className="text-[11px] font-mono text-slate-400">
                        ({(group.file_size / 1024).toFixed(0)} KB)
                      </span>
                    </div>

                    <span className="text-xs font-mono font-medium text-amber-400 bg-amber-950/40 border border-amber-800/60 px-2.5 py-0.5 rounded">
                      {group.duplicate_count} copies (~{((group.total_bytes_occupied - group.file_size) / 1024).toFixed(0)} KB redundant)
                    </span>
                  </div>

                  <div className="space-y-1.5">
                    <div className="text-[11px] font-mono text-slate-500 uppercase">
                      Referencing Messages:
                    </div>
                    <div className="border border-border-subtle rounded divide-y divide-border-subtle">
                      {group.references.map((ref) => (
                        <div
                          key={ref.attachment_id}
                          className="p-2 flex items-center justify-between text-xs hover:bg-bg-elevated font-mono"
                        >
                          <div className="truncate max-w-lg font-sans">
                            <span className="text-slate-300 font-medium">{ref.message_subject}</span>
                            <span className="text-[11px] text-slate-500 font-mono ml-2">from {ref.sender_address}</span>
                          </div>
                          <span className="text-[11px] text-slate-400 shrink-0">{ref.received_at?.slice(0, 10)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      ) : (
        /* All Attachments Table */
        <div className="flex-1 overflow-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-bg-surface border-b border-border-subtle text-[11px] font-mono uppercase tracking-wider text-slate-400 sticky top-0 z-10">
                <th className="py-2.5 px-4">Filename</th>
                <th className="py-2.5 px-3">Type</th>
                <th className="py-2.5 px-3">Message Subject</th>
                <th className="py-2.5 px-3">Sender</th>
                <th className="py-2.5 px-4 text-right">Size</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle text-xs">
              {loading ? (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-slate-400 font-sans">
                    Loading attachments...
                  </td>
                </tr>
              ) : attachments.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-slate-400 font-sans">
                    No attachments found matching criteria.
                  </td>
                </tr>
              ) : (
                attachments.map((att) => (
                  <tr key={att.id} className="table-row-hover">
                    <td className="py-2.5 px-4 font-medium text-slate-200 flex items-center gap-2">
                      <Paperclip className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                      <span className="truncate max-w-xs">{att.filename}</span>
                    </td>
                    <td className="py-2.5 px-3 text-slate-400 font-mono text-[11px]">
                      {att.mime_type?.split('/')[1] || att.mime_type}
                    </td>
                    <td className="py-2.5 px-3 text-slate-300 truncate max-w-md">
                      {att.message_subject}
                    </td>
                    <td className="py-2.5 px-3 text-slate-400 font-mono text-[11px] truncate max-w-xs">
                      {att.sender_address}
                    </td>
                    <td className="py-2.5 px-4 text-right font-mono text-slate-400 text-[11px]">
                      {(att.size_bytes / 1024).toFixed(0)} KB
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
