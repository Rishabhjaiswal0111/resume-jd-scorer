import { createBrowserRouter, Navigate } from 'react-router'

import { RequireAuth } from '@/features/auth/RequireAuth'
import { CandidatePage } from '@/pages/CandidatePage'
import { JobPage } from '@/pages/JobPage'
import { JobsPage } from '@/pages/JobsPage'
import { LoginPage } from '@/pages/LoginPage'
import { NewJobPage } from '@/pages/NewJobPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { SearchPage } from '@/pages/SearchPage'

import { Layout } from './Layout'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: (
      <RequireAuth>
        <Layout />
      </RequireAuth>
    ),
    children: [
      { path: '/', element: <Navigate to="/jobs" replace /> },
      { path: '/jobs', element: <JobsPage /> },
      { path: '/jobs/new', element: <NewJobPage /> },
      { path: '/jobs/:jobId', element: <JobPage /> },
      { path: '/jobs/:jobId/candidates/:jobCandidateId', element: <CandidatePage /> },
      { path: '/search', element: <SearchPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
