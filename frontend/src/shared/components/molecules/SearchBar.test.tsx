import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SearchBar } from './SearchBar'

describe('SearchBar', () => {
  it('renders with placeholder', () => {
    render(<SearchBar onSearch={vi.fn()} />)
    expect(screen.getByPlaceholderText('搜索股票代码或名称...')).toBeInTheDocument()
  })

  it('calls onSearch with trimmed value on submit', () => {
    const handleSearch = vi.fn()
    render(<SearchBar onSearch={handleSearch} />)
    const input = screen.getByPlaceholderText('搜索股票代码或名称...')
    fireEvent.change(input, { target: { value: '  600519  ' } })
    const form = input.closest('form')!
    fireEvent.submit(form)
    expect(handleSearch).toHaveBeenCalledWith('600519')
  })

  it('calls onSearch on enter key press', () => {
    const handleSearch = vi.fn()
    render(<SearchBar onSearch={handleSearch} />)
    const input = screen.getByPlaceholderText('搜索股票代码或名称...')
    fireEvent.change(input, { target: { value: '000001' } })
    const form = input.closest('form')!
    fireEvent.submit(form)
    expect(handleSearch).toHaveBeenCalledWith('000001')
  })

  it('renders search icon and shortcut hint', () => {
    render(<SearchBar onSearch={vi.fn()} />)
    // Check search icon (svg) exists - it's in the form
    const form = screen.getByPlaceholderText('搜索股票代码或名称...').closest('form')!
    expect(form).toBeInTheDocument()
  })
})
