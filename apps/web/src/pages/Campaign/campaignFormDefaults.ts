import type { ProductField } from './types';

export const CAMPAIGN_FORM_DEFAULTS = {
  campaignName: 'PNW Trail Season 2026',
  targetRegion: 'US — Pacific Northwest',
  targetAudience: 'Weekend hikers and backcountry day-trippers',
  campaignMessage: 'Drink clean. Pack smart. Go farther.',
  /** empty = English; `es` = Spanish on-image (requires ANTHROPIC key) */
  overlayLocale: '',
  products: [
    { id: 'insulated-trail-bottle', name: 'Insulated trail bottle (navy)' },
    { id: 'technical-hiking-pack', name: 'Technical hiking pack (olive)' },
  ] satisfies ProductField[],
};
