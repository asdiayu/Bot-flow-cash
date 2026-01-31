import { CartItem } from '../../types/database';
import { Minus, Plus, Trash2, ShoppingCart } from 'lucide-react';

interface CartProps {
  items: CartItem[];
  onUpdateQuantity: (productId: string, quantity: number) => void;
  onRemoveItem: (productId: string) => void;
  total: number;
}

export function Cart({ items, onUpdateQuantity, onRemoveItem, total }: CartProps) {
  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      minimumFractionDigits: 0,
    }).format(price);
  };

  if (items.length === 0) {
    return (
      <div className="cart-empty">
        <ShoppingCart size={48} />
        <p>Cart is empty</p>
        <span>Add products to start a transaction</span>
      </div>
    );
  }

  return (
    <div className="cart">
      <div className="cart-items">
        {items.map((item) => (
          <div key={item.product.id} className="cart-item">
            <div className="cart-item-info">
              <h4>{item.product.name}</h4>
              <p className="cart-item-price">{formatPrice(item.product.price)}</p>
            </div>
            <div className="cart-item-controls">
              <button
                className="qty-btn"
                onClick={() => onUpdateQuantity(item.product.id, item.quantity - 1)}
              >
                <Minus size={16} />
              </button>
              <span className="qty-display">{item.quantity}</span>
              <button
                className="qty-btn"
                onClick={() => onUpdateQuantity(item.product.id, item.quantity + 1)}
                disabled={item.quantity >= item.product.stock}
              >
                <Plus size={16} />
              </button>
              <button
                className="remove-btn"
                onClick={() => onRemoveItem(item.product.id)}
              >
                <Trash2 size={16} />
              </button>
            </div>
            <div className="cart-item-subtotal">
              {formatPrice(item.product.price * item.quantity)}
            </div>
          </div>
        ))}
      </div>
      <div className="cart-total">
        <span>Total</span>
        <span className="total-amount">{formatPrice(total)}</span>
      </div>
    </div>
  );
}
