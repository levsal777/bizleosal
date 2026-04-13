import React from 'react'

export default function Dashboard(){
  return (
    <div>
      <h2>Dashboard</h2>
      <p>Загрузите CSV с данными кампании или выберите sample data.</p>
      <div style={{marginTop:20}}>
        <button>Upload CSV</button>
        <button style={{marginLeft:10}}>Use sample data</button>
      </div>

      <section style={{marginTop:30}}>
        <h3>Available Methods</h3>
        <ul>
          <li>SWOT</li>
          <li>PESTEL</li>
          <li>Porter's Five Forces</li>
          <li>McKinsey 7S</li>
          <li><a href="/unit-economics.html">Unit Economics (open)</a></li>
          <li>AARRR</li>
          <li>RFM</li>
          <li>BCG Matrix</li>
        </ul>
      </section>

      <section style={{marginTop:30}}>
        <h3>Last run</h3>
        <p>No runs yet.</p>
      </section>
    </div>
  )
}
