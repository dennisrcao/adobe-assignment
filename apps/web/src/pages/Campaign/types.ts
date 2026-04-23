export type ProductField = { id: string; name: string };

export type CampaignStatus = 'idle' | 'generating' | 'done' | 'error';

export type Creative = {
  key: string;
  productId: string;
  ratio: string;
  imageUrl: string;
};

export type CompletePayload = {
  elapsed_ms: number;
  genai_calls: number;
  cache_hits: number;
  report_path?: string;
  report_md_path?: string;
};
