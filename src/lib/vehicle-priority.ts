import type { RequirementView } from './api';

export const COMPONENTS = {
  screen: 'Display & infotainment', vents: 'Climate & air vents', seats: 'Seats & adjustment',
  drivetrain: 'Drivetrain', brakes: 'Brakes', battery: 'Battery & charging',
  steering: 'Steering', lighting: 'Lighting', assistance: 'Driver assistance', storage: 'Luggage compartment',
} as const;
export type ComponentId = keyof typeof COMPONENTS;
export type Concept = 'baseline' | 'screen' | 'vents' | 'seats';
export type CameraView = 'exterior' | 'cabin' | 'top' | 'side';
export type Priority = 'critical' | 'High' | 'Medium' | 'Low' | 'Unscored' | 'none';
export const PRIORITY_COLORS: Record<Priority, string> = {
  critical: '#ef4444', High: '#ef4444', Medium: '#f59e0b', Low: '#32b88e', Unscored: '#529ddd', none: '#607789',
};
export function componentForRequirement(requirement: Pick<RequirementView, 'feature'>): ComponentId | null {
  const feature = requirement.feature.toLowerCase();
  if (/airbag|seat belt|child restraint|child safety/.test(feature)) return null;
  if (/seat|headrest|lumbar/.test(feature)) return 'seats';
  if (/air conditioning|climate|climatization|blower|ventilat|cooling|auxiliary heat/.test(feature)) return 'vents';
  if (/touch.?screen|display|infotainment|navigation|carplay|android auto|controller operation|operating (concept|system)|gesture|voice control/.test(feature)) return 'screen';
  if (/brak|automatic.hold/.test(feature)) return 'brakes';
  if (/steer/.test(feature) && !/assist/.test(feature)) return 'steering';
  if (/drivetrain|engine|transmission|selector lever/.test(feature)) return 'drivetrain';
  if (/charg|electric range|high.voltage battery/.test(feature)) return 'battery';
  if (/light|headlamp/.test(feature) && !/traffic/.test(feature)) return 'lighting';
  if (/assist|collision|cruise|blind spot|lane|camera|park distance/.test(feature)) return 'assistance';
  if (/luggage|trunk|frunk|storage|through.loading/.test(feature)) return 'storage';
  return null;
}
export function componentPriorities(requirements: RequirementView[]): Record<ComponentId, Priority> {
  const result = Object.fromEntries(Object.keys(COMPONENTS).map(id => [id, 'none'])) as Record<ComponentId, Priority>;
  const order: Priority[] = ['critical', 'High', 'Medium', 'Low', 'Unscored', 'none'];
  for (const r of requirements) {
    const id = componentForRequirement(r);
    if (!id) continue;
    const priority: Priority = r.critical ? 'critical' : (['High','Medium','Low'].includes(r.band) ? r.band as Priority : 'Unscored');
    if (order.indexOf(priority) < order.indexOf(result[id])) result[id] = priority;
  }
  return result;
}
// Apply a shape change only when the wording explicitly describes it.
// Ordinary feature selection focuses/highlights the component without inventing an improvement.
export function conceptForRequirement(r: Pick<RequirementView, 'feature' | 'title' | 'description'>): Concept {
  const id = componentForRequirement(r);
  const wording = `${r.title} ${r.description}`.toLowerCase();
  if ((id === 'screen' || id === 'vents') && /larger|bigger|enlarge|increase.*size/.test(wording)) return id;
  if (id === 'seats' && /adjustab|adjustment|recline/.test(wording)) return 'seats';
  return 'baseline';
}

export const DESIGN_CONCEPTS = {
  screen: {title: 'Panoramic display', metric: '+80%', detail: 'display width', description: 'Expanded display · +65% height'},
  vents: {title: 'Expanded air vents', metric: '3×', detail: 'opening height', description: 'Larger openings · +18% span'},
  seats: {title: 'New seat design', metric: 'NEW LOOK', detail: 'upholstery finish', description: 'Teal upholstery · original seat placement and proportions'},
} as const;
export function approvalConcept(r: Pick<RequirementView,'feature'|'design_concept'>): Concept {
  if(r.design_concept)return r.design_concept;
  const part=componentForRequirement(r);
  return part==='screen'||part==='vents'||part==='seats'?part:'baseline';
}
export function approvedConcepts(requirements: RequirementView[]): Exclude<Concept,'baseline'>[] {
  return [...new Set(requirements.filter(r=>r.status==='approved'&&r.design_concept).map(r=>r.design_concept!))];
}

// Demo-only visual fallback. Keep AI classifications and the ten categories intact.
export type DemoPart = ComponentId | 'body';
export function demoPartForRequirement(r:Pick<RequirementView,'feature'|'title'|'description'|'category'>):DemoPart {
  const exact=componentForRequirement(r);
  if(exact)return exact;
  const wording=`${r.feature} ${r.title}`.toLowerCase();
  if(/power|performance|accelerat|horsepower|torque|fuel|engine/.test(wording))return 'drivetrain';
  if(/screen|display|software|connectiv|audio|sound|media/.test(wording))return 'screen';
  if(/seat|comfort|upholstery/.test(wording))return 'seats';
  if(/climate|vent|heating|cooling/.test(wording))return 'vents';
  return ({C01:'drivetrain',C02:'battery',C03:'body',C04:'assistance',C05:'seats',C06:'body',C07:'screen',C08:'seats',C09:'assistance',C10:'body'} as Record<string,DemoPart>)[r.category]||'body';
}
