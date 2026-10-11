'use client';

export const G60_SKETCHFAB_URL='https://sketchfab.com/models/ee328c2302494193a05cb4949b17ae55/embed';
export function SketchfabG60({onPreview}:{onPreview:()=>void}) {
  return <div className="sketchfab-g60">
    <div className="sketchfab-reference-label"><span>2024 BMW G60</span><span>Reference model</span></div>
    <iframe title="2024 BMW G60 by SLGA on Sketchfab" src={G60_SKETCHFAB_URL} allow="autoplay; fullscreen; xr-spatial-tracking" allowFullScreen loading="lazy" referrerPolicy="strict-origin-when-cross-origin"/>
    <p className="sketchfab-attribution"><a href="https://sketchfab.com/3d-models/2024-bmw-g60-ee328c2302494193a05cb4949b17ae55" target="_blank" rel="noopener noreferrer nofollow">2024 BMW G60</a> by <a href="https://sketchfab.com/csperamune" target="_blank" rel="noopener noreferrer nofollow">SLGA</a> on <a href="https://sketchfab.com" target="_blank" rel="noopener noreferrer nofollow">Sketchfab</a></p>
    <div className="sketchfab-handoff"><strong>See the car. Explore the improvements.</strong><p>Select a ranked need to see flashing parts and design changes in the interactive schematic. The Sketchfab reference itself stays unchanged.</p><button onClick={onPreview}>Preview selected improvement<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M2 7h9M7 3l4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.5"/></svg></button><small>If the model is slow or unavailable, the interactive schematic remains usable.</small></div>
  </div>;
}
