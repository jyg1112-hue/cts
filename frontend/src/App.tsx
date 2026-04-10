import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './components/layout/AppLayout'
import { HomePage } from './pages/HomePage'
import { FeaturePlaceholderPage } from './pages/FeaturePlaceholderPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/operations/schedule" element={<FeaturePlaceholderPage />} />
          <Route path="/operations/export" element={<FeaturePlaceholderPage />} />
          <Route path="/operations/data" element={<FeaturePlaceholderPage />} />
          <Route path="/operations/yard" element={<FeaturePlaceholderPage />} />
          <Route
            path="/maintenance/equipment"
            element={<FeaturePlaceholderPage />}
          />
          <Route path="/maintenance/history" element={<FeaturePlaceholderPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
