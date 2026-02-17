# orders/views.py
from django.shortcuts import get_object_or_404
from rest_framework import generics, viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
import logging
import traceback
from django.db.models import Q


from .models import (
    Cart, CartItem, Order, OrderItem,
    SmartList, SmartListItem
)
from products.models import Product
from .serializers import CartSerializer, OrderSerializer


# ---------------- Helpers ----------------
logger = logging.getLogger(__name__)

def _get_product_by_identifier(identifier):
    """
    Robust lookup helper with verbose debug logging.
    Tries (in order):
      1. exact slug (case-sensitive)
      2. slug__iexact (case-insensitive)
      3. numeric id
      4. slug__icontains / name__icontains (broad search)
      5. handles "prefix-N" or "prefix_N" by trying prefix and numeric suffix heuristics

    Returns Product instance or None.
    **DEBUG INFO**: prints/logs every attempt so you can see why a lookup returned None.
    Remove the debug prints/logs when done.
    """
    logger.debug("[_get_product_by_identifier] START -> raw identifier: %r", identifier)
    print(f"[DEBUG] _get_product_by_identifier start: {identifier!r}")

    if identifier is None:
        logger.debug("[_get_product_by_identifier] identifier is None -> returning None")
        print("[DEBUG] identifier is None -> returning None")
        return None

    ident = str(identifier).strip()
    if not ident:
        logger.debug("[_get_product_by_identifier] identifier empty after strip -> returning None")
        print("[DEBUG] identifier empty after strip -> returning None")
        return None

    # 1) Try exact slug (case-sensitive)
    try:
        product = Product.objects.get(slug=ident)
        logger.debug("[_get_product_by_identifier] found by exact slug (case-sensitive): %s (id=%s)", product.slug, product.id)
        print("[DEBUG] Found by exact slug (case-sensitive):", product.id, product.slug)
        return product
    except Product.DoesNotExist:
        logger.debug("[_get_product_by_identifier] not found by exact slug (case-sensitive): %r", ident)
        print("[DEBUG] Not found by exact slug (case-sensitive).")
    except Exception as e:
        logger.exception("[_get_product_by_identifier] exception on exact slug lookup")
        print("[DEBUG] Exception during exact slug lookup:", e)
        traceback.print_exc()

    # 2) Try slug case-insensitive
    try:
        product = Product.objects.get(slug__iexact=ident)
        logger.debug("[_get_product_by_identifier] found by slug__iexact: %s (id=%s)", product.slug, product.id)
        print("[DEBUG] Found by slug__iexact:", product.id, product.slug)
        return product
    except Product.DoesNotExist:
        logger.debug("[_get_product_by_identifier] not found by slug__iexact: %r", ident)
        print("[DEBUG] Not found by slug__iexact.")
    except Exception as e:
        logger.exception("[_get_product_by_identifier] exception on slug__iexact")
        print("[DEBUG] Exception during slug__iexact lookup:", e)
        traceback.print_exc()

    # 3) Try numeric id
    try:
        pid = int(ident)
        try:
            product = Product.objects.get(id=pid)
            logger.debug("[_get_product_by_identifier] found by numeric id: %s", product.id)
            print("[DEBUG] Found by numeric id:", product.id)
            return product
        except Product.DoesNotExist:
            logger.debug("[_get_product_by_identifier] no product with id=%s", pid)
            print(f"[DEBUG] No product with id={pid}")
    except (ValueError, TypeError):
        logger.debug("[_get_product_by_identifier] identifier not an integer: %r", ident)
        print("[DEBUG] identifier not an integer:", ident)
    except Exception as e:
        logger.exception("[_get_product_by_identifier] exception converting identifier to int")
        print("[DEBUG] Exception converting identifier to int:", e)
        traceback.print_exc()

    # 4) Broad search: slug or name contains identifier (case-insensitive)
    try:
        candidates = Product.objects.filter(
            Q(slug__icontains=ident) | Q(name__icontains=ident)
        ).distinct()
        logger.debug("[_get_product_by_identifier] broad search candidates count: %d for ident=%r", candidates.count(), ident)
        print(f"[DEBUG] Broad search candidates count: {candidates.count()} for ident={ident!r}")
        if candidates.count() == 1:
            product = candidates.first()
            logger.debug("[_get_product_by_identifier] single broad candidate chosen id=%s slug=%s", product.id, product.slug)
            print("[DEBUG] Chosen single broad candidate:", product.id, product.slug)
            return product
        elif candidates.count() > 1:
            # Try to pick best candidate: slug exact-ish, or name exact-ish
            ident_lower = ident.lower()
            for cand in candidates:
                if cand.slug.lower() == ident_lower or (cand.name and cand.name.lower() == ident_lower):
                    logger.debug("[_get_product_by_identifier] picking candidate by exact match among many: id=%s", cand.id)
                    print("[DEBUG] Picking candidate by exact match among many:", cand.id)
                    return cand
            # fallback: choose first but log ambiguity
            product = candidates.first()
            logger.warning("[_get_product_by_identifier] multiple candidates found for %r - returning first id=%s slug=%s", ident, product.id, product.slug)
            print("[WARNING] multiple candidates found - returning first:", product.id, product.slug)
            return product
    except Exception as e:
        logger.exception("[_get_product_by_identifier] exception during broad search")
        print("[DEBUG] Exception during broad search:", e)
        traceback.print_exc()

    # 5) Heuristics for strings like "beverage-2" or "beverage_2"
    try:
        sep_candidates = ["-", "_", ":"]
        for sep in sep_candidates:
            if sep in ident:
                parts = ident.split(sep)
                prefix = parts[0].strip()
                suffix = parts[-1].strip()
                logger.debug("[_get_product_by_identifier] trying heuristic split by %r -> prefix=%r suffix=%r", sep, prefix, suffix)
                print(f"[DEBUG] Heuristic split by {sep}: prefix={prefix!r}, suffix={suffix!r}")

                # If suffix is numeric, try direct id
                try:
                    pid = int(suffix)
                    try:
                        product = Product.objects.get(id=pid)
                        logger.debug("[_get_product_by_identifier] heuristic found product by numeric suffix id=%s", pid)
                        print("[DEBUG] Heuristic found by numeric suffix id:", pid)
                        return product
                    except Product.DoesNotExist:
                        logger.debug("[_get_product_by_identifier] no product with heuristic id suffix=%s", pid)
                        print("[DEBUG] no product with heuristic id suffix:", pid)
                except (ValueError, TypeError):
                    logger.debug("[_get_product_by_identifier] suffix not integer, trying prefix search")
                    print("[DEBUG] suffix not integer; trying prefix search")

                # Try to find by prefix in slug/name
                candidate = Product.objects.filter(Q(slug__icontains=prefix) | Q(name__icontains=prefix)).first()
                if candidate:
                    logger.debug("[_get_product_by_identifier] heuristic picked candidate id=%s slug=%s", candidate.id, candidate.slug)
                    print("[DEBUG] Heuristic picked candidate:", candidate.id, candidate.slug)
                    return candidate
    except Exception as e:
        logger.exception("[_get_product_by_identifier] exception during heuristic step")
        print("[DEBUG] Exception during heuristic step:", e)
        traceback.print_exc()

    # Nothing matched
    logger.debug("[_get_product_by_identifier] NO MATCH for identifier=%r -> returning None", identifier)
    print("[DEBUG] NO MATCH for identifier:", identifier)
    return None



