# apps/products/models/__init__.py

from .badge import Badge
from .category import Category
from .product_model import Product                # новая Django-модель
from .product_attribute import ProductAttribute
from .product_gallery import ProductGalleryImage  # ← новая модель галереи
from .attribute_type import AttributeType  # ← типы характеристик
from .attribute_value import AttributeValue  # ← значение характеристик
from .brand import Brand  # ← Бренды
from .location import Location  # География каталога жилья.
