export type Attachment = {
  product_id: string;
  product_slug?: string | null;
  name: string;
  price: string | number;
  currency: string;
  image_url: string;
  image_alt_text?: string | null;
  brand?: string | null;
  category?: string | null;
};

export type MissionData = {
  goal?: string | null;
  mission_type?: string | null;
  budget?: number | null;
  preferences?: string[];
  key_requirements?: string[];
  owned_items?: string[];
  priorities?: string[];
};

export type MissionHistoryItem = { id: string; label: string; total: number; at: string };

export type BundleWorkspace = {
  bundle?: { rationale?: string[]; trade_offs?: string[]; budget_remaining?: string | number | null } | null;
  compatibility?: Array<{ status?: string; reason?: string; message?: string }>;
  product_rankings?: Array<{ product_id?: string; reasons?: string[] }>;
  audit?: { status?: string };
};
