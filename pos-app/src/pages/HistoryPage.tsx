import { useState } from 'react';
import { History, Search, Calendar, Eye, ChevronDown, ChevronUp } from 'lucide-react';
import { useSales } from '../hooks/useSales';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { SaleWithItems } from '../types/database';

export function HistoryPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [dateFilter, setDateFilter] = useState('');
  const [expandedSale, setExpandedSale] = useState<string | null>(null);

  const { sales, isLoading } = useSales();

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      minimumFractionDigits: 0,
    }).format(price);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('id-ID', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const filteredSales = sales.filter((sale) => {
    const matchesSearch =
      sale.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      sale.payment_method.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesDate = !dateFilter || sale.created_at.startsWith(dateFilter);
    return matchesSearch && matchesDate;
  });

  const getPaymentMethodBadge = (method: string) => {
    const badges: Record<string, string> = {
      cash: 'badge-success',
      card: 'badge-info',
      transfer: 'badge-warning',
    };
    return badges[method] || 'badge-default';
  };

  const toggleExpand = (saleId: string) => {
    setExpandedSale(expandedSale === saleId ? null : saleId);
  };

  if (isLoading) {
    return <LoadingSpinner text="Loading transaction history..." />;
  }

  return (
    <div className="page history-page">
      <div className="page-header">
        <div className="page-title">
          <History size={28} />
          <h1>Transaction History</h1>
          <span className="badge">{sales.length}</span>
        </div>
      </div>

      <div className="filters">
        <div className="search-box">
          <Search size={20} className="search-icon" />
          <input
            type="text"
            placeholder="Search transactions..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="date-filter">
          <Calendar size={20} className="filter-icon" />
          <input
            type="date"
            value={dateFilter}
            onChange={(e) => setDateFilter(e.target.value)}
          />
        </div>
      </div>

      {filteredSales.length === 0 ? (
        <div className="empty-state">
          <History size={64} />
          <h2>No transactions found</h2>
          <p>
            {searchTerm || dateFilter
              ? 'Try adjusting your filters'
              : 'Complete your first sale to see it here'}
          </p>
        </div>
      ) : (
        <div className="transactions-list">
          {filteredSales.map((sale) => (
            <div key={sale.id} className="transaction-card">
              <div
                className="transaction-header"
                onClick={() => toggleExpand(sale.id)}
              >
                <div className="transaction-info">
                  <span className="transaction-id">#{sale.id.slice(0, 8)}</span>
                  <span className="transaction-date">{formatDate(sale.created_at)}</span>
                </div>
                <div className="transaction-meta">
                  <span className={`badge ${getPaymentMethodBadge(sale.payment_method)}`}>
                    {sale.payment_method}
                  </span>
                  <span className="transaction-total">{formatPrice(Number(sale.total))}</span>
                  {expandedSale === sale.id ? (
                    <ChevronUp size={20} />
                  ) : (
                    <ChevronDown size={20} />
                  )}
                </div>
              </div>

              {expandedSale === sale.id && (
                <div className="transaction-details">
                  <h4>Items</h4>
                  <div className="transaction-items">
                    {sale.sale_items.map((item) => (
                      <div key={item.id} className="transaction-item">
                        <span className="item-name">
                          {item.product?.name || 'Unknown Product'}
                        </span>
                        <span className="item-qty">x{item.quantity}</span>
                        <span className="item-price">{formatPrice(Number(item.subtotal))}</span>
                      </div>
                    ))}
                  </div>
                  {sale.notes && (
                    <div className="transaction-notes">
                      <h4>Notes</h4>
                      <p>{sale.notes}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
