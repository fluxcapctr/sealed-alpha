export type Database = {
  public: {
    Tables: {
      sets: {
        Row: {
          id: string;
          name: string;
          code: string | null;
          series: string | null;
          release_date: string | null;
          tcgplayer_group_id: number | null;
          set_url: string | null;
          image_url: string | null;
          is_in_print: boolean;
          is_in_rotation: boolean;
          total_products: number;
          total_set_value: number | null;
          total_cards: number | null;
          set_value_updated_at: string | null;
          top_card_image_url: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          name: string;
          code?: string | null;
          series?: string | null;
          release_date?: string | null;
          tcgplayer_group_id?: number | null;
          set_url?: string | null;
          image_url?: string | null;
          is_in_print?: boolean;
          is_in_rotation?: boolean;
          total_products?: number;
          total_set_value?: number | null;
          total_cards?: number | null;
          top_card_image_url?: string | null;
        };
        Update: {
          id?: string;
          name?: string;
          code?: string | null;
          series?: string | null;
          release_date?: string | null;
          tcgplayer_group_id?: number | null;
          set_url?: string | null;
          image_url?: string | null;
          is_in_print?: boolean;
          is_in_rotation?: boolean;
          total_products?: number;
          total_set_value?: number | null;
          total_cards?: number | null;
          top_card_image_url?: string | null;
        };
        Relationships: [
          {
            foreignKeyName: "products_set_id_fkey";
            columns: ["id"];
            isOneToOne: false;
            referencedRelation: "products";
            referencedColumns: ["set_id"];
          },
        ];
      };
      products: {
        Row: {
          id: string;
          set_id: string | null;
          name: string;
          product_type: string;
          tcgplayer_product_id: number | null;
          tcgplayer_url: string | null;
          image_url: string | null;
          release_date: string | null;
          msrp: number | null;
          is_active: boolean;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          set_id?: string | null;
          name: string;
          product_type: string;
          tcgplayer_product_id?: number | null;
          tcgplayer_url?: string | null;
          image_url?: string | null;
          release_date?: string | null;
          msrp?: number | null;
          is_active?: boolean;
        };
        Update: {
          id?: string;
          set_id?: string | null;
          name?: string;
          product_type?: string;
          tcgplayer_product_id?: number | null;
          tcgplayer_url?: string | null;
          image_url?: string | null;
          release_date?: string | null;
          msrp?: number | null;
          is_active?: boolean;
        };
        Relationships: [
          {
            foreignKeyName: "products_set_id_fkey";
            columns: ["set_id"];
            isOneToOne: false;
            referencedRelation: "sets";
            referencedColumns: ["id"];
          },
        ];
      };
      price_snapshots: {
        Row: {
          id: string;
          product_id: string;
          snapshot_date: string;
          market_price: number | null;
          low_price: number | null;
          mid_price: number | null;
          high_price: number | null;
          listed_median_price: number | null;
          direct_low_price: number | null;
          total_listings: number | null;
          available_quantity: number | null;
          foil_price: number | null;
          created_at: string;
        };
        Insert: {
          id?: string;
          product_id: string;
          snapshot_date?: string;
          market_price?: number | null;
          low_price?: number | null;
          mid_price?: number | null;
          high_price?: number | null;
          listed_median_price?: number | null;
          direct_low_price?: number | null;
          total_listings?: number | null;
          available_quantity?: number | null;
          foil_price?: number | null;
        };
        Update: {
          id?: string;
          product_id?: string;
          snapshot_date?: string;
          market_price?: number | null;
          low_price?: number | null;
          mid_price?: number | null;
          high_price?: number | null;
          listed_median_price?: number | null;
          direct_low_price?: number | null;
          total_listings?: number | null;
          available_quantity?: number | null;
          foil_price?: number | null;
        };
        Relationships: [
          {
            foreignKeyName: "price_snapshots_product_id_fkey";
            columns: ["product_id"];
            isOneToOne: false;
            referencedRelation: "products";
            referencedColumns: ["id"];
          },
        ];
      };
      sales_snapshots: {
        Row: {
          id: string;
          product_id: string;
          snapshot_date: string;
          total_sales: number | null;
          avg_sale_price: number | null;
          min_sale_price: number | null;
          max_sale_price: number | null;
          sale_count_24h: number | null;
          created_at: string;
        };
        Insert: {
          id?: string;
          product_id: string;
          snapshot_date?: string;
          total_sales?: number | null;
          avg_sale_price?: number | null;
          min_sale_price?: number | null;
          max_sale_price?: number | null;
          sale_count_24h?: number | null;
        };
        Update: {
          id?: string;
          product_id?: string;
          snapshot_date?: string;
          total_sales?: number | null;
          avg_sale_price?: number | null;
          min_sale_price?: number | null;
          max_sale_price?: number | null;
          sale_count_24h?: number | null;
        };
        Relationships: [
          {
            foreignKeyName: "sales_snapshots_product_id_fkey";
            columns: ["product_id"];
            isOneToOne: false;
            referencedRelation: "products";
            referencedColumns: ["id"];
          },
        ];
      };
      signals: {
        Row: {
          id: string;
          product_id: string;
          signal_date: string;
          composite_score: number | null;
          price_vs_ma_score: number | null;
          momentum_score: number | null;
          volatility_score: number | null;
          listings_score: number | null;
          sales_velocity_score: number | null;
          lifecycle_score: number | null;
          recommendation: string | null;
          created_at: string;
        };
        Insert: {
          id?: string;
          product_id: string;
          signal_date?: string;
          composite_score?: number | null;
          price_vs_ma_score?: number | null;
          momentum_score?: number | null;
          volatility_score?: number | null;
          listings_score?: number | null;
          sales_velocity_score?: number | null;
          lifecycle_score?: number | null;
          recommendation?: string | null;
        };
        Update: {
          id?: string;
          product_id?: string;
          signal_date?: string;
          composite_score?: number | null;
          price_vs_ma_score?: number | null;
          momentum_score?: number | null;
          volatility_score?: number | null;
          listings_score?: number | null;
          sales_velocity_score?: number | null;
          lifecycle_score?: number | null;
          recommendation?: string | null;
        };
        Relationships: [
          {
            foreignKeyName: "signals_product_id_fkey";
            columns: ["product_id"];
            isOneToOne: false;
            referencedRelation: "products";
            referencedColumns: ["id"];
          },
        ];
      };
      alerts: {
        Row: {
          id: string;
          product_id: string | null;
          alert_type: string;
          message: string | null;
          signal_score: number | null;
          is_sent: boolean;
          sent_at: string | null;
          created_at: string;
        };
        Insert: {
          id?: string;
          product_id?: string | null;
          alert_type: string;
          message?: string | null;
          signal_score?: number | null;
          is_sent?: boolean;
          sent_at?: string | null;
        };
        Update: {
          id?: string;
          product_id?: string | null;
          alert_type?: string;
          message?: string | null;
          signal_score?: number | null;
          is_sent?: boolean;
          sent_at?: string | null;
        };
        Relationships: [
          {
            foreignKeyName: "alerts_product_id_fkey";
            columns: ["product_id"];
            isOneToOne: false;
            referencedRelation: "products";
            referencedColumns: ["id"];
          },
        ];
      };
      pull_rates: {
        Row: {
          id: string;
          set_id: string;
          rarity: string;
          packs_per_hit: number;
          cards_in_set: number | null;
          source: string;
          created_at: string;
        };
        Insert: {
          id?: string;
          set_id: string;
          rarity: string;
          packs_per_hit: number;
          cards_in_set?: number | null;
          source?: string;
        };
        Update: {
          id?: string;
          set_id?: string;
          rarity?: string;
          packs_per_hit?: number;
          cards_in_set?: number | null;
          source?: string;
        };
        Relationships: [
          {
            foreignKeyName: "pull_rates_set_id_fkey";
            columns: ["set_id"];
            isOneToOne: false;
            referencedRelation: "sets";
            referencedColumns: ["id"];
          },
        ];
      };
      set_rarity_values: {
        Row: {
          id: string;
          set_id: string;
          rarity: string;
          total_value: number;
          card_count: number;
          updated_at: string;
        };
        Insert: {
          id?: string;
          set_id: string;
          rarity: string;
          total_value: number;
          card_count: number;
        };
        Update: {
          id?: string;
          set_id?: string;
          rarity?: string;
          total_value?: number;
          card_count?: number;
        };
        Relationships: [
          {
            foreignKeyName: "set_rarity_values_set_id_fkey";
            columns: ["set_id"];
            isOneToOne: false;
            referencedRelation: "sets";
            referencedColumns: ["id"];
          },
        ];
      };
      user_settings: {
        Row: {
          id: string;
          email: string | null;
          alert_threshold: number;
          alert_frequency: string;
          watched_product_ids: string[];
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          email?: string | null;
          alert_threshold?: number;
          alert_frequency?: string;
          watched_product_ids?: string[];
        };
        Update: {
          id?: string;
          email?: string | null;
          alert_threshold?: number;
          alert_frequency?: string;
          watched_product_ids?: string[];
        };
        Relationships: [];
      };
    };
    Views: {
      product_analytics: {
        Row: {
          product_id: string;
          product_name: string;
          product_type: string;
          tcgplayer_product_id: number | null;
          tcgplayer_url: string | null;
          product_image: string | null;
          msrp: number | null;
          set_id: string;
          set_name: string;
          set_code: string | null;
          series: string | null;
          release_date: string | null;
          is_in_print: boolean;
          is_in_rotation: boolean;
          days_since_release: number | null;
          current_price: number | null;
          current_low: number | null;
          current_mid: number | null;
          current_high: number | null;
          current_listings: number | null;
          current_quantity: number | null;
          last_price_date: string | null;
          ma_7d: number | null;
          ma_30d: number | null;
          ma_90d: number | null;
          price_7d_ago: number | null;
          price_30d_ago: number | null;
          price_90d_ago: number | null;
          price_change_7d_pct: number | null;
          price_change_30d_pct: number | null;
          volatility_30d: number | null;
          all_time_low: number | null;
          all_time_high: number | null;
          listings_7d_ago: number | null;
          quantity_7d_ago: number | null;
          quantity_30d_ago: number | null;
          quantity_90d_ago: number | null;
          quantity_change_90d_pct: number | null;
          avg_daily_sales_7d: number | null;
          avg_daily_sales_30d: number | null;
          total_sold_90d: number | null;
          avg_daily_sold: number | null;
          total_price_points: number | null;
          first_tracked: string | null;
          last_tracked: string | null;
          signal_score: number | null;
          signal_recommendation: string | null;
        };
        Relationships: [];
      };
    };
    Functions: {
      refresh_product_analytics: {
        Args: Record<string, never>;
        Returns: void;
      };
    };
    Enums: Record<string, never>;
    CompositeTypes: Record<string, never>;
  };
};

// Convenience type aliases
export type Set = Database["public"]["Tables"]["sets"]["Row"];
export type Product = Database["public"]["Tables"]["products"]["Row"];
export type PriceSnapshot =
  Database["public"]["Tables"]["price_snapshots"]["Row"];
export type SalesSnapshot =
  Database["public"]["Tables"]["sales_snapshots"]["Row"];
export type Signal = Database["public"]["Tables"]["signals"]["Row"];
export type Alert = Database["public"]["Tables"]["alerts"]["Row"];
export type PullRate = Database["public"]["Tables"]["pull_rates"]["Row"];
export type SetRarityValue =
  Database["public"]["Tables"]["set_rarity_values"]["Row"];
export type ProductAnalytics =
  Database["public"]["Views"]["product_analytics"]["Row"];
