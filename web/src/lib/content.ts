export interface ArticleSummary {
  slug: string;
  title: string;
  excerpt: string;
  category: string;
  tags: string[];
  author: string;
  published_at: string | null;
  updated_at: string;
  meta_title: string;
  meta_description: string;
  canonical_url: string;
  ai_assisted: boolean;
  medical: boolean;
}
export interface ArticleDetail extends ArticleSummary {
  body: string;
  references: string[];
  related: ArticleSummary[];
}
