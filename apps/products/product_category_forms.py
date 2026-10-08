"""Общие правила основной и дополнительных категорий обеих форм."""
from .models import Category


class ProductCategoryFormMixin:
    def clean(self):
        cleaned = super().clean()
        main = cleaned.get("category")
        selected = cleaned.get("categories")
        if "categories" in self.errors:
            return cleaned
        if selected is not None:
            ids = set(selected.values_list("pk", flat=True))
            if main is not None:
                ids.add(main.pk)
            elif ids and "category" not in self.errors:
                self.add_error("category", "Выберите основную категорию объекта.")
            cleaned["categories"] = Category.objects.filter(pk__in=ids)
        return cleaned
