import React from "react";

// Local equirectangular projection: x = R cos(phi0) lambda, y = R phi.
// Inputs are actual CMR polygon coordinates in degrees, never schematic locations.
const WIDTH = 800, HEIGHT = 610, MARGIN = 56;
const bounds = [-105.3, 30.4, -101.6, 33.6];
const cos = Math.cos(32 * Math.PI / 180);
const spanX = (bounds[2] - bounds[0]) * cos;
const spanY = bounds[3] - bounds[1];
const scale = Math.min((WIDTH-2*MARGIN)/spanX,(HEIGHT-2*MARGIN)/spanY);
const tx = lon => MARGIN + (lon-bounds[0])*cos*scale;
const ty = lat => HEIGHT-MARGIN-(lat-bounds[1])*scale;
const path = ring => ring.map(([lon,lat],i) => `${i ? "L" : "M"}${tx(lon)},${ty(lat)}`).join(" ")+" Z";
const region = [[-104.5,31],[-102.5,31],[-102.5,33],[-104.5,33],[-104.5,31]];

export function FootprintMap({rows, selected, onSelect}) {
  const chosen = rows.find(row => row.granule === selected);
  return <div className="methane-map" data-reviewed-rows>
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="group" aria-label="Projected map of real observation footprints over the Permian search region">
      <defs><clipPath id="methane-map-clip"><rect x={MARGIN} y={MARGIN} width={WIDTH-2*MARGIN} height={HEIGHT-2*MARGIN} /></clipPath></defs>
      <rect x={MARGIN} y={MARGIN} width={WIDTH-2*MARGIN} height={HEIGHT-2*MARGIN} fill="var(--background)" stroke="var(--border)" />
      {[-105,-104,-103,-102].map(lon => <g key={lon}><line x1={tx(lon)} x2={tx(lon)} y1={MARGIN} y2={HEIGHT-MARGIN} stroke="var(--border)" /><text x={tx(lon)} y={HEIGHT-MARGIN+26} textAnchor="middle">{Math.abs(lon)}° W</text></g>)}
      {[31,32,33].map(lat => <g key={lat}><line x1={MARGIN} x2={WIDTH-MARGIN} y1={ty(lat)} y2={ty(lat)} stroke="var(--border)" /><text x={MARGIN-10} y={ty(lat)+4} textAnchor="end">{lat}° N</text></g>)}
      <g clipPath="url(#methane-map-clip)">{rows.map((row,index) => {
        let rings=[];try {rings=JSON.parse(row.footprintJSON || "[]");} catch {}
        return rings.map((ring,ri) => <path key={`${row.granule}-${ri}`} d={path(ring)} className={`methane-footprint ${row.granule===selected?"selected":""}`} fillOpacity={selected ? row.granule===selected ? .22 : .025 : .055} tabIndex={0} role="button" aria-label={`Select scene ${row.granule}`} onClick={() => onSelect(row.granule)} onKeyDown={e => {if(e.key==="Enter" || e.key===" "){e.preventDefault();onSelect(row.granule);}}}><title>{`${row.granule}\n${row.observedAt}\nCloud metadata: ${row.cloudPercent ?? "unavailable"}%`}</title></path>);
      })}<path d={path(region)} fill="none" stroke="var(--text)" strokeWidth="2.5" strokeDasharray="8 5" pointerEvents="none" /></g>
      <text x={MARGIN} y={28} className="methane-map-label">PERMIAN REGION · METADATA COVERAGE</text>
      <line x1={WIDTH-180} x2={WIDTH-180+50/111.2*scale} y1={HEIGHT-16} y2={HEIGHT-16} stroke="var(--text)" strokeWidth="3" /><text x={WIDTH-184} y={HEIGHT-22}>50 km (approx.)</text>
    </svg>
    <div className="methane-map-selection" aria-live="polite">{chosen ? <><strong>{chosen.granule}</strong><span>{chosen.observedAt} · Cloud metadata: {chosen.cloudPercent ?? "unavailable"}%</span></> : <span>Select a scene footprint to view its observation identifier.</span>}<button type="button" onClick={() => onSelect(null)}>Clear selection</button></div>
  </div>;
}
