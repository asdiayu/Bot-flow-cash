import { Loader2 } from 'lucide-react';

interface LoadingSpinnerProps {
  size?: number;
  text?: string;
}

export function LoadingSpinner({ size = 40, text }: LoadingSpinnerProps) {
  return (
    <div className="loading-spinner">
      <Loader2 size={size} className="spinner" />
      {text && <p>{text}</p>}
    </div>
  );
}
