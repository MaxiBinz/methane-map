import React from "react";
import { RichNarrative } from "../../data-app-public.jsx";

export function ScientificFigure({figure}) {
 const [zoom,setZoom]=React.useState(false);
 return <figure className="methane-figure">
   <div className="figure-image-controls"><button type="button" aria-pressed={zoom} onClick={()=>setZoom(!zoom)}>{zoom?"Fit image to report":"Zoom scientific image"}</button></div>
   <div className={`figure-image-viewport${zoom?" is-zoomed":""}`} tabIndex={zoom?0:undefined} aria-label={zoom?"Scrollable enlarged scientific image":undefined}>
      <img src={figure.src} alt={figure.alt} style={{width:zoom?"2560px":"100%",maxWidth:zoom?"none":"100%"}} />
   </div>
   <RichNarrative id={`${figure.id}:caption`} value={figure.caption} label="Edit scientific figure caption" />
 </figure>;
}
