// src/pages/OrdersPage.jsx
// Orders dashboard: lists all orders, shows Monday.com sync status,
// QBO invoice status, and lets the user trigger a Monday sync.

import { useState, useEffect, useCallback } from 'react'
import { listOrders, syncOrderToMonday } from '../api'

// ─── Helpers ──────────────────────────────────────────────────────────────────

const STATUS_BADGE = {
  pending:    'badge-pending',
  confirmed:  'badge-approved',
  in_production: 'badge-sent',
  completed:  'badge-invoiced',
  cancelled:  'badge-rejected',
}

const MONDAY_BADGE = {
  pending: 'badge-pending',
  synced:  'badge-synced',
  failed:  'badge-failed',
}

const QBO_BADGE = {
  pending: 'badge-pending',
  synced:  'badge-synced',
  failed:  'badge-failed',
  skipped: 'badge-draft',
}

function StatusBadge({ status, map }) {
  const cls = (map || STATUS_BADGE)[status] || 'badge-draft'
  return <span className={cls}>{status?.replace('_', ' ') || '--'}</span>
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

// ─── Order detail drawer ───────────────────────────────────────────────────

function OrderDrawer({ order, onClose, onAction }) {
  const [syncing,    setSyncing]    = useState(false)
  const [syncError,  setSyncError]  = useState(null)
  const [syncSuccess,setSyncSuccess]= useState(null)

  const doSync = async () => {
    setSyncing(true)
    setSyncError(null)
    setSyncSuccess(null)
    try {
      const res = await syncOrderToMonday(order.order_number)
      setSyncSuccess(
        res.data?.monday_item_id
          ? `Synced to Monday.com. Item ID: ${res.data.monday_item_id}`
          : 'Sync triggered successfully.'
      )
      setTimeout(() => onAction(), 1500)
    } catch (err) {
      setSyncError(err?.response?.data?.detail || 'Monday.com sync failed.')
    } finally {
      setSyncing(false)
    }
  }

  const canSync = order.monday_sync_status !== 'synced'

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="flex-1 bg-black/40" onClick={onClose} />

      {/* Drawer */}
      <div className="w-full max-w-xl bg-white shadow-2xl flex flex-col overflow-y-auto">

        {/* Header */}
        <div className="bg-navy text-offwhite px-6 py-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-gold font-mono">{order.order_number}</p>
            <h2 className="text-lg font-semibold">{order.client_name}</h2>
          </div>
          <button onClick={onClose} className="text-offwhite/70 hover:text-offwhite text-2xl leading-none">
            &times;
          </button>
        </div>

        <div className="flex-1 p-6 space-y-6">

          {/* Status row */}
          <div className="flex items-center gap-3 flex-wrap">
            <StatusBadge status={order.status} map={STATUS_BADGE} />
            <span className="text-xs text-muted">Created: {fmtDate(order.created_at)}</span>
          </div>

          {/* Info cards */}
          <div className="grid grid-cols-2 gap-4">
            <div className="card space-y-1">
              <p className="text-xs font-semibold text-muted uppercase tracking-wide">Client</p>
              <p className="text-sm font-medium text-navy">{order.client_name}</p>
              {order.contact_email && <p className="text-xs text-muted">{order.contact_email}</p>}
            </div>
            <div className="card space-y-1">
              <p className="text-xs font-semibold text-muted uppercase tracking-wide">Quote</p>
              <p className="text-sm font-mono text-gold">{order.quote_number || '--'}</p>
              <p className="text-sm font-bold text-navy">{fmt(order.total_amount)}</p>
            </div>
          </div>

          {/* Artwork */}
          {(order.artwork_width || order.artwork_height) && (
            <div className="card space-y-1">
              <p className="text-xs font-semibold text-muted uppercase tracking-wide">Artwork Dimensions</p>
              <p className="text-sm text-navy">
                {order.artwork_width}" &times; {order.artwork_height}"
                {order.artwork_notes && ` — ${order.artwork_notes}`}
              </p>
            </div>
          )}

          {/* Integration status */}
          <div className="card space-y-3">
            <p className="text-xs font-semibold text-muted uppercase tracking-wide">Integration Status</p>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 bg-[#F6195C] rounded flex items-center justify-center">
                  <span className="text-white text-xs font-bold">M</span>
                </div>
                <span className="text-sm text-navy">Monday.com</span>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge status={order.monday_sync_status || 'pending'} map={MONDAY_BADGE} />
                {order.monday_item_id && (
                  <span className="text-xs text-muted font-mono">#{order.monday_item_id}</span>
                )}
              </div>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 bg-[#2CA01C] rounded flex items-center justify-center">
                  <span className="text-white text-xs font-bold">Q</span>
                </div>
                <span className="text-sm text-navy">QuickBooks</span>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge status={order.qbo_sync_status || 'pending'} map={QBO_BADGE} />
                {order.qbo_invoice_id && (
                  <span className="text-xs text-muted font-mono">#{order.qbo_invoice_id}</span>
                )}
              </div>
            </div>
          </div>

          {/* Notes */}
          {order.notes && (
            <div className="bg-gray-50 rounded p-3">
              <p className="text-xs font-semibold text-muted uppercase tracking-wide mb-1">Notes</p>
              <p className="text-sm text-navy">{order.notes}</p>
            </div>
          )}

          {/* Sync feedback */}
          {syncError && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2">
              {syncError}
            </p>
          )}
          {syncSuccess && (
            <p className="text-xs text-green-700 bg-green-50 border border-green-200 rounded p-2">
              {syncSuccess}
            </p>
          )}

          {/* Actions */}
          <div className="border-t border-gray-100 pt-4 space-y-3">
            {canSync ? (
              <button
                onClick={doSync}
                disabled={syncing}
                className="btn-primary w-full"
              >
                {syncing ? 'Syncing...' : 'Sync to Monday.com'}
              </button>
            ) : (
              <div className="text-center py-2">
                <p className="text-xs text-green-600 font-medium">
                  Already synced to Monday.com
                </p>
                {order.monday_item_id && (
                  <p className="text-xs text-muted mt-0.5">Item ID: {order.monday_item_id}</p>
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

export default function OrdersPage() {
  const [orders,        setOrders]        = useState([])
  const [loading,       setLoading]       = useState(true)
  const [error,         setError]         = useState(null)
  const [statusFilter,  setStatusFilter]  = useState('')
  const [selectedOrder, setSelectedOrder] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    listOrders(statusFilter || null)
      .then(res => setOrders(res.data.orders))
      .catch(() => setError('Failed to load orders.'))
      .finally(() => setLoading(false))
  }, [statusFilter])

  useEffect(() => { load() }, [load])

  const handleAction = () => {
    setSelectedOrder(null)
    load()
  }

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-navy">Orders</h1>
          <p className="text-sm text-muted mt-0.5">
            {orders.length} order{orders.length !== 1 ? 's' : ''}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            className="input w-48 text-sm"
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
          >
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="confirmed">Confirmed</option>
            <option value="in_production">In Production</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <button onClick={load} className="btn-secondary text-sm">
            Refresh
          </button>
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <p className="text-sm text-muted">Loading orders...</p>
      ) : error ? (
        <p className="text-sm text-red-500">{error}</p>
      ) : orders.length === 0 ? (
        <div className="card text-center py-12">
          <p className="text-muted text-sm">No orders found.</p>
          <p className="text-muted text-xs mt-1">
            Orders are created automatically when a quote is approved.
          </p>
        </div>
      ) : (
        <div className="card p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-semibold text-muted uppercase tracking-wide">Order #</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-muted uppercase tracking-wide">Client</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-muted uppercase tracking-wide">Status</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-muted uppercase tracking-wide">Monday</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-muted uppercase tracking-wide">QBO</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-muted uppercase tracking-wide">Total</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-muted uppercase tracking-wide">Created</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {orders.map(o => (
                <tr
                  key={o.id}
                  className="hover:bg-gray-50 cursor-pointer transition-colors"
                  onClick={() => setSelectedOrder(o)}
                >
                  <td className="px-4 py-3 font-mono text-xs text-gold font-semibold">
                    {o.order_number}
                  </td>
                  <td className="px-4 py-3 font-medium text-navy">{o.client_name}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={o.status} map={STATUS_BADGE} />
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={o.monday_sync_status || 'pending'} map={MONDAY_BADGE} />
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={o.qbo_sync_status || 'pending'} map={QBO_BADGE} />
                  </td>
                  <td className="px-4 py-3 text-right font-semibold text-navy">
                    {fmt(o.total_amount)}
                  </td>
                  <td className="px-4 py-3 text-muted text-xs">{fmtDate(o.created_at)}</td>
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
      {selectedOrder && (
        <OrderDrawer
          order={selectedOrder}
          onClose={() => setSelectedOrder(null)}
          onAction={handleAction}
        />
      )}
    </div>
  )
}
