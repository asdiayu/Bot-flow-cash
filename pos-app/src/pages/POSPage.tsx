import { useState } from 'react';
import { Search, ShoppingCart, Trash2 } from 'lucide-react';
import { useProducts } from '../hooks/useProducts';
import { useCategories } from '../hooks/useCategories';
import { useSales } from '../hooks/useSales';
import { useCartStore } from '../store/cartStore';
import { ProductGrid } from '../components/pos/ProductGrid';
import { Cart } from '../components/pos/Cart';
import { CheckoutModal } from '../components/pos/CheckoutModal';
import { Modal } from '../components/ui/Modal';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { Product } from '../types/database';

export function POSPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false);

  const { products, isLoading } = useProducts();
  const { categories } = useCategories();
  const { createSale, getTodayTotal } = useSales();
  const { items, addItem, updateQuantity, removeItem, clearCart, getTotal } = useCartStore();

  const filteredProducts = products.filter((product) => {
    const matchesSearch = product.name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = !selectedCategory || product.category_id === selectedCategory;
    return matchesSearch && matchesCategory && product.stock > 0;
  });

  const handleAddToCart = (product: Product) => {
    const existingItem = items.find((item) => item.product.id === product.id);
    if (existingItem && existingItem.quantity >= product.stock) {
      return;
    }
    addItem(product);
  };

  const handleCheckout = async (paymentMethod: string, notes?: string) => {
    await createSale.mutateAsync({
      items,
      paymentMethod,
      notes,
    });
    clearCart();
  };

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      minimumFractionDigits: 0,
    }).format(price);
  };

  if (isLoading) {
    return <LoadingSpinner text="Loading POS..." />;
  }

  return (
    <div className="pos-page">
      <div className="pos-main">
        <div className="pos-header">
          <div className="pos-stats">
            <div className="stat-card">
              <span className="stat-label">Today's Sales</span>
              <span className="stat-value">{formatPrice(getTodayTotal())}</span>
            </div>
          </div>
          <div className="pos-search">
            <Search size={20} className="search-icon" />
            <input
              type="text"
              placeholder="Search products..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </div>

        <div className="pos-categories">
          <button
            className={`category-btn ${!selectedCategory ? 'active' : ''}`}
            onClick={() => setSelectedCategory('')}
          >
            All
          </button>
          {categories.map((cat) => (
            <button
              key={cat.id}
              className={`category-btn ${selectedCategory === cat.id ? 'active' : ''}`}
              onClick={() => setSelectedCategory(cat.id)}
            >
              {cat.name}
            </button>
          ))}
        </div>

        <ProductGrid products={filteredProducts} onAddToCart={handleAddToCart} />
      </div>

      <div className="pos-sidebar">
        <div className="pos-sidebar-header">
          <ShoppingCart size={24} />
          <h2>Current Order</h2>
          {items.length > 0 && (
            <button className="btn btn-icon btn-danger" onClick={clearCart} title="Clear cart">
              <Trash2 size={18} />
            </button>
          )}
        </div>

        <Cart
          items={items}
          onUpdateQuantity={updateQuantity}
          onRemoveItem={removeItem}
          total={getTotal()}
        />

        {items.length > 0 && (
          <button
            className="btn btn-primary btn-block checkout-btn"
            onClick={() => setIsCheckoutOpen(true)}
          >
            Checkout {formatPrice(getTotal())}
          </button>
        )}
      </div>

      <Modal
        isOpen={isCheckoutOpen}
        onClose={() => setIsCheckoutOpen(false)}
        title="Checkout"
        size="md"
      >
        <CheckoutModal
          items={items}
          total={getTotal()}
          onCheckout={handleCheckout}
          onCancel={() => setIsCheckoutOpen(false)}
          isLoading={createSale.isPending}
        />
      </Modal>
    </div>
  );
}
