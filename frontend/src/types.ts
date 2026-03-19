export interface MenuItem {
  name: string;
  description: string;
  price: string;
}

export interface Restaurant {
  name: string;
  category: string;
  price_range: string;
  score: number;
  ratings: string;
  address: string;
  similarity: number;
  matched_items: MenuItem[];
}
