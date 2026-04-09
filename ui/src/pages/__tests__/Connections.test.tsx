import { renderWithProviders, screen, waitFor } from '../../test/test-utils'
import { server } from '../../test/mocks/server'
import { beforeAll, afterAll, afterEach } from 'vitest'
import Connections from '../Connections'

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

describe('Connections', () => {
  it('shows loading state then renders connections', async () => {
    renderWithProviders(<Connections />)

    expect(screen.getByText('Loading...')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('Production PG')).toBeInTheDocument()
    })
    expect(screen.getByText('Staging MySQL')).toBeInTheDocument()
  })

  it('renders connection details in the table', async () => {
    renderWithProviders(<Connections />)

    await waitFor(() => {
      expect(screen.getByText('Production PG')).toBeInTheDocument()
    })

    expect(screen.getByText('db.example.com:5432')).toBeInTheDocument()
    expect(screen.getByText('myapp')).toBeInTheDocument()
  })

  it('shows Add Connection button', async () => {
    renderWithProviders(<Connections />)

    await waitFor(() => {
      expect(screen.getByText('Production PG')).toBeInTheDocument()
    })

    expect(screen.getByText('Add Connection')).toBeInTheDocument()
  })
})
