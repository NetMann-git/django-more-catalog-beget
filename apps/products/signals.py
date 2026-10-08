# apps/products/signals.py
from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save, m2m_changed
from django.dispatch import receiver

from apps.products.models import Brand, Product, ProductGalleryImage, AttributeType, AttributeValue
from apps.products.image_cleanup import delete_after_commit


@receiver(post_save, sender=Product)
@receiver(post_delete, sender=Product)
@receiver(post_save, sender=Brand)
@receiver(post_delete, sender=Brand)
def clear_catalog_cache(**kwargs):
    cache.delete("catalog_queryset")
    cache.delete("catalog_filters")


@receiver(pre_save, sender=Product)
@receiver(pre_save, sender=ProductGalleryImage)
@receiver(pre_save, sender=AttributeType)
@receiver(pre_save, sender=AttributeValue)
@receiver(pre_save, sender=Brand)
def remember_previous_image(
    sender, instance, using, raw=False, update_fields=None, **kwargs
) -> None:
    """Remember the stored image before saving a replacement or clearing it."""
    instance._previous_image_name = None
    if raw or not instance.pk:
        return
    field_name = ('icon' if sender in (AttributeType, AttributeValue)
                  else 'logo' if sender is Brand else 'image')
    if update_fields is not None and field_name not in update_fields:
        return
    instance._previous_image_name = (
        sender._base_manager.using(using)
        .filter(pk=instance.pk)
        .values_list(field_name, flat=True)
        .first()
    )


@receiver(post_save, sender=Product)
@receiver(post_save, sender=ProductGalleryImage)
@receiver(post_save, sender=AttributeType)
@receiver(post_save, sender=AttributeValue)
@receiver(post_save, sender=Brand)
def remove_replaced_image(
    sender, instance, using, raw=False, **kwargs
) -> None:
    """Remove the former image only after the new database state commits."""
    if raw:
        return
    previous_name = getattr(instance, "_previous_image_name", None)
    field_name = ('icon' if sender in (AttributeType, AttributeValue)
                  else 'logo' if sender is Brand else 'image')
    if previous_name and previous_name != getattr(instance, field_name).name:
        transaction.on_commit(
            lambda: delete_after_commit(
                instance, previous_name, using, field_name=field_name,
            ),
            using=using,
        )
    instance._previous_image_name = None


@receiver(post_delete, sender=Product)
@receiver(post_delete, sender=ProductGalleryImage)
@receiver(post_delete, sender=AttributeType)
@receiver(post_delete, sender=AttributeValue)
@receiver(post_delete, sender=Brand)
def remove_deleted_product_image(sender, instance, using, **kwargs) -> None:
    """Delete physical files only after the database transaction commits."""
    field_name = ('icon' if sender in (AttributeType, AttributeValue)
                  else 'logo' if sender is Brand else 'image')
    name = getattr(instance, field_name).name
    if name:
        transaction.on_commit(
            lambda: delete_after_commit(
                instance, name, using, field_name=field_name,
            ), using=using,
        )


@receiver(m2m_changed, sender=Product.categories.through)
def clear_category_membership_cache(sender, action, **kwargs):
    """Обновлять каталог после изменения категорий через формы и импорт."""
    if action in {"post_add", "post_remove", "post_clear"}:
        transaction.on_commit(lambda: (cache.delete("catalog_queryset"), cache.delete("catalog_filters")))
