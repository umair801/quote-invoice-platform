// src/components/MouldingBrowser.jsx
// Displays a grid of moulding catalog items with image thumbnails.
// Clicking a card selects that moulding and fires onSelect(item).

import { useEffect, useState } from 'react'
import { getCatalog } from '../api'

export default function MouldingBrowser({ selectedSku, onSelect }) {
  const [items, setItems]   = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)

  useEffect(() => {
    getCatalog('moulding', true)
      .then(res => setItems(res.data.items))
      .catch(() => setError('Failed to load moulding catalog.'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <p className="text-sm text-muted py-4">Loading moulding catalog...</p>
  )
  if (error) return (
    <p className="text-sm text-red-500 py-4">{error}</p>
  )
  if (items.length === 0) return (
    <p className="text-sm text-muted py-4">No moulding items in catalog.</p>
  )

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
      {items.map(item => {
        const isSelected = item.sku === selectedSku
        return (
          <button
            key={item.sku}
            onClick={() => onSelect(item)}
            className={`text-left rounded-lg border-2 p-3 transition-all duration-150 focus:outline-none
              ${isSelected
                ? 'border-gold bg-gold/10 shadow-md'
                : 'border-gray-200 bg-white hover:border-gold/50 hover:shadow-sm'
              }`}
          >
            {/* Image */}
            <div className="w-full h-24 rounded mb-2 overflow-hidden bg-gray-100 flex items-center justify-center">
              {item.image_url ? (
                <img
                  src={item.image_url}
                  alt={item.name}
                  className="w-full h-full object-cover"
                />
              ) : (
                <span className="text-xs text-gray-400">No image</span>
              )}
            </div>

            {/* Info */}
            <p className="text-xs font-semibold text-navy leading-tight">{item.name}</p>
            {item.color && (
              <p className="text-xs text-muted">{item.color}</p>
            )}
            <p className="text-xs font-medium text-gold mt-1">
              ${item.unit_price.toFixed(2)}/ft
            </p>
            {isSelected && (
              <span className="inline-block mt-1 text-xs bg-gold text-navy font-semibold px-2 py-0.5 rounded-full">
                Selected
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