# ---------------- CART ---------------- #
class CartView(generics.RetrieveAPIView):
    """
    GET /api/orders/cart/
    Return or create the user's cart.
    """
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        cart, _ = Cart.objects.get_or_create(user=self.request.user)
        return cart


class AddToCartView(generics.GenericAPIView):
    """
    POST /api/orders/cart/add/
    Accepts product_id (slug or numeric) and quantity.
    Deducts from global stock.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        identifier = request.data.get("product_id") or request.data.get("productId")
        if not identifier:
            return Response(
                {"error": "Product identifier is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        product = _get_product_by_identifier(identifier)
        if not product:
            return Response(
                {"detail": "No Product matches the given query."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            quantity = int(request.data.get("quantity", 1))
        except (ValueError, TypeError):
            return Response(
                {"error": "Quantity must be a number"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ✅ Check if stock is sufficient
        if product.stock < quantity:
            return Response(
                {"error": f"Not enough stock available for {product.name}. Only {product.stock} left."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ✅ Deduct from global stock
        product.stock -= quantity
        product.save(update_fields=["stock"])

        # ✅ Add item to user’s cart
        cart, _ = Cart.objects.get_or_create(user=request.user)
        item, created = CartItem.objects.get_or_create(cart=cart, product=product)
        if created:
            item.quantity = quantity
        else:
            item.quantity += quantity
        item.save()

        # ✅ Decide whether to show stock balance or hide it
        stock_balance = None if product.stock == 300 else product.stock

        return Response(
            {
                "message": f"Added {quantity} × {product.name} to cart",
                "cartItem": {
                    "id": item.id,
                    "product": product.name,
                    "quantity": item.quantity,
                    "price": product.price,
                    "stock": stock_balance,  # 👈 only shows when below 300
                },
            },
            status=status.HTTP_200_OK,
        )



class RemoveFromCartView(generics.GenericAPIView):
    """
    POST /api/orders/cart/remove/
    payload: { product_id: slugOrId }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        identifier = request.data.get("product_id") or request.data.get("productId")
        if not identifier:
            return Response({"error": "Product identifier is required"}, status=status.HTTP_400_BAD_REQUEST)

        product = _get_product_by_identifier(identifier)
        cart = get_object_or_404(Cart, user=request.user)

        if not product:
            return Response({"detail": "No Product matches the given query."}, status=status.HTTP_404_NOT_FOUND)

        item = CartItem.objects.filter(cart=cart, product=product).first()
        if item:
            item.delete()
            return Response({"message": "Removed from cart"})
        return Response({"error": "Item not found"}, status=status.HTTP_404_NOT_FOUND)


