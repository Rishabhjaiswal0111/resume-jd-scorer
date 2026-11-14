import { createBrowserRouter } from 'react-router'

import { HistoryPage } from '@/pages/HistoryPage'
import { HomePage } from '@/pages/HomePage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { RunPage } from '@/pages/RunPage'

import { Layout } from './Layout'

export const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/history', element: <HistoryPage /> },
      { path: '/runs/:runId', element: <RunPage /> },
      // Phase 3: /runs, /runs/:runId, /costs, /rubrics/:rubricId
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
