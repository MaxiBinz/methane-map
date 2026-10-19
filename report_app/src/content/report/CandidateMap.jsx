import React from "react";

const W=800,H=680,M=58,B=[-104.5,31,-102.5,33],C=Math.cos(32*Math.PI/180);
const S=Math.min((W-2*M)/((B[2]-B[0])*C),(H-2*M)/(B[3]-B[1]));
const X=lon=>M+(lon-B[0])*C*S, Y=lat=>H-M-(lat-B[1])*S;
const ringPath=ring=>ring.map(([x,y],i)=>`${i?"L":"M"}${X(x)},${Y(y)}`).join(" ")+" Z";
const geometryPaths=g=>g?.type==="Polygon"?g.coordinates.map(ringPath):g?.type==="MultiPolygon"?g.coordinates.flatMap(p=>p.map(ringPath)):[];
const colors={E:"#20758a",C:"#a16d25"};
const fmt=x=>x===null||x===undefined?"Unavailable":Number(x).toLocaleString(undefined,{maximumFractionDigits:1});

export function CandidateMap({rows,selected,onSelect}) {
 const chosen=rows.find(r=>r.candidate_id===selected);
 return <div className="candidate-explorer" data-reviewed-rows>
  <svg viewBox={`0 0 ${W} ${H}`} role="group" aria-label="Projected map of measured enhancement component polygons and centroids">
   <rect x={M} y={M} width={(B[2]-B[0])*C*S} height={(B[3]-B[1])*S} fill="var(--background)" stroke="var(--border)" />
   {[-104.5,-104,-103.5,-103,-102.5].map(lon=><g key={lon}><line x1={X(lon)} x2={X(lon)} y1={M} y2={H-M} stroke="var(--border)"/><text x={X(lon)} y={H-M+26} textAnchor="middle">{Math.abs(lon)}°W</text></g>)}
   {[31,31.5,32,32.5,33].map(lat=><g key={lat}><line x1={M} x2={X(B[2])} y1={Y(lat)} y2={Y(lat)} stroke="var(--border)"/><text x={M-10} y={Y(lat)+4} textAnchor="end">{lat}°N</text></g>)}
   <text x={M} y={28} className="methane-map-label">SCREENING COMPONENTS · CENTROIDS ARE NOT SOURCES</text>
   {rows.map(row=>{
     let geometry;try{geometry=JSON.parse(row.geometryJSON);}catch{}
     const color=colors[row.category]??"#737373",active=selected===row.candidate_id;
     return <g key={row.candidate_id} className="candidate-map-mark" role="button" tabIndex={0} aria-label={`Inspect ${row.candidate_id}, category ${row.category}`} onClick={()=>onSelect(row.candidate_id)} onKeyDown={e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();onSelect(row.candidate_id);}}}>
      {geometryPaths(geometry).map((d,i)=><path key={i} d={d} stroke={color} fill={color} fillOpacity=".25" strokeWidth={active?3:1.2}/>)}
      <circle cx={X(row.longitude)} cy={Y(row.latitude)} r={active?8:5} stroke={color} fill={active?color:"var(--background)"} strokeWidth="2"/>
      <title>{`${row.candidate_id} · ${row.category}\n${row.observed_at}\nPeak: ${fmt(row.peak_ppm_m)} ppm m\n${row.novelty}`}</title>
     </g>;
   })}
   <line x1={X(-103)} x2={X(-103)+50/111.2*S} y1={H-14} y2={H-14} stroke="var(--text)" strokeWidth="3"/><text x={X(-103)} y={H-22}>50 km (approx.)</text>
  </svg>
  <div className="candidate-legend"><span><i style={{background:colors.E}}/> E · published-observation neighborhood</span><span><i style={{background:colors.C}}/> C · ambiguous enhancement</span></div>
  <label className="candidate-chooser">Inspect a component <select value={selected??""} onChange={e=>onSelect(e.target.value||null)}><option value="">Choose a component</option>{rows.map(r=><option key={r.candidate_id} value={r.candidate_id}>{r.candidate_id} · {r.category} · {r.observed_at.slice(0,10)}</option>)}</select></label>
  {chosen&&<div className="candidate-detail" aria-live="polite">
    <div><strong>{chosen.candidate_id}</strong><span>Category {chosen.category} · {chosen.role}</span></div>
    <dl><dt>Observation (UTC)</dt><dd>{chosen.observed_at}</dd><dt>Peak corrected enhancement</dt><dd>{fmt(chosen.peak_ppm_m)} ppm m</dd><dt>Support</dt><dd>{fmt(chosen.pixel_count)} pixels</dd><dt>Median sensor statistic</dt><dd>{fmt(chosen.median_sensor_snr)}</dd><dt>Initial assessment</dt><dd>{chosen.initial_assessment}</dd><dt>Visual inspection</dt><dd>{chosen.visualNote || "Unavailable"}</dd><dt>Audit flags</dt><dd>{chosen.auditFlagsText || "No automated audit flags; physical interpretation remains unverified"}</dd><dt>Baseline screen flags</dt><dd>{chosen.flagsText||"No baseline screen flags; physical interpretation remains unverified"}</dd><dt>Unchecked evidence</dt><dd>{chosen.uncheckedText}</dd></dl>
  </div>}
 </div>;
}
