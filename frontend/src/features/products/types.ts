export type Product = {
  id: string;
  slug: string;
  name: string;
  brand: string;
  category: string;
  desc: string;
  price: number;
  rating: number;
  reviews: number;
  emoji: string;
  image?: string;
  stock: boolean;
  badge?: "new" | "hot" | "sale";
  specs: Array<{ label: string; value: string }>;
};

export type ApiProduct = {
  id: string;
  slug: string;
  name: string;
  brand: string;
  description: string;
  price: string | number;
  badge: Product["badge"] | null;
  emoji: string | null;
  specs: Product["specs"];
  rating_average: string | number;
  review_count: number;
  inventory_quantity: number;
  category: { name: string; slug: string };
  images: Array<{ url: string; alt_text: string | null }>;
};

export function toProduct(product: ApiProduct): Product {
  return {
    id: product.id,
    slug: product.slug,
    name: product.name,
    brand: product.brand,
    category: product.category.name,
    desc: product.description,
    price: Number(product.price),
    rating: Number(product.rating_average),
    reviews: product.review_count,
    emoji: product.emoji || "🛍️",
    image: product.images[0]?.url,
    stock: product.inventory_quantity > 0,
    badge: product.badge ?? undefined,
    specs: product.specs,
  };
}
