import React, {useEffect, useState} from 'react'

export default function UnitEconomics(){
  const [data,setData]=useState(null)
  useEffect(()=>{
    fetch('/methods/unit-economics/report_sample.json')
      .then(r=>r.json())
      .then(setData)
      .catch(e=>console.error(e))
  },[])

  if(!data) return <div>Loading report...</div>

  return (
    <div>
      <h2>Unit Economics — Report</h2>
      <table style={{width:'100%',borderCollapse:'collapse'}}>
        <thead>
          <tr style={{textAlign:'left'}}>
            <th>Channel</th><th>Revenue</th><th>Cost</th><th>ROAS</th><th>CAC</th><th>AOV</th><th>Recommendation</th>
          </tr>
        </thead>
        <tbody>
          {data.map((r)=>(
            <tr key={r.channel} style={{borderTop:'1px solid #e2e8f0'}}>
              <td>{r.channel}</td>
              <td>{r.revenue.toFixed(2)}</td>
              <td>{r.cost.toFixed(2)}</td>
              <td>{r.roas.toFixed(2)}</td>
              <td>{r.cac.toFixed(2)}</td>
              <td>{r.aov.toFixed(2)}</td>
              <td>{r.recommendation}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3 style={{marginTop:20}}>ROAS chart (simple)</h3>
      <div style={{display:'flex',gap:10,alignItems:'flex-end',height:150}}>
        {data.map(d=> (
          <div key={d.channel} title={d.channel} style={{width:80,background:'#60a5fa',height:`${Math.min(d.roas*100,300)}px`,display:'flex',alignItems:'end',justifyContent:'center',color:'#042c5c'}}>
            <div style={{padding:6,background:'rgba(255,255,255,0.9)',borderRadius:4}}>{d.roas.toFixed(2)}</div>
          </div>
        ))}
      </div>

    </div>
  )
}
