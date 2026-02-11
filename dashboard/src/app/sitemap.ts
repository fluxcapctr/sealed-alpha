import { MetadataRoute } from "next";
import { createClient } from "@supabase/supabase-js";
import type { Database } from "@/types/database";

const BASE_URL = "https://sealedalpha.com";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const staticPages: MetadataRoute.Sitemap = [
    {
      url: BASE_URL,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 1,
    },
    {
      url: `${BASE_URL}/signup`,
      lastModified: new Date(),
      changeFrequency: "monthly",
      priority: 0.8,
    },
    {
      url: `${BASE_URL}/privacy`,
      lastModified: new Date(),
      changeFrequency: "yearly",
      priority: 0.3,
    },
    {
      url: `${BASE_URL}/terms`,
      lastModified: new Date(),
      changeFrequency: "yearly",
      priority: 0.3,
    },
  ];

  // Fetch all EN sets for dynamic pages
  let setPages: MetadataRoute.Sitemap = [];

  try {
    const supabase = createClient<Database>(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
    );

    const { data: sets } = await supabase
      .from("sets")
      .select("id, updated_at")
      .eq("language", "en")
      .order("release_date", { ascending: false });

    if (sets) {
      setPages = sets.map((set) => ({
        url: `${BASE_URL}/sets/${set.id}`,
        lastModified: new Date(set.updated_at),
        changeFrequency: "daily" as const,
        priority: 0.7,
      }));
    }
  } catch (e) {
    console.error("[Sitemap] Failed to fetch sets:", e);
  }

  return [...staticPages, ...setPages];
}
