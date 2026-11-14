import { createBrowserRouter } from 'react-router'

import { HomePage } from '@/pages/HomePage'
import { NotFoundPage } from '@/pages/NotFoundPage'

import { Layout } from './Layout'

export const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <HomePage /> },
      // Phase 3: /runs, /runs/:runId, /costs, /rubrics/:rubricId
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
