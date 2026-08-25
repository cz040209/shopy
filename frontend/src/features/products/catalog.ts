import { type ApiProduct, toProduct, type Product } from "./types";

const backendOrigin = process.env.BACKEND_ORIGIN ?? "http://localhost:8002";

export async function getProducts(query?: string): Promise<Product[]> {
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  const response = await fetch(`${backendOrigin}/api/v1/products?${params}`, { cache: "no-store" });
  if (!response.ok) throw new Error("The catalog is currently unavailable.");
  const data: { items: ApiProduct[] } = await response.json();
  return data.items.map(toProduct);
}

export async function getProduct(id: string): Promise<Product | null> {
  const response = await fetch(`${backendOrigin}/api/v1/products/${id}`, { cache: "no-store" });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error("The product is currently unavailable.");
  return toProduct((await response.json()) as ApiProduct);
}
