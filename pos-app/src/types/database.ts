export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[];

export interface Database {
  public: {
    Tables: {
      categories: {
        Row: {
          id: string;
          name: string;
          description: string | null;
          created_at: string;
          updated_at: string;
          user_id: string;
        };
        Insert: {
          id?: string;
          name: string;
          description?: string | null;
          created_at?: string;
          updated_at?: string;
          user_id: string;
        };
        Update: {
          id?: string;
          name?: string;
          description?: string | null;
          created_at?: string;
          updated_at?: string;
          user_id?: string;
        };
      };
      products: {
        Row: {
          id: string;
          name: string;
          description: string | null;
          price: number;
          stock: number;
          category_id: string | null;
          image_url: string | null;
          sku: string | null;
          created_at: string;
          updated_at: string;
          user_id: string;
        };
        Insert: {
          id?: string;
          name: string;
          description?: string | null;
          price: number;
          stock?: number;
          category_id?: string | null;
          image_url?: string | null;
          sku?: string | null;
          created_at?: string;
          updated_at?: string;
          user_id: string;
        };
        Update: {
          id?: string;
          name?: string;
          description?: string | null;
          price?: number;
          stock?: number;
          category_id?: string | null;
          image_url?: string | null;
          sku?: string | null;
          created_at?: string;
          updated_at?: string;
          user_id?: string;
        };
      };
      sales: {
        Row: {
          id: string;
          total: number;
          payment_method: string;
          status: string;
          notes: string | null;
          created_at: string;
          user_id: string;
        };
        Insert: {
          id?: string;
          total: number;
          payment_method: string;
          status?: string;
          notes?: string | null;
          created_at?: string;
          user_id: string;
        };
        Update: {
          id?: string;
          total?: number;
          payment_method?: string;
          status?: string;
          notes?: string | null;
          created_at?: string;
          user_id?: string;
        };
      };
      sale_items: {
        Row: {
          id: string;
          sale_id: string;
          product_id: string;
          quantity: number;
          price: number;
          subtotal: number;
          created_at: string;
        };
        Insert: {
          id?: string;
          sale_id: string;
          product_id: string;
          quantity: number;
          price: number;
          subtotal: number;
          created_at?: string;
        };
        Update: {
          id?: string;
          sale_id?: string;
          product_id?: string;
          quantity?: number;
          price?: number;
          subtotal?: number;
          created_at?: string;
        };
      };
    };
  };
}

export type Category = Database['public']['Tables']['categories']['Row'];
export type Product = Database['public']['Tables']['products']['Row'];
export type Sale = Database['public']['Tables']['sales']['Row'];
export type SaleItem = Database['public']['Tables']['sale_items']['Row'];

export interface CartItem {
  product: Product;
  quantity: number;
}

export interface SaleWithItems extends Sale {
  sale_items: (SaleItem & { product: Product })[];
}
