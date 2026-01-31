import { Product } from '../../types/database';
import { Package, Edit, Trash2 } from 'lucide-react';

interface ProductCardProps {
  product: Product & { category?: { id: string; name: string } | null };
  onEdit: (product: Product) => void;
  onDelete: (id: string) => void;
}

export function ProductCard({ product, onEdit, onDelete }: ProductCardProps) {
  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      minimumFractionDigits: 0,
    }).format(price);
  };

  return (
    <div className="product-card">
      <div className="product-image">
        {product.image_url ? (
          <img src={product.image_url} alt={product.name} />
        ) : (
          <div className="product-placeholder">
            <Package size={48} />
          </div>
        )}
      </div>
      <div className="product-info">
        <h3 className="product-name">{product.name}</h3>
        {product.category && (
          <span className="product-category">{product.category.name}</span>
        )}
        <p className="product-price">{formatPrice(product.price)}</p>
        <p className="product-stock">
          Stock: <span className={product.stock <= 5 ? 'low-stock' : ''}>{product.stock}</span>
        </p>
      </div>
      <div className="product-actions">
        <button
          className="btn btn-icon"
          onClick={() => onEdit(product)}
          title="Edit product"
        >
          <Edit size={18} />
        </button>
        <button
          className="btn btn-icon btn-danger"
          onClick={() => onDelete(product.id)}
          title="Delete product"
        >
          <Trash2 size={18} />
        </button>
      </div>
    </div>
  );
}