class UpdateCartItemView(generics.GenericAPIView):
    """
    PUT /api/orders/cart/update/
    payload: { product_id: slugOrId, quantity: n }
    Updates item quantity and adjusts global stock accordingly.
    """
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request):
        identifier = request.data.get("product_id") or request.data.get("productId")
        quantity = request.data.get("quantity")

        if not identifier or quantity is None:
            return Response(
                {"error": "Product identifier and quantity required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        product = _get_product_by_identifier(identifier)
        if not product:
            return Response(
                {"detail": "No Product matches the given query."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            quantity = int(quantity)
        except (ValueError, TypeError):
            return Response(
                {"error": "Quantity must be an integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if quantity < 1:
            return Response(
                {"error": "Quantity must be at least 1"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cart, _ = Cart.objects.get_or_create(user=request.user)
        item = CartItem.objects.filter(cart=cart, product=product).first()

        if not item:
            return Response(
                {"detail": "This product is not in your cart"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ✅ Adjust stock difference
        prev_quantity = item.quantity
        diff = quantity - prev_quantity

        # If user increased quantity, deduct more stock
        if diff > 0:
            if product.stock < diff:
                return Response(
                    {"error": "Not enough stock available"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            product.stock -= diff
        # If user decreased quantity, restock the difference
        elif diff < 0:
            product.stock += abs(diff)

        product.save(update_fields=["stock"])

        # ✅ Update cart item quantity
        item.quantity = quantity
        item.save(update_fields=["quantity"])

        return Response(
            {
                "message": f"Updated {product.name} to quantity {item.quantity}",
                "cartItem": {
                    "id": item.id,
                    "product": product.name,
                    "quantity": item.quantity,
                    "price": product.price,
                },
                "stock_balance": product.stock,
            },
            status=status.HTTP_200_OK,
        )


class ClearCartView(generics.GenericAPIView):
    """
    POST /api/orders/cart/clear/
    Clear all items in the user's cart.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        deleted_count, _ = CartItem.objects.filter(cart=cart).delete()
        return Response({
            "message": f"Cleared cart. Removed {deleted_count} items.",
            "cart": []
        })


# orders/views.py
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Cart, Order, OrderItem
from django.utils import timezone


from django.utils import timezone
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Order, OrderItem
from .models import Cart  # ✅ adjust import if your Cart model is in a different module


class CheckoutView(generics.GenericAPIView):
    """
    POST /api/orders/checkout/
    Create an Order from the cart and clear the cart.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        print(f"[DEBUG] Checkout triggered by {user}")

        # ✅ Get user's cart
        try:
            cart = get_object_or_404(Cart, user=user)
        except Exception as e:
            print("[DEBUG] Cart not found:", e)
            return Response({"error": "Cart not found."}, status=status.HTTP_404_NOT_FOUND)

        cart_items = list(cart.items.all())
        if not cart_items:
            return Response({"error": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Create new order (auto-generates order_id in model)
        order = Order.objects.create(
            user=user,
            total=cart.total_price(),
            source="cart",
            progress=1,  # “Order Confirmed” step
            status="pending",
        )

        # ✅ Add all cart items to order
        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price=item.product.price,
            )

        # ✅ Clear cart
        cart.items.all().delete()

        print(f"[DEBUG] Order {order.order_id} created for {user} ({len(cart_items)} items)")

        # ✅ Return success response
        return Response(
            {
                "message": "Order placed successfully!",
                "order_id": order.order_id,
                "redirect": "/orders",  # frontend can redirect here
                "progress": order.progress,
                "status": order.status,
                "source": order.source,
            },
            status=status.HTTP_201_CREATED,
        )




# ---------------- ORDERS (viewset for CRUD on Orders) ---------------- #
class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    # return newest orders first so frontend shows newest at top
    def get_queryset(self):
        return self.queryset.filter(user=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

# ---------------- SMARTLISTS (explicit APIViews) ---------------- #
class SmartListListCreateAPIView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        smartlists = SmartList.objects.filter(user=request.user).prefetch_related("items__product")
        data = []
        for sl in smartlists:
            items = []
            for it in sl.items.all():
                items.append({
                    "id": it.id,
                    "product_id": it.product.id if it.product else None,
                    "product": it.product.name if it.product else None,
                    "quantity": it.quantity,
                })
            data.append({"id": sl.id, "name": sl.name, "items": items})
        return Response(data)

    def post(self, request):
        name = request.data.get("name", "Default List")
        smartlist, _ = SmartList.objects.get_or_create(user=request.user, name=name)
        return Response({"id": smartlist.id, "name": smartlist.name}, status=status.HTTP_201_CREATED)

import requests

class SmartListDetailAPIView(APIView):
    """
    GET / DELETE a single smartlist:
    GET    /api/orders/smartlists/<pk>/
    DELETE /api/orders/smartlists/<pk>/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        print(f"[DEBUG] SmartListDetailAPIView.get() pk={pk}, user={request.user}")
        sl = get_object_or_404(SmartList, id=pk, user=request.user)

        items = []
        for it in sl.items.select_related("product"):
            product = it.product
            product_data = None
            if product:
                try:
                    image_url = (
                        request.build_absolute_uri(product.image.url)
                        if getattr(product, "image", None)
                        else None
                    )
                except Exception:
                    image_url = None

                product_data = {
                    "id": product.id,
                    "name": product.name,
                    "price": float(product.price) if product.price else 0,
                    "image": image_url,
                }

            items.append({
                "id": it.id,
                "product_id": product.id if product else None,
                "product": product_data,
                "quantity": it.quantity,
            })

        return Response({
            "id": sl.id,
            "name": sl.name,
            "items": items
        }, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        print(f"[DEBUG] SmartListDetailAPIView.delete() pk={pk}, user={request.user}")
        sl = get_object_or_404(SmartList, id=pk, user=request.user)
        sl.delete()
        return Response({"message": "Smartlist deleted"}, status=status.HTTP_200_OK)


class SmartListAddItemAPIView(APIView):
    """
    POST /api/orders/smartlists/<pk>/add_item/
    payload: { product_id: slugOrId, quantity: n }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        print("=" * 60)
        print(f"[DEBUG] SmartListAddItemAPIView.post() user={request.user}, pk={pk}")
        print(f"[DEBUG] request.data={request.data}")

        smartlist = get_object_or_404(SmartList, id=pk, user=request.user)

        identifier = request.data.get("product_id") or request.data.get("productId")
        if not identifier:
            print("[DEBUG] Missing product identifier")
            return Response({"error": "Product identifier required"}, status=status.HTTP_400_BAD_REQUEST)

        product = _get_product_by_identifier(identifier)
        if not product:
            print(f"[DEBUG] No product found for identifier={identifier}")
            return Response({"detail": "No Product matches the given query."}, status=status.HTTP_404_NOT_FOUND)

        try:
            quantity = int(request.data.get("quantity", 1))
        except (ValueError, TypeError):
            print(f"[DEBUG] Invalid quantity: {request.data.get('quantity')}")
            return Response({"error": "Quantity must be a number"}, status=status.HTTP_400_BAD_REQUEST)

        item, created = SmartListItem.objects.get_or_create(smartlist=smartlist, product=product)
        if not created:
            item.quantity += quantity
        else:
            item.quantity = quantity
        item.save()

        try:
            image_url = (
                request.build_absolute_uri(product.image.url)
                if getattr(product, "image", None)
                else None
            )
        except Exception:
            image_url = None

        print(f"[DEBUG] Added {quantity} x {product.name} (id={product.id}) to SmartList {pk}")

        return Response({
            "id": item.id,
            "product": {
                "id": product.id,
                "name": product.name,
                "price": float(product.price) if product.price else 0,
                "image": image_url,
            },
            "quantity": item.quantity,
        }, status=status.HTTP_200_OK)


class SmartListUpdateItemAPIView(APIView):
    """
    POST /api/orders/smartlists/<pk>/update_item/
    payload: { item_id: <id>, quantity: n }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        smartlist = get_object_or_404(SmartList, id=pk, user=request.user)
        item_id = request.data.get("item_id")
        if not item_id:
            return Response({"error": "item_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        item = get_object_or_404(SmartListItem, id=item_id, smartlist=smartlist)
        try:
            item.quantity = int(request.data.get("quantity", item.quantity))
        except (ValueError, TypeError):
            return Response({"error": "Quantity must be a number"}, status=status.HTTP_400_BAD_REQUEST)
        item.save()

        return Response({"id": item.id, "product_id": item.product.id, "product": item.product.name, "quantity": item.quantity})


class SmartListRemoveItemAPIView(APIView):
    """
    POST /api/orders/smartlists/<pk>/remove_item/
    payload: { item_id: <id> }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        smartlist = get_object_or_404(SmartList, id=pk, user=request.user)
        item_id = request.data.get("item_id")
        if not item_id:
            return Response({"error": "item_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        item = get_object_or_404(SmartListItem, id=item_id, smartlist=smartlist)
        item.delete()
        return Response({"message": "Item removed"})


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Order, OrderItem, SmartList
from .serializers import OrderSerializer


class SmartListOrderAllAPIView(APIView):
    """
    POST /api/orders/smartlists/<int:pk>/order_all/
    Converts all SmartList items into an Order and clears the SmartList.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        print(f"[DEBUG] SmartListOrderAll triggered by {user} for SmartList {pk}")

        # ✅ Validate smartlist
        smartlist = get_object_or_404(SmartList, id=pk, user=user)

        items = list(smartlist.items.all())
        if not items:
            return Response({"error": "Smart list is empty."}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Compute total
        total = sum(item.product.price * item.quantity for item in items)

        # ✅ Create order (auto-generates unique order_id)
        order = Order.objects.create(
            user=user,
            total=total,
            source="smartlist",
            progress=1,  # "Order Confirmed"
            status="pending",
        )

        # ✅ Transfer all smartlist items into OrderItems
        for item in items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price=item.product.price,
            )

        # ✅ Clear SmartList
        smartlist.items.all().delete()

        print(f"[DEBUG] SmartList {smartlist.id} converted to Order {order.order_id} ({len(items)} items)")

        # ✅ Serialize order and respond
        serializer = OrderSerializer(order)
        return Response(
            {
                "message": f"All items from '{smartlist.name}' have been ordered successfully.",
                "order": serializer.data,
                "redirect": "/orders",  # frontend can use this for navigation
            },
            status=status.HTTP_201_CREATED,
        )

# orders/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import SmartList, SmartListItem, Order, OrderItem
from .serializers import SmartListSerializer, SmartListItemSerializer, OrderSerializer
from products.models import Product
from .utils import _get_product_by_identifier  # if you already have this helper


# ---------------- SMARTLISTS ---------------- #
class SmartListListCreateAPIView(APIView):
    """
    GET  /api/orders/smartlists/
    POST /api/orders/smartlists/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        smartlists = (
            SmartList.objects.filter(user=request.user)
            .prefetch_related("items__product")
            .order_by("-created_at")
        )
        serializer = SmartListSerializer(smartlists, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        name = request.data.get("name", "Default List")
        smartlist, created = SmartList.objects.get_or_create(user=request.user, name=name)
        serializer = SmartListSerializer(smartlist, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class SmartListDetailAPIView(APIView):
    """
    GET /api/orders/smartlists/<pk>/
    DELETE /api/orders/smartlists/<pk>/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        smartlist = get_object_or_404(SmartList, id=pk, user=request.user)
        serializer = SmartListSerializer(smartlist, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        smartlist = get_object_or_404(SmartList, id=pk, user=request.user)
        smartlist.delete()
        return Response({"message": "Smartlist deleted successfully"}, status=status.HTTP_200_OK)


class SmartListAddItemAPIView(APIView):
    """
    POST /api/orders/smartlists/<pk>/add_item/
    payload: { product_id: slugOrId, quantity: n }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        smartlist = get_object_or_404(SmartList, id=pk, user=request.user)

        identifier = request.data.get("product_id") or request.data.get("productId")
        if not identifier:
            return Response({"error": "Product identifier required"}, status=status.HTTP_400_BAD_REQUEST)

        product = _get_product_by_identifier(identifier)
        if not product:
            return Response({"detail": "No Product matches the given query."}, status=status.HTTP_404_NOT_FOUND)

        try:
            quantity = int(request.data.get("quantity", 1))
        except (ValueError, TypeError):
            return Response({"error": "Quantity must be a number"}, status=status.HTTP_400_BAD_REQUEST)

        item, created = SmartListItem.objects.get_or_create(smartlist=smartlist, product=product)
        item.quantity = item.quantity + quantity if not created else quantity
        item.save()

        serializer = SmartListItemSerializer(item, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class SmartListUpdateItemAPIView(APIView):
    """
    POST /api/orders/smartlists/<pk>/update_item/
    payload: { item_id: <id>, quantity: n }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        smartlist = get_object_or_404(SmartList, id=pk, user=request.user)
        item_id = request.data.get("item_id")

        if not item_id:
            return Response({"error": "item_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        item = get_object_or_404(SmartListItem, id=item_id, smartlist=smartlist)

        try:
            quantity = int(request.data.get("quantity", item.quantity))
        except (ValueError, TypeError):
            return Response({"error": "Quantity must be a number"}, status=status.HTTP_400_BAD_REQUEST)

        item.quantity = quantity
        item.save()

        serializer = SmartListItemSerializer(item, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class SmartListRemoveItemAPIView(APIView):
    """
    POST /api/orders/smartlists/<pk>/remove_item/
    payload: { item_id: <id> }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        smartlist = get_object_or_404(SmartList, id=pk, user=request.user)
        item_id = request.data.get("item_id")

        if not item_id:
            return Response({"error": "item_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        item = get_object_or_404(SmartListItem, id=item_id, smartlist=smartlist)
        item.delete()
        return Response({"message": "Item removed successfully"}, status=status.HTTP_200_OK)


class SmartListOrderAllAPIView(APIView):
    """
    POST /api/orders/smartlists/<int:pk>/order_all/
    Converts all SmartList items into an Order and clears the SmartList.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        smartlist = get_object_or_404(SmartList, id=pk, user=user)

        items = list(smartlist.items.select_related("product"))
        if not items:
            return Response({"error": "Smart list is empty."}, status=status.HTTP_400_BAD_REQUEST)

        total = sum((item.product.price or 0) * item.quantity for item in items)

        order = Order.objects.create(
            user=user,
            total=total,
            source="smartlist",
            progress=1,
            status="pending",
        )

        for item in items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price=item.product.price,
            )

        smartlist.items.all().delete()

        serializer = OrderSerializer(order, context={"request": request})
        return Response(
            {
                "message": f"All items from '{smartlist.name}' have been ordered successfully.",
                "order": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )



# ---------------- SUMMARY ---------------- #
class OrderSummaryView(APIView):
    """
    GET /api/orders/summary/  -> { total_orders, total_spent }
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        orders = Order.objects.filter(user=request.user)
        total_orders = orders.count()
        total_spent = sum(order.total for order in orders)
        return Response({"total_orders": total_orders, "total_spent": total_spent})



from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.core.mail import send_mail
from django.conf import settings
from .serializers import SupportMessageSerializer


@api_view(['POST'])
def support_message(request):
    serializer = SupportMessageSerializer(data=request.data)
    if serializer.is_valid():
        # ✅ Save to DB first
        serializer.save()

        name = serializer.validated_data['name']
        email = serializer.validated_data['email']
        subject = serializer.validated_data['subject']
        message = serializer.validated_data['message']

        full_message = f"""
        From: {name} <{email}>
        Subject: {subject}

        {message}
        """

        # ✅ Try to send email, but don’t block or fail if it doesn’t work
        try:
            send_mail(
                subject=f"New Support Message from {name}",
                message=full_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=['chiamoorder@gmail.com'],
                fail_silently=True,  # 👈 this ensures no exception is raised
            )
        except Exception as e:
            # 👇 log the error but still return success
            print(f"[Email Error] Support message saved, but email failed: {e}")

        # ✅ Always return success if saved successfully
        return Response(
            {'message': 'Message received successfully! Our team will reach out soon.'},
            status=status.HTTP_201_CREATED
        )

    # ❌ Invalid form
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# orders/views.py

from .models import Notification

def create_order_notification(user, order, event):
    messages = {
        "placed": f"Your order #{order.id} has been placed successfully.",
        "shipped": f"Good news! Order #{order.id} is on the way.",
        "delivered": f"Your order #{order.id} has been delivered successfully.",
    }
    
    Notification.objects.create(
        user=user,
        title="Order Update",
        message=messages.get(event, "Order update"),
        type="order"
    )

# orders/views.py
from rest_framework import generics, permissions
from .models import Notification
from .serializers import NotificationSerializer

class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # show only this user's notifications, newest first
        return Notification.objects.filter(user=self.request.user).order_by("-created_at")

# orders/views.py
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes

@api_view(["PATCH"])
@permission_classes([permissions.IsAuthenticated])
def mark_notification_read(request, pk):
    try:
        notif = Notification.objects.get(pk=pk, user=request.user)
        notif.is_read = True
        notif.save()
        return Response({"detail": "Marked as read"})
    except Notification.DoesNotExist:
        return Response({"detail": "Not found"}, status=404)
