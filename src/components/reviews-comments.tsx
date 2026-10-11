'use client';

import { useEffect, useState } from 'react';
import { MessageSquareText, Search, Files, AlertTriangle, ArrowUpRight, ChevronLeft, ChevronRight, Quote, CircleHelp } from 'lucide-react';
import { useApi, cohortQuery, number, type Cohort } from '@/lib/api';
import { Badge, Empty, ErrorBox, Loading } from './cockpit';
import { Button } from './ui/button';
import { RedditCollection } from './reddit-collection';

interface CommentRecord {
  id: string; external_id: string; text: string; model: string; country: string;
  powertrain: string; origin: string; source_date: string | null; source_label: string | null;
  source_id: string; filename: string; duplicate_text: boolean; evidence_id: string | null;
  locator: { sheet?: string; row?: number; range?: string; url?: string } | null;
  aspects: { feature: string; category: string; type: string; status: string; critical: boolean }[];
}
interface CommentResults { items: CommentRecord[]; total: number; source_count: number; critical_count: number }
interface Source { id: string; filename: string; kind: string }
const PAGE_SIZE = 20;
const originLabel = (origin: string) => origin === 'unknown' ? 'Supplied / unverified' : origin === 'synthetic' ? 'Synthetic' : origin === 'observed' ? 'Observed' : 'Origin unknown';

export function ReviewsComments({ cohort, version, categories, onEvidence, onImported }: {
  cohort: Cohort; version: number; categories: Record<string, string>; onEvidence: (id: string) => void; onImported: (model: 'G60' | 'G70' | 'F70') => void;
}) {
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [source, setSource] = useState('');
  const [offset, setOffset] = useState(0);
  useEffect(() => {
    const timeout = setTimeout(() => { setSearch(query); setOffset(0); }, 250);
    return () => clearTimeout(timeout);
  }, [query]);
  const params = cohortQuery(cohort) + '&' + new URLSearchParams({
    q: search, category, source_id: source, offset: String(offset), limit: String(PAGE_SIZE),
  });
  const { data, error, loading } = useApi<CommentResults>('/feedback?' + params, version);
  const { data: sources } = useApi<Source[]>('/sources', version);
  const clearFilters = () => { setQuery(''); setSearch(''); setCategory(''); setSource(''); setOffset(0); };
  const filtering = Boolean(query || category || source);
  return <div className="view-content reviews-workspace">
    <section className="reviews-intro">
      <div className="reviews-intro-icon"><MessageSquareText size={25}/></div>
      <div><div className="eyebrow">VOICE OF THE CUSTOMER</div><h2>Every comment adds context.</h2><p>Read the original feedback, explore feature mappings, and keep the source in view.</p></div>
      <Badge tone="blue">Customer feedback</Badge>
    </section>
    <RedditCollection initialModel={cohort.model || 'G60'} onImported={onImported}/>
    <div className="reviews-metrics" aria-label="Comment results summary" aria-live="polite">
      <section className="metric"><div className="metric-label">Matching comments<MessageSquareText size={18}/></div><strong className="metric-value">{data ? number(data.total) : '—'}</strong><p>Distinct feedback IDs in the current filters</p></section>
      <section className="metric"><div className="metric-label">Source files<Files size={18}/></div><strong className="metric-value">{data ? number(data.source_count) : '—'}</strong><p>Original files behind these comments</p></section>
      <section className="metric"><div className="metric-label">Critical-review flags<AlertTriangle size={18}/></div><strong className="metric-value">{data ? number(data.critical_count) : '—'}</strong><p>Flagged comments requiring closer review</p></section>
    </div>
    <section className="panel" aria-label="Reviews and comments">
      <div className="panel-heading"><div><h2>Reviews & Comments</h2><p>Browse customer statements for the model, market, powertrain, and origin selected above.</p></div><span className="reviews-register-label"><Quote size={16}/> Original wording</span></div>
      <div className="list-toolbar reviews-toolbar">
        <div className="search-input"><Search size={17}/><input aria-label="Search reviews and comments" placeholder="Search comments or feedback IDs…" value={query} onChange={e => setQuery(e.target.value)}/></div>
        <select aria-label="Comment category" value={category} onChange={e => { setCategory(e.target.value); setOffset(0); }}><option value="">All categories</option>{Object.entries(categories).map(([id, name]) => <option key={id} value={id}>{id} · {name}</option>)}</select>
        <select aria-label="Comment source" value={source} onChange={e => { setSource(e.target.value); setOffset(0); }}><option value="">All source files</option>{sources?.filter(s => s.kind === 'customer_statement').map(s => <option key={s.id} value={s.id}>{s.filename}</option>)}</select>
        {filtering && <Button variant="ghost" size="sm" onClick={clearFilters}>Clear filters</Button>}
      </div>
      {error ? <div className="reviews-message"><ErrorBox message={error}/></div> : !data || loading ? <Loading/> : data.items.length ? <>
        <div className="reviews-list">{data.items.map(record => <CommentCard key={record.id} record={record} categories={categories} onEvidence={onEvidence}/>)}</div>
        <div className="pagination">
          <span>{number(offset + 1)}–{number(Math.min(offset + PAGE_SIZE, data.total))} of {number(data.total)} comments</span>
          <div><Button variant="outline" size="icon" aria-label="Previous comments page" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}><ChevronLeft size={15}/></Button><Button variant="outline" size="icon" aria-label="Next comments page" disabled={offset + PAGE_SIZE >= data.total} onClick={() => setOffset(offset + PAGE_SIZE)}><ChevronRight size={15}/></Button></div>
        </div>
      </> : <Empty title="No comments match this view" description="Try another search, category, source, or customer evidence cohort.">{filtering && <Button variant="outline" onClick={clearFilters}>Clear filters</Button>}</Empty>}
      <div className="panel-footnote"><CircleHelp size={14}/><span>One card per source-scoped feedback ID. Multiple feature tags do not create additional comments. These counts do not establish unique customers.</span></div>
    </section>
    <div className="notice quiet"><CircleHelp size={17}/><span>Feature mappings are interpretations with their own review status. Missing dates remain unknown; synthetic and unverified origins stay labeled on every comment.</span></div>
  </div>;
}

