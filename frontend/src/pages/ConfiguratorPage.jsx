// src/pages/ConfiguratorPage.jsx
// Pricing configurator: sales rep selects materials, enters dimensions,
// sees live price breakdown, then saves as a draft quote.

import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import MouldingBrowser from '../components/MouldingBrowser'
import CategorySelect  from '../components/CategorySelect'
import PriceBreakdown  from '../components/PriceBreakdown'
import { calculatePrice, createQuote } from '../api'

const DEFAULT_TAX = 0.08875  // NYC default (8.875%)

const emptyForm = {
  // Client info
  client_name:    '',
  client_email:   '',
  client_phone:   '',

  // Artwork
  artwork_title:  '',
  width_inches:   '',
  height_inches:  '',

  // Selections
  moulding_sku:   null,
  glass_sku:      null,
  mat_sku:        null,
  mounting_sku:   null,
  labor_skus:     [],

  // Options
  tax_rate:       DEFAULT_TAX,
  notes:          '',
}

export default function ConfiguratorPage() {
  const navigate = useNavigate()
  const [form, setForm]           = useState(emptyForm)
  const [priceResult, setPriceResult] = useState(null)
  const [calculating, setCalculating] = useState(false)
  const [saving, setSaving]       = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [saveSuccess, setSaveSuccess] = useState(null)
  const debounceRef = useRef(null)

  // ─── Field helpers ──────────────────────────────────────────────────────────
  const set = (field) => (val) => setForm(f => ({ ...f, [field]: val }))
  const setInput = (field) => (e) => setForm(f => ({ ...f, [field]: e.target.value }))

  // ─── Live price calculation (debounced 500ms) ────────────────────────────
  const runCalculation = useCallback((f) => {
    const w = parseFloat(f.width_inches)
    const h = parseFloat(f.height_inches)
    const hasAnyMaterial = f.moulding_sku || f.glass_sku || f.mat_sku ||
                           f.mounting_sku || f.labor_skus.length > 0

    if (!w || !h || w <= 0 || h <= 0 || !hasAnyMaterial) {
      setPriceResult(null)
      return
    }

    setCalculating(true)
    calculatePrice({
      width_inches:  w,
      height_inches: h,
      moulding_sku:  f.moulding_sku  || undefined,
      glass_sku:     f.glass_sku     || undefined,
      mat_sku:       f.mat_sku       || undefined,
      mounting_sku:  f.mounting_sku  || undefined,
      labor_skus:    f.labor_skus,
      tax_rate:      parseFloat(f.tax_rate) || 0,
      notes:         f.notes,
    })
      .then(res => setPriceResult(res.data))
      .catch(() => setPriceResult(null))
      .finally(() => setCalculating(false))
  }, [])

  useEffect(() => {
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => runCalculation(form), 500)
    return () => clearTimeout(debounceRef.current)
  }, [
    form.width_inches, form.height_inches,
    form.moulding_sku, form.glass_sku, form.mat_sku,
    form.mounting_sku, form.labor_skus, form.tax_rate,
    runCalculation,
  ])

  // ─── Save as draft quote ─────────────────────────────────────────────────
  const handleSave = async () => {
    setSaveError(null)
    setSaveSuccess(null)

    if (!form.client_name.trim()) {
      setSaveError('Client name is required.')
      return
    }
    if (!priceResult || !priceResult.line_items.length) {
      setSaveError('Select at least one material and enter dimensions before saving.')
      return
    }

    setSaving(true)
    try {
      const payload = {
        client_info: {
          name:  form.client_name.trim(),
          email: form.client_email.trim(),
          phone: form.client_phone.trim(),
        },
        artwork_specs: {
          title:         form.artwork_title.trim(),
          width_inches:  parseFloat(form.width_inches),
          height_inches: parseFloat(form.height_inches),
        },
        line_items:    priceResult.line_items,
        subtotal:      priceResult.subtotal,
        tax_rate:      priceResult.tax_rate,
        tax_amount:    priceResult.tax,
        total_amount:  priceResult.total,
        notes:         form.notes.trim(),
        status:        'draft',
      }
      const res = await createQuote(payload)
      const qNum = res.data?.quote_number
      setSaveSuccess(`Quote ${qNum} saved as draft.`)
      setTimeout(() => navigate('/quotes'), 1500)
    } catch (err) {
      setSaveError(
        err?.response?.data?.detail || 'Failed to save quote. Please try again.'
      )
    } finally {
      setSaving(false)
    }
  }

  // ─── Reset form ──────────────────────────────────────────────────────────
  const handleReset = () => {
    setForm(emptyForm)
    setPriceResult(null)
    setSaveError(null)
    setSaveSuccess(null)
  }

  // ─── Render ──────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">

      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-navy">New Quote</h1>
          <p className="text-sm text-muted mt-0.5">
            Select materials, enter artwork dimensions, and review live pricing.
          </p>
        </div>
        <button onClick={handleReset} className="btn-secondary text-sm">
          Reset
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* ── Left column: client + dimensions + material selectors ─────── */}
        <div className="lg:col-span-2 space-y-5">

          {/* Client info */}
          <div className="card space-y-4">
            <h2 className="font-semibold text-navy text-base border-b border-gray-100 pb-2">
              Client Information
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="label">Client Name <span className="text-red-500">*</span></label>
                <input className="input" placeholder="Jane Smith"
                  value={form.client_name} onChange={setInput('client_name')} />
              </div>
              <div>
                <label className="label">Email</label>
                <input className="input" type="email" placeholder="jane@example.com"
                  value={form.client_email} onChange={setInput('client_email')} />
              </div>
              <div>
                <label className="label">Phone</label>
                <input className="input" placeholder="(212) 555-0100"
                  value={form.client_phone} onChange={setInput('client_phone')} />
              </div>
            </div>
          </div>

          {/* Artwork dimensions */}
          <div className="card space-y-4">
            <h2 className="font-semibold text-navy text-base border-b border-gray-100 pb-2">
              Artwork Dimensions
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="label">Artwork Title</label>
                <input className="input" placeholder="e.g. Sunset Over Hudson"
                  value={form.artwork_title} onChange={setInput('artwork_title')} />
              </div>
              <div>
                <label className="label">Width (inches) <span className="text-red-500">*</span></label>
                <input className="input" type="number" min="0.1" step="0.25"
                  placeholder="16"
                  value={form.width_inches} onChange={setInput('width_inches')} />
              </div>
              <div>
                <label className="label">Height (inches) <span className="text-red-500">*</span></label>
                <input className="input" type="number" min="0.1" step="0.25"
                  placeholder="20"
                  value={form.height_inches} onChange={setInput('height_inches')} />
              </div>
            </div>
            {form.width_inches && form.height_inches && (
              <p className="text-xs text-muted">
                Area: {(parseFloat(form.width_inches) * parseFloat(form.height_inches) / 144).toFixed(3)} sqft
                &nbsp;|&nbsp;
                Perimeter: {((2 * (parseFloat(form.width_inches) + parseFloat(form.height_inches)) + 16) / 12).toFixed(3)} ft (with waste)
              </p>
            )}
          </div>

          {/* Moulding browser */}
          <div className="card space-y-4">
            <h2 className="font-semibold text-navy text-base border-b border-gray-100 pb-2">
              Moulding
              {form.moulding_sku && (
                <span className="ml-2 text-xs font-normal text-muted">
                  Selected: <span className="font-mono text-gold">{form.moulding_sku}</span>
                  <button
                    onClick={() => set('moulding_sku')(null)}
                    className="ml-2 text-red-400 hover:text-red-600 text-xs"
                  >
                    clear
                  </button>
                </span>
              )}
            </h2>
            <MouldingBrowser
              selectedSku={form.moulding_sku}
              onSelect={(item) => set('moulding_sku')(item.sku)}
            />
          </div>

          {/* Glass, Mat, Mounting */}
          <div className="card space-y-5">
            <h2 className="font-semibold text-navy text-base border-b border-gray-100 pb-2">
              Glazing, Mat & Mounting
            </h2>
            <CategorySelect
              category="glass"
              label="Glass / Glazing"
              value={form.glass_sku}
              onChange={set('glass_sku')}
            />
            <CategorySelect
              category="mat"
              label="Mat Board"
              value={form.mat_sku}
              onChange={set('mat_sku')}
            />
            <CategorySelect
              category="mounting"
              label="Mounting Method"
              value={form.mounting_sku}
              onChange={set('mounting_sku')}
            />
          </div>

          {/* Labor */}
          <div className="card space-y-4">
            <h2 className="font-semibold text-navy text-base border-b border-gray-100 pb-2">
              Labor
            </h2>
            <CategorySelect
              category="labor"
              label="Labor Services (select all that apply)"
              value={form.labor_skus}
              onChange={set('labor_skus')}
              multi={true}
            />
          </div>

          {/* Notes + Tax */}
          <div className="card space-y-4">
            <h2 className="font-semibold text-navy text-base border-b border-gray-100 pb-2">
              Additional Options
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="label">Tax Rate</label>
                <select
                  className="input"
                  value={form.tax_rate}
                  onChange={setInput('tax_rate')}
                >
                  <option value={0}>No Tax (0%)</option>
                  <option value={0.08875}>NYC Tax (8.875%)</option>
                  <option value={0.08}>8%</option>
                  <option value={0.06}>6%</option>
                </select>
              </div>
              <div>
                <label className="label">Notes</label>
                <textarea
                  className="input resize-none"
                  rows={2}
                  placeholder="Special instructions, framing notes..."
                  value={form.notes}
                  onChange={setInput('notes')}
                />
              </div>
            </div>
          </div>
        </div>

        {/* ── Right column: live price breakdown + save button ──────────── */}
        <div className="space-y-4">
          <div className="card sticky top-6">
            <h2 className="font-semibold text-navy text-base border-b border-gray-100 pb-2 mb-4">
              Price Breakdown
            </h2>
            <PriceBreakdown result={priceResult} loading={calculating} />

            {/* Save as draft */}
            <div className="mt-6 space-y-3">
              {saveError && (
                <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2">
                  {saveError}
                </p>
              )}
              {saveSuccess && (
                <p className="text-xs text-green-700 bg-green-50 border border-green-200 rounded p-2">
                  {saveSuccess}
                </p>
              )}
              <button
                onClick={handleSave}
                disabled={saving || calculating || !priceResult?.line_items?.length}
                className="btn-primary w-full"
              >
                {saving ? 'Saving...' : 'Save as Draft Quote'}
              </button>
              <p className="text-xs text-muted text-center">
                Saves to Quotes. You can review, send, and approve from there.
              </p>
            </div>
          </div>
        </div>

      </div>
    </div>
  )
}
