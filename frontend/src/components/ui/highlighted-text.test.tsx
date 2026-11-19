import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { HighlightedText } from './highlighted-text'

describe('HighlightedText', () => {
  it('marks the wrapped words', () => {
    const { container } = render(
      <HighlightedText text={'Built \u0001React\u0002 apps with \u0001TypeScript\u0002.'} />,
    )
    expect([...container.querySelectorAll('mark')].map((m) => m.textContent)).toEqual([
      'React',
      'TypeScript',
    ])
    expect(container.textContent).toBe('Built React apps with TypeScript.')
  })

  it('never renders markup from the text', () => {
    const { container } = render(
      <HighlightedText text={'<img src=x onerror=alert(1)> \u0001<b>x</b>\u0002'} />,
    )
    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('b')).toBeNull()
    expect(container.textContent).toContain('<img src=x onerror=alert(1)>')
  })
})
