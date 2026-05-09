import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Input } from './Input'

describe('Input', () => {
  it('renders without label', () => {
    render(<Input placeholder="Enter text" />)
    expect(screen.getByPlaceholderText('Enter text')).toBeInTheDocument()
  })

  it('renders with label', () => {
    render(<Input label="Stock Code" placeholder="000001" />)
    expect(screen.getByLabelText('Stock Code')).toBeInTheDocument()
  })

  it('updates value on change', () => {
    render(<Input placeholder="Enter code" />)
    const input = screen.getByPlaceholderText('Enter code') as HTMLInputElement
    fireEvent.change(input, { target: { value: '600519' } })
    expect(input.value).toBe('600519')
  })

  it('shows error message when error prop is provided', () => {
    render(<Input placeholder="Enter code" error="Invalid stock code" />)
    expect(screen.getByText('Invalid stock code')).toBeInTheDocument()
  })

  it('handles number type input', () => {
    render(<Input type="number" placeholder="0" />)
    const input = screen.getByPlaceholderText('0')
    expect(input).toHaveAttribute('type', 'number')
  })

  it('forwards ref correctly', () => {
    const ref = { current: null }
    render(<Input ref={ref} placeholder="test" />)
    expect(ref.current).not.toBeNull()
  })
})
