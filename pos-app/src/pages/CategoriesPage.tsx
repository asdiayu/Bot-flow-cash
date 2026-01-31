import { useState } from 'react';
import { Plus, Search, FolderOpen, Edit, Trash2 } from 'lucide-react';
import { useCategories } from '../hooks/useCategories';
import { Modal } from '../components/ui/Modal';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { Category } from '../types/database';

export function CategoriesPage() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingCategory, setEditingCategory] = useState<Category | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const { categories, isLoading, createCategory, updateCategory, deleteCategory } = useCategories();

  const filteredCategories = categories.filter((cat) =>
    cat.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (editingCategory) {
      await updateCategory.mutateAsync({
        id: editingCategory.id,
        name,
        description: description || null,
      });
    } else {
      await createCategory.mutateAsync({
        name,
        description: description || null,
      });
    }
    handleCloseModal();
  };

  const handleEdit = (category: Category) => {
    setEditingCategory(category);
    setName(category.name);
    setDescription(category.description || '');
    setIsModalOpen(true);
  };

  const handleDelete = async (id: string) => {
    if (window.confirm('Are you sure you want to delete this category?')) {
      await deleteCategory.mutateAsync(id);
    }
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setEditingCategory(null);
    setName('');
    setDescription('');
  };

  if (isLoading) {
    return <LoadingSpinner text="Loading categories..." />;
  }

  return (
    <div className="page categories-page">
      <div className="page-header">
        <div className="page-title">
          <FolderOpen size={28} />
          <h1>Categories</h1>
          <span className="badge">{categories.length}</span>
        </div>
        <button
          className="btn btn-primary"
          onClick={() => setIsModalOpen(true)}
        >
          <Plus size={20} />
          <span>Add Category</span>
        </button>
      </div>

      <div className="filters">
        <div className="search-box">
          <Search size={20} className="search-icon" />
          <input
            type="text"
            placeholder="Search categories..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </div>

      {filteredCategories.length === 0 ? (
        <div className="empty-state">
          <FolderOpen size={64} />
          <h2>No categories found</h2>
          <p>
            {searchTerm
              ? 'Try adjusting your search'
              : 'Add your first category to organize products'}
          </p>
        </div>
      ) : (
        <div className="categories-list">
          {filteredCategories.map((category) => (
            <div key={category.id} className="category-card">
              <div className="category-info">
                <FolderOpen size={24} className="category-icon" />
                <div>
                  <h3>{category.name}</h3>
                  {category.description && <p>{category.description}</p>}
                </div>
              </div>
              <div className="category-actions">
                <button
                  className="btn btn-icon"
                  onClick={() => handleEdit(category)}
                  title="Edit category"
                >
                  <Edit size={18} />
                </button>
                <button
                  className="btn btn-icon btn-danger"
                  onClick={() => handleDelete(category.id)}
                  title="Delete category"
                >
                  <Trash2 size={18} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal
        isOpen={isModalOpen}
        onClose={handleCloseModal}
        title={editingCategory ? 'Edit Category' : 'Add New Category'}
        size="sm"
      >
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="categoryName">Category Name *</label>
            <input
              id="categoryName"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Enter category name"
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="categoryDescription">Description</label>
            <textarea
              id="categoryDescription"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Enter description"
              rows={3}
            />
          </div>
          <div className="form-actions">
            <button type="button" className="btn btn-outline" onClick={handleCloseModal}>
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={createCategory.isPending || updateCategory.isPending}
            >
              {createCategory.isPending || updateCategory.isPending
                ? 'Saving...'
                : editingCategory
                ? 'Update'
                : 'Add Category'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
