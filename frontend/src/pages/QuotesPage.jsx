// src/pages/QuotesPage.jsx
// Lists all quotes with status badges, line item detail drawer,
// and approve / reject / send actions.

import { useState, useEffect, useCallback } from 'react'
import { listQuotes, approveQuote, rejectQuote, sendQuote } from '../api'

// ─── Helpers ──────────────────────────────────────────────────────────────────

const STATUS_BADGE = {
  draft:    'badge-draft',
  sent:     'badge-sent',
  approved: 'badge-approved',
  rejected: 'badge-rejected',
  invoiced: 'badge-invoiced',
}

function StatusBadge({ status }) {
  const cls = STATUS_BADGE[status] || 'badge-draft'
  return <span className={cls}>{status}</span>
}

function fmt(n) {
  return typeof n === 'number' ? `$${n.toFixed(2)}` : '--'
}

function fmtDate(iso) {
  if (!iso) return '--'
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

// ─── Line item detail drawer ───────────────────────────────────────────────

function QuoteDrawer({ quote, onClose, onAction }) {
  const [actionLoading, setActionLoading] = useState(null)
  const [actionError,   setActionError]   = useState(null)
  const [rejectReason,  setRejectReason]  = useState('')
  const [showReject,    setShowReject]    = useState(false)
  const [sendEmail,     setSendEmail]     = useState(quote.contact_email || '')
  const [showSend,      setShowSend]      = useState(false)

  const canApprove = ['draft', 'sent'].includes(quote.status)
  const canReject  = ['draft', 'sent'].includes(quote.status)
  const canSend    = quote.status === 'draft'

  const doApprove = async () => {
    setActionLoading('approve')
    setActionError(null)
    try {
      await approveQuote(quote.quote_number, false) // skip QBO for now
      onAction()
    } catch (err) {
      setActionError(err?.response?.data?.detail || 'Approve failed.')
    } finally {
      setActionLoading(null)
    }
  }

  const doReject = async () => {
    if (!rejectReason.trim()) return
    setActionLoading('reject')
    setActionError(null)
    try {
      await rejectQuote(quote.quote_number, rejectReason.trim())
      onAction()
    } catch (err) {
      setActionError(err?.response?.data?.detail || 'Reject failed.')
    } finally {
      setActionLoading(null)
    }
  }

  const doSend = async () => {
    if (!sendEmail.trim()) return
    setActionLoading('send')
    setActionError(null)
    try {
      await sendQuote(quote.quote_number, sendEmail.trim())
      onAction()
    } catch (err) {
      setActionError(err?.response?.data?.detail || 'Send failed.')
    } finally {
      setActionLoading(null)
    }
  }

  const lineItems = Array.isArray(quote.line_items) ? quote.line_items : []

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="flex-1 bg-black/40" onClick={onClose} />

      {/* Drawer */}
      <div className="w-full max-w-xl bg-white shadow-2xl flex flex-col overflow-y-auto">

        {/* Header */}
        <div className="bg-navy text-offwhite px-6 py-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-gold font-mono">{quote.quote_number}</p>
            <h2 className="text-lg font-semibold">{quote.client_name}</h2>
          </div>
          <button onClick={onClose} className="text-offwhite/70 hover:text-offwhite text-2xl leading-none">
            &times;
          </button>
        </div>

        <div className="flex-1 p-6 space-y-6">

          {/* Status + dates */}
          <div className="flex items-center gap-4 flex-wrap">
            <StatusBadge status={quote.status} />
            <span className="text-xs text-muted">Created: {fmtDate(quote.created_at)}</span>
            {quote.sent_at     && <span className="text-xs text-muted">Sent: {fmtDate(quote.sent_at)}</span>}
            {quote.approved_at && <span className="text-xs text-muted">Approved: {fmtDate(quote.approved_at)}</span>}
          </div>

          {/* Client info */}
          <div className="card space-y-1">
            <p className="text-xs font-semibold text-muted uppercase tracking-wide mb-2">Client</p>
            <p className="text-sm font-medium text-navy">{quote.client_name}</p>
            {quote.contact_email && <p className="text-xs text-muted">{quote.contact_email}</p>}
            {quote.contact_phone && <p className="text-xs text-muted">{quote.contact_phone}</p>}
          </div>

          {/* Artwork */}
          {(quote.artwork_width || quote.artwork_height) && (
            <div className="card space-y-1">
              <p className="text-xs font-semibold text-muted uppercase tracking-wide mb-2">Artwork</p>
              <p className="text-sm text-navy">
                {quote.artwork_width}" &times; {quote.artwork_height}"
                {quote.artwork_notes && ` — ${quote.artwork_notes}`}
              </p>
            </div>
          )}

          {/* Line items */}
          <div>
            <p className="text-xs font-semibold text-muted uppercase tracking-wide mb-3">Line Items</p>
            {lineItems.length === 0 ? (
              <p className="text-sm text-muted">No line items.</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-1.5 text-xs text-muted">#</th>
                    <th className="text-left py-1.5 text-xs text-muted">Description</th>
                    <th className="text-right py-1.5 text-xs text-muted">Qty</th>
                    <th className="text-right py-1.5 text-xs text-muted">Unit</th>
                    <th className="text-right py-1.5 text-xs text-muted">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {lineItems.map((item, i) => (
                    <tr key={i}>
                      <td className="py-2 text-muted text-xs">{item.line_number}</td>
                      <td className="py-2">
                        <p className="font-medium text-navy text-xs">{item.description}</p>
                        {item.sku && <p className="text-xs text-muted font-mono">{item.sku}</p>}
                      </td>
                      <td className="py-2 text-right text-xs text-navy">{Number(item.quantity).toFixed(3)}</td>
                      <td className="py-2 text-right text-xs text-navy">${Number(item.unit_price).toFixed(2)}</td>
                      <td className="py-2 text-right text-xs font-semibold text-navy">${Number(item.total).toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Totals */}
          <div className="border-t border-gray-200 pt-4 space-y-1">
            <div className="flex justify-between text-sm text-muted">
              <span>Subtotal</span>
              <span className="text-navy">{fmt(quote.subtotal)}</span>
            </div>
            {quote.tax > 0 && (
              <div className="flex justify-between text-sm text-muted">
                <span>Tax</span>
                <span className="text-navy">{fmt(quote.tax)}</span>
              </div>
            )}
            <div className="flex justify-between text-base font-bold text-navy border-t border-gray-200 pt-2 mt-1">
              <span>Total</span>
              <span className="text-gold">{fmt(quote.total)}</span>
            </div>
          </div>

          {/* Notes */}
          {quote.notes && (
            <div className="bg-gray-50 rounded p-3">
              <p className="text-xs font-semibold text-muted uppercase tracking-wide mb-1">Notes</p>
              <p className="text-sm text-navy">{quote.notes}</p>
            </div>
          )}

          {/* Rejection reason */}
          {quote.status === 'rejected' && quote.rejection_reason && (
            <div className="bg-red-50 border border-red-200 rounded p-3">
              <p className="text-xs font-semibold text-red-500 uppercase tracking-wide mb-1">Rejection Reason</p>
              <p className="text-sm text-red-700">{quote.rejection_reason}</p>
            </div>
          )}

          {/* Error */}
          {actionError && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2">
              {actionError}
            </p>
          )}

          {/* Actions */}
          <div className="space-y-3 border-t border-gray-100 pt-4">

            {/* Send */}
            {canSend && (
              <div>
                {showSend ? (
                  <div className="flex gap-2">
                    <input
                      className="input flex-1 text-sm"
                      placeholder="Client email address"
                      value={sendEmail}
                      onChange={e => setSendEmail(e.target.value)}
                    />
                    <button
                      onClick={doSend}
                      disabled={actionLoading === 'send'}
                      className="btn-primary text-sm px-4"
                    >
                      {actionLoading === 'send' ? '...' : 'Send'}
                    </button>
                    <button onClick={() => setShowSend(false)} className="btn-secondary text-sm px-3">
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button onClick={() => setShowSend(true)} className="btn-secondary w-full">
                    Mark as Sent
                  </button>
                )}
              </div>
            )}

            {/* Approve */}
            {canApprove && (
              <button
                onClick={doApprove}
                disabled={actionLoading === 'approve'}
                className="btn-primary w-full"
              >
                {actionLoading === 'approve' ? 'Approving...' : 'Approve Quote'}
              </button>
            )}

            {/* Reject */}
            {canReject && (
              <div>
                {showReject ? (
                  <div className="space-y-2">
                    <textarea
                      className="input resize-none text-sm"
                      rows={2}
                      placeholder="Reason for rejection..."
                      value={rejectReason}
                      onChange={e => setRejectReason(e.target.value)}
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={doReject}
                        disabled={actionLoading === 'reject' || !rejectReason.trim()}
                        className="btn-danger flex-1 text-sm"
                      >
                        {actionLoading === 'reject' ? 'Rejecting...' : 'Confirm Reject'}
                      </button>
                      <button onClick={() => setShowReject(false)} className="btn-secondary text-sm px-4">
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <button onClick={() => setShowReject(true)} className="btn-danger w-full">
                    Reject Quote
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Main page ─────────────────────────────────────────────────────────────

export default function QuotesPage() {
  const [quotes,        setQuotes]        = useState([])
  const [loading,       setLoading]       = useState(true)
  const [error,         setError]         = useState(null)
  const [statusFilter,  setStatusFilter]  = useState('')
  const [selectedQuote, setSelectedQuote] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    listQuotes(statusFilter || null)
      .then(res => setQuotes(res.data.quotes))
      .catch(() => setError('Failed to load quotes.'))
      .finally(() => setLoading(false))
  }, [statusFilter])

  useEffect(() => { load() }, [load])

  const handleAction = () => {
    setSelectedQuote(null)
    load()
  }

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-navy">Quotes</h1>
          <p className="text-sm text-muted mt-0.5">{quotes.length} quote{quotes.length !== 1 ? 's' : ''}</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            className="input w-44 text-sm"
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
          >
            <option value="">All Statuses</option>
            <option value="draft">Draft</option>
            <option value="sent">Sent</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="invoiced">Invoiced</option>
          </select>
          <button onClick={load} className="btn-secondary text-sm">
            Refresh
          </button>
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <p className="text-sm text-muted">Loading quotes...</p>
      ) : error ? (
        <p className="text-sm text-red-500">{error}</p>
      ) : quotes.length === 0 ? (
        <div className="card text-center py-12">
          <p className="text-muted text-sm">No quotes found.</p>
          <p className="text-muted text-xs mt-1">Create one using the New Quote button.</p>
        </div>
      ) : (
        <div className="card p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-semibold text-muted uppercase tracking-wide">Quote #</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-muted uppercase tracking-wide">Client</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-muted uppercase tracking-wide">Status</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-muted uppercase tracking-wide">Total</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-muted uppercase tracking-wide">Created</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {quotes.map(q => (
                <tr
                  key={q.id}
                  className="hover:bg-gray-50 cursor-pointer transition-colors"
                  onClick={() => setSelectedQuote(q)}
                >
                  <td className="px-4 py-3 font-mono text-xs text-gold font-semibold">{q.quote_number}</td>
                  <td className="px-4 py-3 font-medium text-navy">{q.client_name}</td>
                  <td className="px-4 py-3"><StatusBadge status={q.status} /></td>
                  <td className="px-4 py-3 text-right font-semibold text-navy">{fmt(q.total)}</td>
                  <td className="px-4 py-3 text-muted text-xs">{fmtDate(q.created_at)}</td>
                  <td className="px-4 py-3 text-right">
                    <span className="text-xs text-gold hover:underline">View</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Detail drawer */}
      {selectedQuote && (
        <QuoteDrawer
          quote={selectedQuote}
          onClose={() => setSelectedQuote(null)}
          onAction={handleAction}
        />
      )}
    </div>
  )
}
