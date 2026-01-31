import { useState } from 'react';
import { Plus, Search, Package } from 'lucide-react';
import { useProducts } from '../hooks/useProducts';
import { useCategories } from '../hooks/useCategories';
import { ProductCard } from '../components/products/ProductCard';
import { ProductForm } from '../components/products/ProductForm';
import { Modal } from '../components/ui/Modal';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { Product } from '../types/database';

export function ProductsPage() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');

  const { products, isLoading, createProduct, updateProduct, deleteProduct } = useProducts();
  const { categories } = useCategories();

  const filteredProducts = products.filter((product) => {
    const matchesSearch = product.name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = !selectedCategory || product.category_id === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  const handleSubmit = async (data: Omit<Product, 'id' | 'created_at' | 'updated_at' | 'user_id'>) => {
    if (editingProduct) {
      await updateProduct.mutateAsync({ id: editingProduct.id, ...data });
    } else {
      await createProduct.mutateAsync(data);
    }
    setIsModalOpen(false);
    setEditingProduct(null);
  };

  const handleEdit = (product: Product) => {
    setEditingProduct(product);
    setIsModalOpen(true);
  };

  const handleDelete = async (id: string) => {
    if (window.confirm('Are you sure you want to delete this product?')) {
      await deleteProduct.mutateAsync(id);
    }
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setEditingProduct(null);
  };

  if (isLoading) {
    return <LoadingSpinner text="Loading products..." />;
  }

  return (
    <div className="page products-page">
      <div className="page-header">
        <div className="page-title">
          <Package size={28} />
          <h1>Products</h1>
          <span className="badge">{products.length}</span>
        </div>
        <button
          className="btn btn-primary"
          onClick={() => setIsModalOpen(true)}
        >
          <Plus size={20} />
          <span>Add Product</span>
        </button>
      </div>

      <div className="filters">
        <div className="search-box">
          <Search size={20} className="search-icon" />
          <input
            type="text"
            placeholder="Search products..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <select
          value={selectedCategory}
          onChange={(e) => setSelectedCategory(e.target.value)}
          className="filter-select"
        >
          <option value="">All Categories</option>
          {categories.map((cat) => (
            <option key={cat.id} value={cat.id}>
              {cat.name}
            </option>
          ))}
        </select>
      </div>

      {filteredProducts.length === 0 ? (
        <div className="empty-state">
          <Package size={64} />
          <h2>No products found</h2>
          <p>
            {searchTerm || selectedCategory
              ? 'Try adjusting your filters'
              : 'Add your first product to get started'}
          </p>
        </div>
      ) : (
        <div className="products-grid">
          {filteredProducts.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              onEdit={handleEdit}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}

      <Modal
        isOpen={isModalOpen}
        onClose={handleCloseModal}
        title={editingProduct ? 'Edit Product' : 'Add New Product'}
        size="md"
      >
        <ProductForm
          product={editingProduct}
          categories={categories}
          onSubmit={handleSubmit}
          onCancel={handleCloseModal}
          isLoading={createProduct.isPending || updateProduct.isPending}
        />
      </Modal>
    </div>
  );
}
