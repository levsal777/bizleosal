import React from 'react'
import Dashboard from './pages/Dashboard'

export default function App(){
  return (
    <div>
      <header style={{padding: '16px', background: '#0f172a', color:'#fff'}}>
        <h1>BizLeosal — Campaign Analytics (alpha)</h1>
      </header>
      <main style={{padding: '24px'}}>
        <Dashboard />
      </main>
    </div>
  )
}
