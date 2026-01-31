import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { supabase } from '../lib/supabase';
import { Sale, SaleItem, CartItem, SaleWithItems } from '../types/database';
import { useAuthStore } from '../store/authStore';

export function useSales() {
  const { user } = useAuthStore();
  const queryClient = useQueryClient();

  const salesQuery = useQuery({
    queryKey: ['sales', user?.id],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('sales')
        .select(`
          *,
          sale_items(
            *,
            product:products(*)
          )
        `)
        .order('created_at', { ascending: false });

      if (error) throw error;
      return data as SaleWithItems[];
    },
    enabled: !!user,
  });

  const createSale = useMutation({
    mutationFn: async ({
      items,
      paymentMethod,
      notes,
    }: {
      items: CartItem[];
      paymentMethod: string;
      notes?: string;
    }) => {
      const total = items.reduce(
        (sum, item) => sum + item.product.price * item.quantity,
        0
      );

      // Create sale
      const { data: sale, error: saleError } = await supabase
        .from('sales')
        .insert({
          total,
          payment_method: paymentMethod,
          notes,
          user_id: user!.id,
        })
        .select()
        .single();

      if (saleError) throw saleError;

      // Create sale items
      const saleItems: Omit<SaleItem, 'id' | 'created_at'>[] = items.map((item) => ({
        sale_id: sale.id,
        product_id: item.product.id,
        quantity: item.quantity,
        price: item.product.price,
        subtotal: item.product.price * item.quantity,
      }));

      const { error: itemsError } = await supabase
        .from('sale_items')
        .insert(saleItems);

      if (itemsError) throw itemsError;

      return sale;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sales'] });
      queryClient.invalidateQueries({ queryKey: ['products'] });
    },
  });

  const getTodaySales = () => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return (salesQuery.data ?? []).filter(
      (sale) => new Date(sale.created_at) >= today
    );
  };

  const getTodayTotal = () => {
    return getTodaySales().reduce((sum, sale) => sum + Number(sale.total), 0);
  };

  return {
    sales: salesQuery.data ?? [],
    isLoading: salesQuery.isLoading,
    error: salesQuery.error,
    createSale,
    getTodaySales,
    getTodayTotal,
  };
}
