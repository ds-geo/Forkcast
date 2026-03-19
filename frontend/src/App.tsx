import { useState } from 'react'
import './App.css'
import SearchIcon from './assets/mag.png'
import { Restaurant } from './types'

const PRICE_OPTIONS = ['', '$', '$$', '$$$', '$$$$']

function PriceBadge({ range }: { range: string }) {
  if (!range) return null
  return <span className="price-badge">{range}</span>
}

function StarScore({ score }: { score: number }) {
  if (!score) return null
  return <span className="score-badge">★ {score.toFixed(1)}</span>
}

function App(): JSX.Element {
  const [query, setQuery] = useState<string>('')
  const [priceFilter, setPriceFilter] = useState<string>('')
  const [results, setResults] = useState<Restaurant[]>([])
  const [loading, setLoading] = useState<boolean>(false)
  const [searched, setSearched] = useState<boolean>(false)

  const doSearch = async (q: string, price: string) => {
    if (!q.trim()) { setResults([]); setSearched(false); return }
    setLoading(true)
    setSearched(true)
    const params = new URLSearchParams({ q, ...(price ? { price } : {}) })
    const res = await fetch(`/api/search?${params}`)
    const data: Restaurant[] = await res.json()
    setResults(data)
    setLoading(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') doSearch(query, priceFilter)
  }

  const handlePriceChange = (p: string) => {
    setPriceFilter(p)
    doSearch(query, p)
  }

  return (
    <div className="full-body-container">
      {/* Header */}
      <div className="top-text">
        <div className="brand">
          <span className="brand-fork">🍴</span>
          <h1 className="brand-name">Forkcast</h1>
        </div>
        <p className="brand-tagline">Describe what you want to eat — we'll find the spot.</p>

        {/* Search bar */}
        <div className="input-box" onClick={() => document.getElementById('search-input')?.focus()}>
          <img src={SearchIcon} alt="search" />
          <input
            id="search-input"
            placeholder='e.g. "spicy vegetarian noodles" or "cheap late-night burgers"'
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <button className="search-btn" onClick={() => doSearch(query, priceFilter)}>
            Search
          </button>
        </div>

        {/* Price filter */}
        <div className="price-filters">
          {PRICE_OPTIONS.map((p) => (
            <button
              key={p || 'all'}
              className={`price-filter-btn ${priceFilter === p ? 'active' : ''}`}
              onClick={() => handlePriceChange(p)}
            >
              {p || 'Any price'}
            </button>
          ))}
        </div>
      </div>

      {/* Results */}
      <div id="answer-box">
        {loading && (
          <div className="loading-row">
            <div className="loading-dot" />
            <div className="loading-dot" />
            <div className="loading-dot" />
          </div>
        )}

        {!loading && searched && results.length === 0 && (
          <p className="no-results">No restaurants matched your query. Try different keywords.</p>
        )}

        {!loading && results.map((r, i) => (
          <div key={i} className="restaurant-card">
            <div className="card-header">
              <div className="card-title-row">
                <h3 className="restaurant-name">{r.name}</h3>
                <div className="card-badges">
                  <PriceBadge range={r.price_range} />
                  <StarScore score={r.score} />
                </div>
              </div>
              <p className="restaurant-category">{r.category}</p>
              {r.address && <p className="restaurant-address">{r.address}</p>}
            </div>

            {r.matched_items.length > 0 && (
              <div className="menu-items">
                <p className="menu-label">Matched items</p>
                {r.matched_items.map((item, j) => (
                  <div key={j} className="menu-item">
                    <div className="menu-item-header">
                      <span className="menu-item-name">{item.name}</span>
                      {item.price && <span className="menu-item-price">{item.price}</span>}
                    </div>
                    {item.description && (
                      <p className="menu-item-desc">{item.description}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export default App
