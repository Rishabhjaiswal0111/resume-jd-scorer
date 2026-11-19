import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { JobForm, MIN_JD_CHARS } from './JobForm'

describe('JobForm', () => {
  it('previews pasted text and only submits it once long enough', () => {
    const onSubmit = vi.fn()
    render(<JobForm onSubmit={onSubmit} pending={false} />)
    fireEvent.click(screen.getByRole('radio', { name: 'Paste text' }))
    const box = screen.getByLabelText('Job description text')
    fireEvent.change(box, { target: { value: 'Senior Engineer' } })
    expect(screen.getByLabelText('Job description preview')).toHaveTextContent('Senior Engineer')
    expect(screen.getByRole('button', { name: /Add job/ })).toBeDisabled()

    const text = 'Senior Engineer\n' + 'x'.repeat(MIN_JD_CHARS)
    fireEvent.change(box, { target: { value: text } })
    fireEvent.click(screen.getByRole('button', { name: /Add job/ }))
    expect(onSubmit).toHaveBeenCalledWith(text)
  })

  it('previews a chosen PDF in the page before adding it', () => {
    URL.createObjectURL = vi.fn(() => 'blob:preview')
    URL.revokeObjectURL = vi.fn()
    render(<JobForm onSubmit={vi.fn()} pending={false} />)
    const file = new File(['%PDF-1.4'], 'jd.pdf', { type: 'application/pdf' })
    fireEvent.change(screen.getByLabelText('Job description PDF'), { target: { files: [file] } })
    expect(screen.getByTitle('Job description preview')).toHaveAttribute('src', 'blob:preview')
    expect(screen.getByRole('button', { name: /Add job/ })).toBeEnabled()
  })
})
