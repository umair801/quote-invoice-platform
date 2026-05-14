// src/components/CategorySelect.jsx
// Generic dropdown selector for glass, mat, mounting, and labor catalog items.
// Loads items for a given category from the API on mount.

import { useEffect, useState } from 'react'
import { getCatalog } from '../api'

export default function CategorySelect({
  category,
  label,
  value,
  onChange,
  multi = false,
}) {
  const [items, setItems]     = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    getCatalog(category, true)
      .then(res => setItems(res.data.items))
      .catch(() => setError(`Failed to load ${category} options.`))
      .finally(() => setLoading(false))
  }, [category])

  const unitLabel = (item) => {
    const map = {
      per_foot:  '/ft',
      per_sqft:  '/sqft',
      per_hour:  '/hr',
      each:      ' ea',
    }
    return map[item.unit_of_measure] || ''
  }

  if (loading) return (
    <div>
      <label className="label">{label}</label>
      <p className="text-xs text-muted">Loading...</p>
    </div>
  )
  if (error) return (
    <div>
      <label className="label">{label}</label>
      <p className="text-xs text-red-500">{error}</p>
    </div>
  )

  // Multi-select: render checkboxes (used for labor)
  if (multi) {
    const selected = Array.isArray(value) ? value : []
    const toggle = (sku) => {
      if (selected.includes(sku)) {
        onChange(selected.filter(s => s !== sku))
      } else {
        onChange([...selected, sku])
      }
    }
    return (
      <div>
        <label className="label">{label}</label>
        <div className="space-y-2">
          {items.map(item => (
            <label
              key={item.sku}
              className="flex items-center gap-3 p-2.5 rounded border border-gray-200
                         bg-white hover:border-gold/50 cursor-pointer transition-colors"
            >
              <input
                type="checkbox"
                checked={selected.includes(item.sku)}
                onChange={() => toggle(item.sku)}
                className="accent-gold w-4 h-4"
              />
              <span className="flex-1 text-sm text-navy">{item.name}</span>
              <span className="text-sm font-medium text-gold">
                ${item.unit_price.toFixed(2)}{unitLabel(item)}
              </span>
            </label>
          ))}
        </div>
      </div>
    )
  }

  // Single select: render a styled dropdown
  return (
    <div>
      <label className="label">{label}</label>
      <select
        value={value || ''}
        onChange={e => onChange(e.target.value || null)}
        className="input"
      >
        <option value="">-- None --</option>
        {items.map(item => (
          <option key={item.sku} value={item.sku}>
            {item.name} — ${item.unit_price.toFixed(2)}{unitLabel(item)}
          </option>
        ))}
      </select>
    </div>
  )
}
