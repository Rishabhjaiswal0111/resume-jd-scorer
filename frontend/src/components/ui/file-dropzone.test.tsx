import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'

import { FileDropzone } from './file-dropzone'

function Harness() {
  const [file, setFile] = useState<File | null>(null)
  return (
    <FileDropzone label="Resume (PDF)" hint="PDF" accept=".pdf" file={file} onChange={setFile} />
  )
}

const pdf = new File(['%PDF-1.4 hello'], 'cv.pdf', { type: 'application/pdf' })

describe('FileDropzone', () => {
  it('accepts a dropped file and shows it as a removable chip', () => {
    render(<Harness />)
    const zone = screen.getByText(/or drag it here/).closest('label')!
    fireEvent.dragOver(zone)
    fireEvent.drop(zone, { dataTransfer: { files: [pdf] } })
    expect(screen.getByText('cv.pdf')).toBeInTheDocument()
    expect(screen.getByText('1 KB')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Remove cv.pdf' }))
    expect(screen.queryByText('cv.pdf')).toBeNull()
    expect(screen.getByLabelText('Resume (PDF)')).toBeInTheDocument()
  })

  it('keeps a real (keyboard-reachable) file input for click / keyboard users', () => {
    render(<Harness />)
    const input = screen.getByLabelText('Resume (PDF)')
    expect(input).toHaveAttribute('type', 'file')
    fireEvent.change(input, { target: { files: [pdf] } })
    expect(screen.getByText('cv.pdf')).toBeInTheDocument()
  })
})