function CommentCard({ record, categories, onEvidence }: { record: CommentRecord; categories: Record<string, string>; onEvidence: (id: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const features = [...new Set(record.aspects.map(a => a.feature))];
  const categoryIds = [...new Set(record.aspects.map(a => a.category))];
  const statuses = [...new Set(record.aspects.map(a => a.status))];
  const types = [...new Set(record.aspects.map(a => a.type))];
  const critical = record.aspects.some(a => a.critical);
  const locator = record.locator;
  const location = [locator?.sheet, locator?.range || (locator?.row ? 'Row ' + locator.row : '')].filter(Boolean).join(' · ');
  return <article className="review-comment">
    <div className="review-comment-header"><div className="review-comment-avatar"><Quote size={18}/></div><div className="review-comment-identity"><h3>{record.external_id}</h3><p>{record.model} · {record.country} · {record.powertrain === 'unknown' ? 'Powertrain unknown' : record.powertrain}</p></div><Badge tone={record.origin === 'synthetic' ? 'purple' : record.origin === 'observed' ? 'blue' : 'neutral'}>{originLabel(record.origin)}</Badge></div>
    <div className="review-comment-tags">{categoryIds.map(id => <span className="badge" key={id} title={categories[id]}>{id} · {categories[id] || 'Unclassified'}</span>)}{critical && <Badge tone="red"><AlertTriangle size={11}/>Critical review</Badge>}</div>
    <blockquote className={expanded ? 'review-comment-text expanded' : 'review-comment-text'}>{record.text}</blockquote>
    {record.text.length > 280 && <button className="text-link review-expand" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? 'Show less' : 'Read full comment'}</button>}
    <div className="review-comment-context"><span>Feature mappings</span><p>{features.length ? features.join(' · ') : 'No feature mapping yet'}</p><div>{types.map(type => <Badge key={type}>{type}</Badge>)}{statuses.map(status => <Badge key={status} tone={status === 'reviewed' ? 'green' : status === 'rejected' ? 'red' : 'amber'}>Mapping: {status}</Badge>)}</div></div>
    {record.duplicate_text && <p className="review-duplicate"><CircleHelp size={13}/> Identical wording exists under other feedback IDs.</p>}
    <div className="review-comment-footer"><div><strong title={record.filename}><Files size={13}/>{record.filename}</strong><small>{location || 'Source location available in original file'} · {record.source_date || 'Feedback date unknown'}</small></div>{record.evidence_id ? <Button variant="outline" size="sm" onClick={() => onEvidence(record.evidence_id!)}>View original<ArrowUpRight size={13}/></Button> : <a className="text-link" href={'/api/v1/sources/' + encodeURIComponent(record.source_id) + '/file'} target="_blank" rel="noreferrer">Open source file<ArrowUpRight size={13}/></a>}</div>
  </article>;
}
