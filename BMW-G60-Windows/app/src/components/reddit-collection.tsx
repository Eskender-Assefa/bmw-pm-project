'use client';

import { useEffect, useRef, useState } from 'react';
import { ArrowRight, Check, Download, KeyRound, LoaderCircle, MessageSquareText } from 'lucide-react';
import { api, number, type Job } from '@/lib/api';
import { Button } from './ui/button';
import { Badge, ErrorBox } from './cockpit';

type Model = 'G60' | 'G70' | 'F70';
interface Result {
  requested: number; collected: number; categorized: number; discarded: number; shortfall: number;
  model: Model; ready_for_import: boolean; artifacts: Record<string, string>; imported_source_id?: string;
}

export function RedditCollection({ initialModel, onImported }: { initialModel: string; onImported: (model: Model) => void }) {
  const [model, setModel] = useState<Model>(['G60', 'G70', 'F70'].includes(initialModel) ? initialModel as Model : 'G60');
  const [count, setCount] = useState('100');
  const [runs, setRuns] = useState<Job[]>([]);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [importing, setImporting] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const keyInput = useRef<HTMLInputElement>(null);
  const startedRun = useRef<string | null>(null);
  const revealedRun = useRef<string | null>(null);
  const active = runs.some(run => run.state === 'queued' || run.state === 'running');

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const rows = await api<Job[]>('/reddit/runs', undefined, controller.signal);
        if (!controller.signal.aborted) {
          setRuns(rows);
          const completed = rows.find(run => run.id === startedRun.current && run.state === 'succeeded') as Job | undefined;
          const result = completed?.result as unknown as Result | null;
          if (completed && result?.imported_source_id && revealedRun.current !== completed.id) {
            revealedRun.current = completed.id;
            onImported(result.model);
          }
        }
      } catch (e) {
        if (!controller.signal.aborted) setError((e as Error).message);
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(poll, 2500);
      }
    }
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [refresh]);

  async function collect(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = Number(count);
    if (!/^\d+$/.test(count) || !Number.isSafeInteger(target) || target < 1 || target > 10000) {
      setError('Enter a whole number from 1 to 10,000.'); return;
    }
    if (!keyInput.current?.value.trim()) { setError('Enter your OpenAI API key.'); return; }
    setSubmitting(true);
    setError('');
    try {
      const request = api<Job>('/reddit/runs', { api_key: keyInput.current.value.trim(), model, count: target });
      // The key is never saved in browser storage and is cleared immediately after submission.
      keyInput.current.value = '';
      const run = await request;
      startedRun.current = run.id;
      setRuns(previous => [run, ...previous.filter(item => item.id !== run.id)].slice(0, 10));
      setRefresh(value => value + 1);
    } catch (e) { setError((e as Error).message); }
    finally { setSubmitting(false); }
  }

  async function importRun(run: Job, result: Result) {
    setImporting(run.id);
    setError('');
    try {
      await api('/reddit/runs/' + run.id + '/import', {});
      setRefresh(value => value + 1);
      onImported(result.model);
    } catch (e) { setError((e as Error).message); }
    finally { setImporting(null); }
  }

  return <section className="panel reddit-collection" aria-label="Reddit comment collection">
    <div className="panel-heading"><div><h2><MessageSquareText size={18}/>Collect Reddit comments</h2><p>Collect public Reddit quotations, categorize relevant feedback, and prepare it for your evidence library.</p></div><Badge tone="blue">OpenAI web search</Badge></div>
    <form className="reddit-collection-form" onSubmit={collect} autoComplete="off">
      <label className="reddit-key"><span><KeyRound size={13}/>OpenAI API key</span><input ref={keyInput} type="password" name="openai-key" aria-label="OpenAI API key" autoComplete="off" spellCheck={false} autoCapitalize="none" required minLength={10} maxLength={512} placeholder="Enter your API key" disabled={submitting || active}/><small>Used for this run only. Cleared after submission.</small></label>
      <label><span>Car model</span><select aria-label="Reddit car model" value={model} disabled={submitting || active} onChange={e => setModel(e.target.value as Model)}><option value="G60">BMW G60</option><option value="G70">BMW G70</option><option value="F70">BMW F70</option></select></label>
      <label><span>Comment count</span><input type="text" inputMode="numeric" pattern="[0-9]+" aria-label="Reddit comment count" required value={count} maxLength={5} disabled={submitting || active} onChange={e => setCount(e.target.value)} placeholder="100"/><small>1–10,000 comments requested</small></label>
      <Button type="submit" disabled={submitting || active}>{submitting || active ? <LoaderCircle className="spin" size={15}/> : <ArrowRight size={15}/>} {active ? 'Collection running' : submitting ? 'Starting…' : 'Collect & categorize'}</Button>
    </form>
    <p className="reddit-run-note">This starts paid OpenAI requests. Collection may return fewer comments than requested; categorization removes irrelevant comments. Quotations remain unverified until reviewed. Market and powertrain stay unknown.</p>
    {error && <div className="reddit-run-error"><ErrorBox message={error}/></div>}
    {runs.length > 0 && <div className="reddit-runs" aria-live="polite">{runs.map(run => {
      const result = run.result as unknown as Result | null;
      const pending = run.state === 'queued' || run.state === 'running';
      return <article className="reddit-run" key={run.id}>
        <div className="reddit-run-heading"><strong>BMW {String(run.input.model)} <span>· {number(Number(run.input.count))} requested</span></strong><Badge tone={run.state === 'succeeded' ? 'green' : pending ? 'blue' : 'amber'}>{pending && <LoaderCircle size={12} className="spin"/>}{run.state === 'succeeded' ? 'Complete' : run.state}</Badge></div>
        <p role={pending ? 'status' : undefined}>{run.progress}</p>
        {run.error && <ErrorBox message={run.error}/>}
        {(run.state === 'failed' || run.state === 'interrupted') && <small>Enter your API key again to start a new run. Previous files remain preserved.</small>}
        {result && run.state === 'succeeded' && <>
          <div className="reddit-result-counts"><span><strong>{number(result.collected)}</strong> collected</span><span><strong>{number(result.categorized)}</strong> categorized</span><span><strong>{number(result.discarded)}</strong> filtered out</span>{result.shortfall > 0 && <span className="reddit-shortfall"><strong>{number(result.shortfall)}</strong> collection shortfall</span>}</div>
          <div className="reddit-result-actions"><a className="button button-outline button-sm" href={result.artifacts['categorized.jsonl']}><Download size={13}/>categorized.jsonl</a><a className="button button-outline button-sm" href={result.artifacts['import-bundle.zip']}><Download size={13}/>Import bundle</a><a className="text-link" href={result.artifacts['input.jsonl']}>Collected input</a><a className="text-link" href={result.artifacts['manifest.json']}>Run details</a>
          {result.ready_for_import && <Button size="sm" disabled={!!importing} onClick={() => result.imported_source_id ? onImported(result.model) : void importRun(run, result)}>{importing === run.id ? <LoaderCircle className="spin" size={13}/> : result.imported_source_id ? <Check size={13}/> : <ArrowRight size={13}/>}{result.imported_source_id ? 'View imported comments' : 'Retry import into reviews'}</Button>}</div>
          {!result.ready_for_import && <small>No relevant comments remain to import. The output and collected input are available for inspection.</small>}
        </>}
      </article>;
    })}</div>}
  </section>;
}
