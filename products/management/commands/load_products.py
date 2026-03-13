# products/management/commands/load_products.py

from django.core.management.base import BaseCommand
from products.models import Category, Product
from products.data.products_data import products_by_category

IMAGEKIT_BASE = "https://ik.imagekit.io/ljwnlcbqyu"


class Command(BaseCommand):
    help = "Load products into the database (safe to re-run)"

    def convert_image_url(self, local_path):
        if not local_path:
            return ""
        if local_path.startswith("http"):
            return local_path
        path = local_path.replace("assets/images/categories/", "")
        return f"{IMAGEKIT_BASE}/{path}"

    def handle(self, *args, **kwargs):
        # ✅ Get existing names to SKIP duplicates (NOT delete!)
        existing_names = set(
            Product.objects.values_list('name', flat=True)
        )

        bulk_products = []
        skipped = 0

        for category_name, products in products_by_category.items():
            category_obj, _ = Category.objects.get_or_create(
                name=category_name
            )
            self.stdout.write(
                f"📁 {category_name} ({len(products)} products)"
            )

            for prod in products:
                # ✅ Skip if already exists
                if prod["name"] in existing_names:
                    skipped += 1
                    continue

                image_url = self.convert_image_url(
                    prod.get("image", "")
                )

                bulk_products.append(Product(
                    name=prod["name"],
                    image=image_url,
                    category=category_obj,
                    rating=prod.get("rating", 0),
                    num_reviews=prod.get("numReviews", 0),
                    price=prod["price"],
                    stock=prod.get("stock", 0),
                    flash_sale=prod.get("flashSale", False),
                    is_new=prod.get("isNew", False),
                    is_promo=prod.get("isPromo", False),
                ))

        if bulk_products:
            Product.objects.bulk_create(
                bulk_products, ignore_conflicts=True
            )

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ NEW products added: {len(bulk_products)}"
        ))
        self.stdout.write(self.style.WARNING(
            f"⏭️  Skipped (existing): {skipped}"
        ))
        self.stdout.write(
            f"📊 Total in DB: {Product.objects.count()}"
        )

        # Show sample to verify image URLs
        if bulk_products:
            sample = Product.objects.filter(
                name=bulk_products[0].name
            ).first()
            if sample:
                self.stdout.write(
                    f"\n📸 Sample: {sample.name}"
                )
                self.stdout.write(
                    f"   URL: {sample.image}"
                )