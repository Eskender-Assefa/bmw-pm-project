import type { RequirementView } from './api';
export type RequirementSort = 'priority' | 'demand' | 'impact' | 'name';
const bandOrder:Record<string,number>={High:0,Medium:1,Low:2,Unscored:3};
export function sortRequirements(rows:RequirementView[],sort:RequirementSort='priority',descending=true) {
  return [...rows].sort((a,b)=>{
    let order=0;
    if(sort==='priority')order=Number(b.critical)-Number(a.critical)||(bandOrder[a.band]??3)-(bandOrder[b.band]??3)||(b.demand??-1)-(a.demand??-1);
    if(sort==='demand')order=(b.demand??-1)-(a.demand??-1);
    if(sort==='impact')order=(bandOrder[a.band]??3)-(bandOrder[b.band]??3)||(b.demand??-1)-(a.demand??-1);
    if(sort==='name')order=a.feature.localeCompare(b.feature);
    return (descending?1:-1)*(order||a.id.localeCompare(b.id));
  });
}
