from django.core.management.base import BaseCommand
from products.models import Category, Product   # adjust app name!
from products.data import products_by_category  # import your data dictionary

class Command(BaseCommand):
    help = "Load initial products into the database"

    def handle(self, *args, **kwargs):
        bulk_products = []

        for category_name, products in products_by_category.items():
            category_obj, _ = Category.objects.get_or_create(name=category_name)

            for prod in products:
                bulk_products.append(Product(
                    name=prod["name"],
                    image=prod["image"],
                    category=category_obj,
                    rating=prod.get("rating", 0),
                    num_reviews=prod.get("numReviews", 0),
                    price=prod["price"],
                    stock=prod.get("stock", 0),
                    flash_sale=prod.get("flashSale", False),
                    is_new=prod.get("isNew", False),
                    is_promo=prod.get("isPromo", False),
                ))

        Product.objects.bulk_create(bulk_products, ignore_conflicts=True)
        self.stdout.write(self.style.SUCCESS(
            f"✅ Inserted {len(bulk_products)} products successfully!"
        ))
