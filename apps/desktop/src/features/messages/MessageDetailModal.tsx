import React, { useState, useEffect } from 'react';
import { Mail, Calendar, User, Paperclip, Shield, Trash2, Archive, Download, ExternalLink } from 'lucide-react';
import { MessageDetail } from '../../types/api';
import { api } from '../../api/client';
import { Modal } from '../../components/Modal';
import { Badge } from '../../components/Badge';
import { Button } from '../../components/Button';

interface MessageDetailModalProps {
  messageId: number | null;
  onClose: () => void;
  onTrash?: (messageId: number) => void;
  onArchive?: (messageId: number) => void;
}

export const MessageDetailModal: React.FC<MessageDetailModalProps> = ({
  messageId,
  onClose,
  onTrash,
  onArchive,
}) => {
  const [detail, setDetail] = useState<MessageDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [showRawText, setShowRawText] = useState<boolean>(false);

  useEffect(() => {
    if (messageId) {
      setLoading(true);
      api
        .getMessageDetail(messageId)
        .then((res) => setDetail(res))
        .catch((err) => console.error(err))
        .finally(() => setLoading(false));
    } else {
      setDetail(null);
    }
  }, [messageId]);

  if (!messageId) return null;

  return (
    <Modal
      isOpen={messageId !== null}
      onClose={onClose}
      title={detail ? detail.subject : 'Loading Message...'}
      subtitle={detail ? `Received ${detail.received_at}` : ''}
      maxWidth="4xl"
    >
      {loading || !detail ? (
        <div className="py-12 text-center text-slate-400 font-sans text-xs">
          Loading email details and attachments...
        </div>
      ) : (
        <div className="space-y-4">
          {/* Metadata Grid */}
          <div className="bg-bg-deep p-3.5 rounded border border-border-subtle space-y-2 text-xs">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-slate-400 font-mono">From: </span>
                <span className="font-semibold text-slate-200">{detail.sender_name} </span>
                <span className="text-slate-400 font-mono">&lt;{detail.sender_address}&gt;</span>
              </div>
              <Badge label={detail.category} color={detail.category_color} />
            </div>

            {detail.addresses && detail.addresses.length > 0 && (
              <div>
                <span className="text-slate-400 font-mono">To: </span>
                <span className="text-slate-300 font-mono">
                  {detail.addresses
                    .filter((a) => a.role === 'to')
                    .map((a) => a.display_name ? `${a.display_name} <${a.address}>` : a.address)
                    .join(', ') || 'Undisclosed recipients'}
                </span>
              </div>
            )}

            <div className="flex items-center gap-4 text-slate-400 font-mono text-[11px] pt-1 border-t border-border-subtle">
              <span>Date: {detail.received_at}</span>
              <span>Size: {(detail.size_bytes / 1024).toFixed(1)} KB</span>
              <span>Message-ID: {detail.provider_message_id}</span>
              {detail.category_reason && (
                <span className="text-slate-400 italic">Classification: {detail.category_reason}</span>
              )}
            </div>
          </div>

          {/* Attachments List */}
          {detail.attachments && detail.attachments.length > 0 && (
            <div className="p-3 bg-bg-surface border border-border-subtle rounded space-y-2">
              <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <Paperclip className="w-3.5 h-3.5" />
                Attachments ({detail.attachments.length})
              </div>
              <div className="grid grid-cols-2 gap-2">
                {detail.attachments.map((att) => (
                  <div
                    key={att.id}
                    className="p-2 rounded bg-bg-deep border border-border-subtle flex items-center justify-between text-xs"
                  >
                    <div className="truncate pr-2">
                      <div className="font-medium text-slate-200 truncate">{att.filename}</div>
                      <div className="text-[10px] font-mono text-slate-500">
                        {(att.size_bytes / 1024).toFixed(0)} KB • {att.mime_type}
                      </div>
                    </div>
                    <Button size="xs" variant="ghost" title="Save attachment">
                      <Download className="w-3.5 h-3.5 text-slate-400" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Email Body Preview (Sanitized) */}
          <div className="border border-border-subtle rounded overflow-hidden">
            <div className="bg-bg-surface px-3 py-1.5 border-b border-border-subtle flex items-center justify-between text-xs">
              <span className="text-slate-400 font-mono text-[11px]">Sanitized Content View</span>
              <button
                onClick={() => setShowRawText(!showRawText)}
                className="text-xs text-brand-light hover:underline font-mono"
              >
                {showRawText ? 'View HTML Preview' : 'View Plain Text'}
              </button>
            </div>

            <div className="p-4 bg-slate-950 max-h-[350px] overflow-y-auto">
              {showRawText ? (
                <pre className="font-mono text-xs text-slate-300 whitespace-pre-wrap leading-relaxed">
                  {detail.body_text || '(No plain text body content)'}
                </pre>
              ) : (
                <div
                  className="prose prose-invert prose-sm max-w-none text-slate-300"
                  dangerouslySetInnerHTML={{ __html: detail.sanitized_html }}
                />
              )}
            </div>
          </div>

          {/* Bottom Action Footer */}
          <div className="pt-3 border-t border-border-subtle flex items-center justify-between">
            <div className="flex items-center gap-2">
              {onArchive && (
                <Button
                  size="sm"
                  variant="secondary"
                  icon={<Archive className="w-3.5 h-3.5 text-blue-400" />}
                  onClick={() => onArchive(detail.id)}
                >
                  Archive
                </Button>
              )}
              {onTrash && (
                <Button
                  size="sm"
                  variant="danger"
                  icon={<Trash2 className="w-3.5 h-3.5 text-red-400" />}
                  onClick={() => onTrash(detail.id)}
                >
                  Move to Trash
                </Button>
              )}
            </div>
            <Button size="sm" variant="ghost" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
};
