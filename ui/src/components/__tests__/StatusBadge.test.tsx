import { render, screen } from '@testing-library/react'
import StatusBadge from '../StatusBadge'

describe('StatusBadge', () => {
  it('renders the status text', () => {
    render(<StatusBadge status="success" />)
    expect(screen.getByText('success')).toBeInTheDocument()
  })

  it('shows pulse dot for running status', () => {
    const { container } = render(<StatusBadge status="running" />)
    const pulse = container.querySelector('.animate-pulse')
    expect(pulse).toBeInTheDocument()
  })

  it('does not show pulse dot for non-running status', () => {
    const { container } = render(<StatusBadge status="success" />)
    const pulse = container.querySelector('.animate-pulse')
    expect(pulse).not.toBeInTheDocument()
  })

  it('applies custom className', () => {
    render(<StatusBadge status="failed" className="my-class" />)
    const badge = screen.getByText('failed')
    expect(badge).toHaveClass('my-class')
  })

  it('falls back to gray styling for unknown status', () => {
    render(<StatusBadge status="unknown" />)
    const badge = screen.getByText('unknown')
    expect(badge).toHaveClass('bg-gray-100')
  })
})
