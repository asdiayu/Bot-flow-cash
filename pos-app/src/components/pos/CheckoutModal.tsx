import { useState } from 'react';
import { CreditCard, Banknote, Smartphone, CheckCircle } from 'lucide-react';
import { CartItem } from '../../types/database';

interface CheckoutModalProps {
  items: CartItem[];
  total: number;
  onCheckout: (paymentMethod: string, notes?: string) => Promise<void>;
  onCancel: () => void;
  isLoading?: boolean;
}

const paymentMethods = [
  { id: 'cash', label: 'Cash', icon: Banknote },
  { id: 'card', label: 'Card', icon: CreditCard },
  { id: 'transfer', label: 'Transfer', icon: Smartphone },
];

export function CheckoutModal({
  items,
  total,
  onCheckout,
  onCancel,
  isLoading,
}: CheckoutModalProps) {
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [notes, setNotes] = useState('');
  const [cashReceived, setCashReceived] = useState('');
  const [isSuccess, setIsSuccess] = useState(false);

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      minimumFractionDigits: 0,
    }).format(price);
  };

  const change = cashReceived ? parseFloat(cashReceived) - total : 0;

  const handleSubmit = async () => {
    await onCheckout(paymentMethod, notes || undefined);
    setIsSuccess(true);
  };

  if (isSuccess) {
    return (
      <div className="checkout-success">
        <CheckCircle size={64} className="success-icon" />
        <h2>Transaction Complete!</h2>
        <p className="success-total">{formatPrice(total)}</p>
        {paymentMethod === 'cash' && change > 0 && (
          <p className="success-change">Change: {formatPrice(change)}</p>
        )}
        <button className="btn btn-primary btn-block" onClick={onCancel}>
          New Transaction
        </button>
      </div>
    );
  }

  return (
    <div className="checkout-form">
      <div className="checkout-summary">
        <h3>Order Summary</h3>
        <div className="checkout-items">
          {items.map((item) => (
            <div key={item.product.id} className="checkout-item">
              <span>
                {item.product.name} x {item.quantity}
              </span>
              <span>{formatPrice(item.product.price * item.quantity)}</span>
            </div>
          ))}
        </div>
        <div className="checkout-total">
          <span>Total</span>
          <span>{formatPrice(total)}</span>
        </div>
      </div>

      <div className="payment-methods">
        <h3>Payment Method</h3>
        <div className="payment-options">
          {paymentMethods.map((method) => (
            <button
              key={method.id}
              className={`payment-option ${paymentMethod === method.id ? 'selected' : ''}`}
              onClick={() => setPaymentMethod(method.id)}
            >
              <method.icon size={24} />
              <span>{method.label}</span>
            </button>
          ))}
        </div>
      </div>

      {paymentMethod === 'cash' && (
        <div className="form-group">
          <label htmlFor="cashReceived">Cash Received</label>
          <input
            id="cashReceived"
            type="number"
            value={cashReceived}
            onChange={(e) => setCashReceived(e.target.value)}
            placeholder="Enter amount received"
          />
          {change > 0 && (
            <p className="change-display">Change: {formatPrice(change)}</p>
          )}
        </div>
      )}

      <div className="form-group">
        <label htmlFor="notes">Notes (Optional)</label>
        <textarea
          id="notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Add transaction notes"
          rows={2}
        />
      </div>

      <div className="checkout-actions">
        <button className="btn btn-outline" onClick={onCancel} disabled={isLoading}>
          Cancel
        </button>
        <button
          className="btn btn-primary"
          onClick={handleSubmit}
          disabled={isLoading || (paymentMethod === 'cash' && parseFloat(cashReceived || '0') < total)}
        >
          {isLoading ? 'Processing...' : `Pay ${formatPrice(total)}`}
        </button>
      </div>
    </div>
  );
}
