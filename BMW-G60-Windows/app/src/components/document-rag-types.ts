export interface Assignment {
 category:string; scope_layer:string; quote:string; rationale:string;
 feature?:string|null; value?:string|null; unit?:string|null; variant?:string|null;
}
export interface Passage {
 id:string; evidence_id:string; source_id:string; filename:string; checksum:string;
 model:string|null; market:string|null; origin:string; kind:string;
 locator:Record<string,unknown>; text:string; start:number; end:number;
 assignments:Assignment[]; review_status:string; revision:number; method:string;
}
export function passageLocation(p:Passage){
 const l=p.locator;
 return l.page?`Page ${l.page}`:l.sheet?`${l.sheet} / ${l.range||'row '+l.row}`:`Line ${l.line||'?'}; characters ${p.start}-${p.end}`;
}
