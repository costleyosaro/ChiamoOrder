from django.core.management.base import BaseCommand
from products.models import Category, Product
from products.data.products_data import products_by_category

# ✅ Your ImageKit base URL
IMAGEKIT_BASE = "https://ik.imagekit.io/ljwnlcbqyu"

class Command(BaseCommand):
    help = "Load initial products into the database"

    def convert_image_url(self, local_path):
        """Convert local image path to ImageKit URL"""
        if not local_path:
            return ""
        
        # Already a full URL? Return as-is
        if local_path.startswith("http"):
            return local_path
        
        # Remove the local prefix
        # "assets/images/categories/beverages/Bev12.png"
        # becomes → "beverages/Bev12.png"
        path = local_path
        path = path.replace("assets/images/categories/", "")
        path = path.replace("assets/images/", "")
        
        # Build ImageKit URL
        return f"{IMAGEKIT_BASE}/{path}"

    def handle(self, *args, **kwargs):
        # ✅ Clear existing products first (optional)
        existing_count = Product.objects.count()
        if existing_count > 0:
            self.stdout.write(self.style.WARNING(
                f"⚠️  Found {existing_count} existing products. Clearing..."
            ))
            Product.objects.all().delete()
            Category.objects.all().delete()

        bulk_products = []

        for category_name, products in products_by_category.items():
            category_obj, _ = Category.objects.get_or_create(name=category_name)
            self.stdout.write(f"📁 Processing category: {category_name} ({len(products)} products)")

            for prod in products:
                # ✅ Auto-convert image path to ImageKit URL
                image_url = self.convert_image_url(prod.get("image", ""))

                bulk_products.append(Product(
                    name=prod["name"],
                    image=image_url,  # ✅ Now uses ImageKit URL!
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
            f"\n✅ Inserted {len(bulk_products)} products successfully!"
        ))
        self.stdout.write(self.style.SUCCESS(
            f"✅ Categories created: {Category.objects.count()}"
        ))
        
        # ✅ Show a sample to verify
        sample = Product.objects.first()
        if sample:
            self.stdout.write(f"\n📸 Sample image URL: {sample.image}")
            self.stdout.write(f"   Expected format: https://ik.imagekit.io/ljwnlcbqyu/beverages/Bev12.png")