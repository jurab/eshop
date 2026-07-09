const API_BASE = 'http://127.0.0.1:8000/api';

const statusEl = document.getElementById('status');
const productsEl = document.getElementById('products');

function productCard(p) {
  const card = document.createElement('div');
  card.className = 'card';

  const name = document.createElement('h2');
  name.textContent = p.name;

  const desc = document.createElement('p');
  desc.className = 'desc';
  desc.textContent = p.description;

  const price = document.createElement('p');
  price.className = 'price';
  price.textContent = `${p.price} €`;

  const stock = document.createElement('p');
  const inStock = p.stock > 0;
  stock.className = inStock ? 'stock' : 'stock out';
  stock.textContent = inStock ? `${p.stock} in stock` : 'out of stock';

  card.append(name, desc, price, stock);
  return card;
}

async function loadProducts() {
  try {
    const res = await fetch(`${API_BASE}/products/`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const products = await res.json();

    if (products.length === 0) {
      statusEl.textContent = 'no products yet — add some in the admin';
      return;
    }

    statusEl.textContent = `${products.length} product(s)`;
    productsEl.replaceChildren(...products.map(productCard));
  } catch (err) {
    statusEl.textContent = `failed to load products: ${err.message} — is the API running on :8000?`;
  }
}

loadProducts();
