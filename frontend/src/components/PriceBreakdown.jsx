// src/components/PriceBreakdown.jsx
// Displays the computed line items table + subtotal, tax, and total.
// Shows a loading spinner while the calculation is in flight.

export default function PriceBreakdown({ result, loading }) {
  if (loading) return (
    <div className="flex items-center gap-2 py-6 text-muted text-sm">
      <svg className="animate-spin h-4 w-4 text-gold" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
      </svg>
      Calculating price...
    </div>
  )

  if (!result) return (
    <p className="text-sm text-muted py-6">
      Select materials and enter dimensions to see pricing.
    </p>
  )

  const { line_items, subtotal, tax_rate, tax, total, errors } = result

  return (
    <div className="space-y-4">
      {/* Errors */}
      {errors && errors.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded p-3 space-y-1">
          {errors.map((e, i) => (
            <p key={i} className="text-xs text-red-600">{e}</p>
          ))}
        </div>
      )}

      {/* Line items table */}
      {line_items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-2 text-xs font-semibold text-muted uppercase tracking-wide">#</th>
                <th className="text-left py-2 text-xs font-semibold text-muted uppercase tracking-wide">Item</th>
                <th className="text-left py-2 text-xs font-semibold text-muted uppercase tracking-wide">SKU</th>
                <th className="text-right py-2 text-xs font-semibold text-muted uppercase tracking-wide">Qty</th>
                <th className="text-right py-2 text-xs font-semibold text-muted uppercase tracking-wide">Unit Price</th>
                <th className="text-right py-2 text-xs font-semibold text-muted uppercase tracking-wide">Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {line_items.map(item => (
                <tr key={item.line_number} className="hover:bg-gray-50">
                  <td className="py-2.5 text-muted text-xs">{item.line_number}</td>
                  <td className="py-2.5">
                    <p className="font-medium text-navy">{item.description}</p>
                    {item.notes && (
                      <p className="text-xs text-muted">{item.notes}</p>
                    )}
                  </td>
                  <td className="py-2.5 text-xs text-muted font-mono">{item.sku}</td>
                  <td className="py-2.5 text-right text-navy">
                    {item.quantity.toFixed(3)}
                    <span className="text-xs text-muted ml-1">{item.unit_of_measure}</span>
                  </td>
                  <td className="py-2.5 text-right text-navy">${item.unit_price.toFixed(2)}</td>
                  <td className="py-2.5 text-right font-semibold text-navy">${item.total.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Totals */}
      {line_items.length > 0 && (
        <div className="border-t border-gray-200 pt-4 space-y-1.5">
          <div className="flex justify-between text-sm text-muted">
            <span>Subtotal</span>
            <span className="text-navy font-medium">${subtotal.toFixed(2)}</span>
          </div>
          {tax_rate > 0 && (
            <div className="flex justify-between text-sm text-muted">
              <span>Tax ({(tax_rate * 100).toFixed(3)}%)</span>
              <span className="text-navy font-medium">${tax.toFixed(2)}</span>
            </div>
          )}
          <div className="flex justify-between text-base font-bold text-navy border-t border-gray-200 pt-2 mt-2">
            <span>Total</span>
            <span className="text-gold text-lg">${total.toFixed(2)}</span>
          </div>
        </div>
      )}

      {line_items.length === 0 && (!errors || errors.length === 0) && (
        <p className="text-sm text-muted py-4">
          No items selected. Choose at least one material above.
        </p>
      )}
    </div>
  )
}
