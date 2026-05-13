import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './Layout'
import ConfiguratorPage from './pages/ConfiguratorPage'
import QuotesPage from './pages/QuotesPage'
import OrdersPage from './pages/OrdersPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/configurator" replace />} />
          <Route path="configurator" element={<ConfiguratorPage />} />
          <Route path="quotes"       element={<QuotesPage />} />
          <Route path="orders"       element={<OrdersPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
