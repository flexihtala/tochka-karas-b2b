from .auth.depends import provider as auth_provider
from .products.depends import provider as products_provider
from .skus.depends import provider as skus_provider


providers = [auth_provider, products_provider, skus_provider]
