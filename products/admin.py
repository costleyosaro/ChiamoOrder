from django.contrib import admin
from .models import Product, Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name")  # shows in list view
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "price", "category", "stock", "is_new", "is_promo", "flash_sale", "created_at")
    list_filter = ("category", "is_new", "is_promo", "flash_sale", "created_at")
    search_fields = ("name",)
    ordering = ("-created_at",)
    # If you added rating/num_reviews in model:
    # list_display += ("rating", "num_reviews")

    # Optional: show category as dropdown in admin
    autocomplete_fields = ("category",)

