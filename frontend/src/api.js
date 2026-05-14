import axios from 'axios'

// In production (Vercel), VITE_API_URL points to the Railway backend.
// Locally, /api is proxied to localhost:8000 via vite.config.js.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// ─── Catalog ──────────────────────────────────────────────────────────────────
export const getCatalog = (category = null, activeOnly = true) =>
  api.get('/catalog/', { params: { category, active_only: activeOnly } })

export const getCatalogCategories = () =>
  api.get('/catalog/categories')

export const getCatalogItemBySku = (sku) =>
  api.get(`/catalog/sku/${sku}`)

export const createCatalogItem = (data) =>
  api.post('/catalog/', data)

export const updateCatalogItem = (id, data) =>
  api.patch(`/catalog/${id}`, data)

export const uploadCatalogImage = (id, file) => {
  const form = new FormData()
  form.append('file', file)
  return api.post(`/catalog/${id}/upload-image`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// ─── Pricing ─────────────────────────────────────────────────────────────────
export const calculatePrice = (payload) =>
  api.post('/pricing/calculate', payload)

export const getPricingRules = () =>
  api.get('/pricing/rules')

// ─── Quotes ──────────────────────────────────────────────────────────────────
export const listQuotes = (status = null) =>
  api.get('/quotes/', { params: { status } })

export const getQuote = (quoteNumber) =>
  api.get(`/quotes/${quoteNumber}`)

export const createQuote = (data) =>
  api.post('/quotes/', data)

export const approveQuote = (quoteNumber, syncToQbo = true) =>
  api.post(`/quotes/${quoteNumber}/approve`, { sync_to_qbo: syncToQbo })

export const rejectQuote = (quoteNumber, reason) =>
  api.post(`/quotes/${quoteNumber}/reject`, { reason })

export const sendQuote = (quoteNumber, recipientEmail) =>
  api.post(`/quotes/${quoteNumber}/send`, null, {
    params: { recipient_email: recipientEmail },
  })

// ─── Orders ──────────────────────────────────────────────────────────────────
export const listOrders = (status = null) =>
  api.get('/orders/', { params: { status } })

export const getOrder = (orderNumber) =>
  api.get(`/orders/${orderNumber}`)

export const syncOrderToMonday = (orderNumber) =>
  api.post(`/orders/${orderNumber}/sync-monday`)

export default api
