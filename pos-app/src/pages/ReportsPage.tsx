import { useState, useMemo } from 'react';
import {
  BarChart3,
  TrendingUp,
  DollarSign,
  ShoppingBag,
  Calendar,
  Package,
} from 'lucide-react';
import { useSales } from '../hooks/useSales';
import { useProducts } from '../hooks/useProducts';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';

type DateRange = 'today' | 'week' | 'month' | 'year';

export function ReportsPage() {
  const [dateRange, setDateRange] = useState<DateRange>('today');

  const { sales, isLoading: salesLoading } = useSales();
  const { products, isLoading: productsLoading } = useProducts();

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      minimumFractionDigits: 0,
    }).format(price);
  };

  const getDateRangeStart = (range: DateRange) => {
    const now = new Date();
    switch (range) {
      case 'today':
        now.setHours(0, 0, 0, 0);
        return now;
      case 'week':
        now.setDate(now.getDate() - 7);
        return now;
      case 'month':
        now.setMonth(now.getMonth() - 1);
        return now;
      case 'year':
        now.setFullYear(now.getFullYear() - 1);
        return now;
    }
  };

  const filteredSales = useMemo(() => {
    const rangeStart = getDateRangeStart(dateRange);
    return sales.filter((sale) => new Date(sale.created_at) >= rangeStart);
  }, [sales, dateRange]);

  const stats = useMemo(() => {
    const totalRevenue = filteredSales.reduce(
      (sum, sale) => sum + Number(sale.total),
      0
    );
    const totalTransactions = filteredSales.length;
    const averageTransaction = totalTransactions > 0 ? totalRevenue / totalTransactions : 0;

    const itemsSold = filteredSales.reduce((sum, sale) => {
      return sum + sale.sale_items.reduce((itemSum, item) => itemSum + item.quantity, 0);
    }, 0);

    const paymentMethods = filteredSales.reduce(
      (acc, sale) => {
        acc[sale.payment_method] = (acc[sale.payment_method] || 0) + Number(sale.total);
        return acc;
      },
      {} as Record<string, number>
    );

    const topProducts = filteredSales
      .flatMap((sale) => sale.sale_items)
      .reduce(
        (acc, item) => {
          const key = item.product_id;
          if (!acc[key]) {
            acc[key] = {
              name: item.product?.name || 'Unknown',
              quantity: 0,
              revenue: 0,
            };
          }
          acc[key].quantity += item.quantity;
          acc[key].revenue += Number(item.subtotal);
          return acc;
        },
        {} as Record<string, { name: string; quantity: number; revenue: number }>
      );

    const topProductsList = Object.values(topProducts)
      .sort((a, b) => b.revenue - a.revenue)
      .slice(0, 5);

    return {
      totalRevenue,
      totalTransactions,
      averageTransaction,
      itemsSold,
      paymentMethods,
      topProducts: topProductsList,
    };
  }, [filteredSales]);

  const lowStockProducts = useMemo(() => {
    return products.filter((p) => p.stock <= 5).sort((a, b) => a.stock - b.stock);
  }, [products]);

  if (salesLoading || productsLoading) {
    return <LoadingSpinner text="Loading reports..." />;
  }

  return (
    <div className="page reports-page">
      <div className="page-header">
        <div className="page-title">
          <BarChart3 size={28} />
          <h1>Reports</h1>
        </div>
        <div className="date-range-selector">
          {(['today', 'week', 'month', 'year'] as DateRange[]).map((range) => (
            <button
              key={range}
              className={`range-btn ${dateRange === range ? 'active' : ''}`}
              onClick={() => setDateRange(range)}
            >
              {range.charAt(0).toUpperCase() + range.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div className="stats-grid">
        <div className="stat-card large">
          <div className="stat-icon revenue">
            <DollarSign size={24} />
          </div>
          <div className="stat-content">
            <span className="stat-label">Total Revenue</span>
            <span className="stat-value">{formatPrice(stats.totalRevenue)}</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon transactions">
            <ShoppingBag size={24} />
          </div>
          <div className="stat-content">
            <span className="stat-label">Transactions</span>
            <span className="stat-value">{stats.totalTransactions}</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon average">
            <TrendingUp size={24} />
          </div>
          <div className="stat-content">
            <span className="stat-label">Average Order</span>
            <span className="stat-value">{formatPrice(stats.averageTransaction)}</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon items">
            <Package size={24} />
          </div>
          <div className="stat-content">
            <span className="stat-label">Items Sold</span>
            <span className="stat-value">{stats.itemsSold}</span>
          </div>
        </div>
      </div>

      <div className="reports-grid">
        <div className="report-card">
          <h3>Payment Methods</h3>
          <div className="payment-breakdown">
            {Object.entries(stats.paymentMethods).length === 0 ? (
              <p className="no-data">No data available</p>
            ) : (
              Object.entries(stats.paymentMethods).map(([method, amount]) => (
                <div key={method} className="payment-row">
                  <span className="payment-method">{method}</span>
                  <span className="payment-amount">{formatPrice(amount)}</span>
                  <div
                    className="payment-bar"
                    style={{
                      width: `${(amount / stats.totalRevenue) * 100}%`,
                    }}
                  />
                </div>
              ))
            )}
          </div>
        </div>

        <div className="report-card">
          <h3>Top Products</h3>
          <div className="top-products">
            {stats.topProducts.length === 0 ? (
              <p className="no-data">No data available</p>
            ) : (
              stats.topProducts.map((product, index) => (
                <div key={index} className="product-row">
                  <span className="product-rank">{index + 1}</span>
                  <div className="product-info">
                    <span className="product-name">{product.name}</span>
                    <span className="product-qty">{product.quantity} sold</span>
                  </div>
                  <span className="product-revenue">{formatPrice(product.revenue)}</span>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="report-card">
          <h3>Low Stock Alert</h3>
          <div className="low-stock-list">
            {lowStockProducts.length === 0 ? (
              <p className="no-data">All products are well stocked</p>
            ) : (
              lowStockProducts.map((product) => (
                <div key={product.id} className="low-stock-item">
                  <span className="product-name">{product.name}</span>
                  <span className={`stock-count ${product.stock === 0 ? 'out' : 'low'}`}>
                    {product.stock} left
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
