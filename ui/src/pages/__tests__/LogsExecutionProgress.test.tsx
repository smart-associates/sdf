import { renderWithProviders, screen, waitFor } from '../../test/test-utils'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '../../test/mocks/server'
import { beforeAll, afterAll, afterEach } from 'vitest'
import Logs from '../Logs'
import { Execution } from '../../api/executions'
import { Job } from '../../api/jobs'

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

const mockJob: Job = {
  id: 1,
  name: 'Nightly Sync',
  source_connection_id: 1,
  tables: [],
  target_connection_id: 2,
  create_target_table: false,
  migration_mode: 'append',
}

const mockExecution: Execution = {
  id: 100,
  job_id: 1,
  status: 'running',
  started_at: '2026-01-01T00:00:00Z',
  record_count: 60,
  tables: [
    { id: 1, execution_id: 100, table_name: 'public.orders', status: 'running', started_at: '2026-01-01T00:00:00Z', record_count: 50, estimated_row_count: 100 },
    { id: 2, execution_id: 100, table_name: 'public.customers', status: 'success', started_at: '2026-01-01T00:00:00Z', record_count: 10, estimated_row_count: 10 },
  ],
}

describe('Execution logs overall progress bar', () => {
  it('renders the aggregate progress bar when an execution row is expanded', async () => {
    server.use(
      http.get('*/api/executions', () => HttpResponse.json([mockExecution])),
      http.get('*/api/jobs', () => HttpResponse.json([mockJob])),
      http.get('*/api/executions/100/logs', () => HttpResponse.json([])),
    )
    renderWithProviders(<Logs />)

    const row = await screen.findByText('#100')
    await userEvent.click(row)

    // (min(50,100) + min(10,10)) / (100 + 10) = 60/110 = 55%
    await waitFor(() => {
      expect(screen.getByText('1/2 tables · 55%')).toBeInTheDocument()
    })
  })
})
