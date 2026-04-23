import { useRef, useState } from 'react';
import { getCampaignStreamUrl, parseSseResponse } from '@/lib/campaignApi';
import { CAMPAIGN_FORM_DEFAULTS } from './campaignFormDefaults';
import styles from './CampaignPage.module.scss';

type ProductField = { id: string; name: string };
type Status = 'idle' | 'generating' | 'done' | 'error';

type Creative = {
  key: string;
  productId: string;
  ratio: string;
  imageUrl: string;
};

type CompletePayload = {
  elapsed_ms: number;
  genai_calls: number;
  cache_hits: number;
  report_path?: string;
  report_md_path?: string;
  legal_ok?: boolean;
  localization_applied?: boolean;
  all_checks_pass?: boolean;
};

type CheckRow = {
  key: string;
  productId: string;
  ratio: string;
  legalOk: boolean;
  brandOk: boolean;
  brandIssues: string[];
  legalHitTerms: string[];
};

export default function CampaignPage() {
  const [form, setForm] = useState(CAMPAIGN_FORM_DEFAULTS);
  const [status, setStatus] = useState<Status>('idle');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [creatives, setCreatives] = useState<Creative[]>([]);
  const [totalExpected, setTotalExpected] = useState(0);
  const [complete, setComplete] = useState<CompletePayload | null>(null);
  const [overviewMsg, setOverviewMsg] = useState<string | null>(null);
  const [legalStatus, setLegalStatus] = useState<{ ok: boolean; terms: string[] } | null>(null);
  const [checkRows, setCheckRows] = useState<CheckRow[]>([]);
  const [heroSteps, setHeroSteps] = useState<string[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  const setProduct = (index: number, patch: Partial<ProductField>) => {
    setForm((f) => {
      const next = [...f.products];
      next[index] = { ...next[index], ...patch };
      return { ...f, products: next };
    });
  };

  const addProduct = () => {
    setForm((f) => ({
      ...f,
      products: [...f.products, { id: `product-${f.products.length + 1}`, name: '' }],
    }));
  };

  const removeProduct = (index: number) => {
    setForm((f) => {
      if (f.products.length <= 2) return f;
      const next = f.products.filter((_, i) => i !== index);
      return { ...f, products: next };
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setCreatives([]);
    setComplete(null);
    setOverviewMsg(null);
    setLegalStatus(null);
    setCheckRows([]);
    setHeroSteps([]);
    setStatus('generating');
    for (const p of form.products) {
      if (!p.id.trim() || !p.name.trim()) {
        setErrorMsg('Each product needs an id and name');
        setStatus('error');
        return;
      }
    }

    const body = {
      campaign_name: form.campaignName || null,
      products: form.products.map((p) => ({ id: p.id.trim(), name: p.name.trim() })),
      target_region: form.targetRegion,
      target_audience: form.targetAudience,
      campaign_message: form.campaignMessage,
      overlay_locale: form.overlayLocale?.trim() || null,
    };

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch(getCampaignStreamUrl(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || res.statusText);
      }
      for await (const evt of parseSseResponse(res)) {
        const t = evt.type as string;
        if (t === 'overview') {
          const tc = evt.total_creatives as number;
          setTotalExpected(tc);
          setOverviewMsg(
            `Run ${evt.run_id as string} — ${evt.product_count as number} products, ${tc} creatives`,
          );
        } else if (t === 'creative') {
          const productId = evt.product_id as string;
          const ratio = evt.ratio as string;
          const imageUrl = evt.image_url as string;
          setCreatives((c) => [
            ...c,
            { key: `${productId}-${ratio}`, productId, ratio, imageUrl },
          ]);
        } else if (t === 'legal_check') {
          setLegalStatus({
            ok: Boolean(evt.ok),
            terms: (evt.hit_terms as string[] | undefined) ?? [],
          });
        } else if (t === 'product_start') {
          const pid = String(evt.product_id ?? '');
          const src = String(evt.source ?? '');
          const line =
            src === 'local'
              ? `${pid}: using local hero from input_assets/`
              : `${pid}: generating hero (Claude + Luma — often 30–90s)…`;
          setHeroSteps((prev) => [...prev, line]);
        } else if (t === 'check_result') {
          const productId = evt.product_id as string;
          const ratio = evt.ratio as string;
          setCheckRows((rows) => [
            ...rows,
            {
              key: `${productId}-${ratio}-${rows.length}`,
              productId,
              ratio,
              legalOk: Boolean(evt.legal_ok),
              brandOk: Boolean(evt.brand_ok),
              brandIssues: (evt.brand_issues as string[] | undefined) ?? [],
              legalHitTerms: (evt.legal_hit_terms as string[] | undefined) ?? [],
            },
          ]);
        } else if (t === 'complete') {
          setComplete({
            elapsed_ms: evt.elapsed_ms as number,
            genai_calls: (evt.genai_calls as number) ?? 0,
            cache_hits: (evt.cache_hits as number) ?? 0,
            report_path: evt.report_path as string | undefined,
            report_md_path: evt.report_md_path as string | undefined,
            legal_ok: evt.legal_ok as boolean | undefined,
            localization_applied: evt.localization_applied as boolean | undefined,
            all_checks_pass: evt.all_checks_pass as boolean | undefined,
          });
          setStatus('done');
        } else if (t === 'error') {
          setStatus('error');
          setErrorMsg((evt.message as string) || 'Unknown error');
        }
      }
    } catch (err) {
      if ((err as Error).name === 'AbortError') {
        setStatus('idle');
        return;
      }
      setStatus('error');
      setErrorMsg((err as Error).message);
    } finally {
      abortRef.current = null;
    }
  };

  const handleCancel = () => {
    abortRef.current?.abort();
    setStatus('idle');
  };

  const isGenerating = status === 'generating';
  const progress =
    totalExpected > 0 ? Math.round((creatives.length / totalExpected) * 100) : 0;

  return (
    <div className={styles.page}>
      <header className={styles.pageHeader}>
        <h1>Campaign creative studio</h1>
        <p className={styles.subtitle}>
          <strong>Assets are not uploaded in the browser.</strong> Put files on disk under{' '}
          <code>input_assets/&lt;product id&gt;/hero.png</code> (same name as each product’s id field);
          the API reuses them or calls Claude + Luma if missing. SSE streams to this page; PNGs are
          written under <code>output/</code>.
        </p>
      </header>

      <form className={styles.form} onSubmit={handleSubmit}>
        <div className={styles.field}>
          <label htmlFor="cn">Campaign name (optional)</label>
          <input
            id="cn"
            value={form.campaignName}
            onChange={(e) => setForm((f) => ({ ...f, campaignName: e.target.value }))}
            disabled={isGenerating}
          />
        </div>
        <div className={styles.field}>
          <label>Products (at least 2)</label>
          <p className={styles.fieldHint}>
            Each product is separate in the brief (assignment minimum: ≥2 products). On disk, each{' '}
            <strong>product id</strong> has its own optional hero:{' '}
            <code>input_assets/&lt;id&gt;/hero.png</code> — two products means two folders and up to
            two hero files, not one image shared by both.
          </p>
          <div className={styles.productsBlock}>
            {form.products.map((p, i) => (
              <div key={i} className={styles.productRow}>
                <div className={styles.field}>
                  <label htmlFor={`pi-${i}`}>Product id (folder name)</label>
                  <input
                    id={`pi-${i}`}
                    value={p.id}
                    onChange={(e) => setProduct(i, { id: e.target.value })}
                    required
                    disabled={isGenerating}
                    placeholder="insulated-trail-bottle"
                  />
                </div>
                <div className={styles.field}>
                  <label htmlFor={`pn-${i}`}>Name</label>
                  <input
                    id={`pn-${i}`}
                    value={p.name}
                    onChange={(e) => setProduct(i, { name: e.target.value })}
                    required
                    disabled={isGenerating}
                  />
                </div>
                <button
                  type="button"
                  className={styles.removeBtn}
                  onClick={() => removeProduct(i)}
                  disabled={isGenerating || form.products.length <= 2}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
          <button
            type="button"
            className={styles.addBtn}
            onClick={addProduct}
            disabled={isGenerating}
          >
            Add product
          </button>
        </div>
        <div className={styles.row}>
          <div className={styles.field}>
            <label htmlFor="tr">Target region</label>
            <input
              id="tr"
              value={form.targetRegion}
              onChange={(e) => setForm((f) => ({ ...f, targetRegion: e.target.value }))}
              required
              disabled={isGenerating}
            />
          </div>
          <div className={styles.field}>
            <label htmlFor="ta">Target audience</label>
            <input
              id="ta"
              value={form.targetAudience}
              onChange={(e) => setForm((f) => ({ ...f, targetAudience: e.target.value }))}
              required
              disabled={isGenerating}
            />
          </div>
        </div>
        <div className={styles.field}>
          <label htmlFor="msg">Campaign message (on-image text)</label>
          <textarea
            id="msg"
            value={form.campaignMessage}
            onChange={(e) => setForm((f) => ({ ...f, campaignMessage: e.target.value }))}
            required
            rows={2}
            disabled={isGenerating}
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="ol">On-image language (optional)</label>
          <select
            id="ol"
            value={form.overlayLocale}
            onChange={(e) => setForm((f) => ({ ...f, overlayLocale: e.target.value }))}
            disabled={isGenerating}
          >
            <option value="">English (source message)</option>
            <option value="es">Spanish (translate for overlay)</option>
          </select>
        </div>
        <div className={styles.actions}>
          {isGenerating ? (
            <button type="button" onClick={handleCancel} className={styles.cancelBtn}>
              Cancel
            </button>
          ) : (
            <button type="submit" className={styles.submitBtn}>
              Generate campaign
            </button>
          )}
        </div>
        {errorMsg && <div className={styles.error}>{errorMsg}</div>}
      </form>

      {(isGenerating || (status === 'done' && totalExpected > 0)) && (
        <div className={styles.progressWrap}>
          <span className={styles.progressLabel}>
            {overviewMsg ?? 'Starting…'}
            {totalExpected > 0 && ` — ${creatives.length} / ${totalExpected}`}
          </span>
          <div className={styles.progressTrack}>
            <div
              className={styles.progressFill}
              style={totalExpected > 0 ? { width: `${progress}%` } : { width: '8%' }}
            />
          </div>
          {isGenerating && totalExpected > 0 && creatives.length === 0 && (
            <p className={styles.phaseHint}>
              <strong>0 / {totalExpected} is normal right now</strong> — the bar only moves when
              finished creatives stream in. The API is still resolving hero images (local file or
              GenAI). GenAI can take 1–2+ minutes per product; wait or add{' '}
              <code>input_assets/&lt;id&gt;/hero.png</code> to skip.
            </p>
          )}
          {heroSteps.length > 0 && (isGenerating || status === 'done') && (
            <ul className={styles.heroSteps} aria-label="Hero resolution steps">
              {heroSteps.map((line, i) => (
                <li key={i}>{line}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {legalStatus && (isGenerating || status === 'done') && (
        <div className={styles.compliance} role="status">
          <strong>Legal (prohibited terms):</strong>{' '}
          {legalStatus.ok
            ? 'No flagged terms in overlay copy'
            : `Flagged: ${legalStatus.terms.join(', ')}`}
        </div>
      )}

      {checkRows.length > 0 && status === 'done' && (
        <div className={styles.checkTable} role="region" aria-label="Per-creative brand checks">
          <h3 className={styles.checkTableTitle}>Brand checks (per file)</h3>
          <ul>
            {checkRows.map((r) => (
              <li key={r.key}>
                {r.productId} / {r.ratio}: brand {r.brandOk ? 'OK' : 'issues'}{' '}
                {!r.brandOk && r.brandIssues.length > 0 && (
                  <span className={styles.muted}>({r.brandIssues.join('; ')})</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {complete && status === 'done' && (
        <div className={styles.summary}>
          <h3>Run complete</h3>
          <p>Elapsed: {complete.elapsed_ms} ms</p>
          <p>GenAI hero generations: {complete.genai_calls}</p>
          <p>Cache hits: {complete.cache_hits}</p>
          {typeof complete.localization_applied === 'boolean' && (
            <p>Localization: {complete.localization_applied ? 'Yes (overlay)' : 'No'}</p>
          )}
          {typeof complete.legal_ok === 'boolean' && <p>Legal copy OK: {String(complete.legal_ok)}</p>}
          {typeof complete.all_checks_pass === 'boolean' && (
            <p>All checks pass: {String(complete.all_checks_pass)}</p>
          )}
          {complete.report_path && <p>Report: {complete.report_path}</p>}
        </div>
      )}

      {creatives.length > 0 && (
        <section className={styles.results}>
          {[...new Set(creatives.map((c) => c.productId))].map((pid) => (
            <div key={pid} className={styles.productSection}>
              <div className={styles.productLabel}>{pid}</div>
              <div className={styles.ratioRow}>
                {creatives.filter((c) => c.productId === pid).map((c) => (
                  <article key={c.key} className={styles.card}>
                    <img
                      className={`${styles.thumb} ${styles[`ratio${c.ratio}` as keyof typeof styles]}`}
                      src={c.imageUrl}
                      alt={c.ratio}
                    />
                    <div className={styles.caption}>{c.ratio}</div>
                  </article>
                ))}
              </div>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
