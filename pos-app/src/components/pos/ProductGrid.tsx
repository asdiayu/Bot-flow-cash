import { Product } from '../../types/database';
import { Package, Plus } from 'lucide-react';

interface ProductGridProps {
  products: (Product & { category?: { id: string; name: string } | null })[];
  onAddToCart: (product: Product) => void;
}

export function ProductGrid({ products, onAddToCart }: ProductGridProps) {
  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      minimumFractionDigits: 0,
    }).format(price);
  };

  if (products.length === 0) {
    return (
      <div className="empty-state">
        <Package size={64} />
        <h2>No products available</h2>
        <p>Add products from the Products page</p>
      </div>
    );
  }

  return (
    <div className="pos-products-grid">
      {products.map((product) => (
        <button
          key={product.id}
          className={`pos-product-card ${product.stock <= 0 ? 'out-of-stock' : ''}`}
          onClick={() => onAddToCart(product)}
          disabled={product.stock <= 0}
        >
          <div className="pos-product-image">
            {product.image_url ? (
              <img src={product.image_url} alt={product.name} />
            ) : (
              <Package size={32} />
            )}
          </div>
          <div className="pos-product-info">
            <h4>{product.name}</h4>
            <p className="pos-product-price">{formatPrice(product.price)}</p>
            <span className={`pos-product-stock ${product.stock <= 5 ? 'low' : ''}`}>
              Stock: {product.stock}
            </span>
          </div>
          <div className="pos-product-add">
            <Plus size={20} />
          </div>
        </button>
      ))}
    </div>
  );
}
