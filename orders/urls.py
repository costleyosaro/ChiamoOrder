# orders/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import support_message, mark_notification_read
from .views import NotificationListView
from .views import (
    CartView,
    AddToCartView,
    RemoveFromCartView,
    UpdateCartItemView,
    ClearCartView,
    CheckoutView,
    OrderViewSet,
    SmartListListCreateAPIView,
    SmartListDetailAPIView,
    SmartListAddItemAPIView,
    SmartListUpdateItemAPIView,
    SmartListRemoveItemAPIView,
    SmartListOrderAllAPIView,
    OrderSummaryView,
)

# Router for regular Orders
router = DefaultRouter()
router.register(r"", OrderViewSet, basename="orders")

urlpatterns = [
    # -------------------------------
    # 🧺 CART ENDPOINTS
    # -------------------------------
    path("cart/", CartView.as_view(), name="cart"),
    path("cart/add/", AddToCartView.as_view(), name="add-to-cart"),
    path("cart/remove/", RemoveFromCartView.as_view(), name="remove-from-cart"),
    path("cart/update/", UpdateCartItemView.as_view(), name="cart-update"),
    path("cart/clear/", ClearCartView.as_view(), name="cart-clear"),
    path("checkout/", CheckoutView.as_view(), name="checkout"),

    # -------------------------------
    # 🧾 ORDER SUMMARY
    # -------------------------------
    path("summary/", OrderSummaryView.as_view(), name="order-summary"),

    # -------------------------------
    # 🧠 SMART LIST ENDPOINTS
    # -------------------------------
    # Create + list all smartlists
    path("smartlists/", SmartListListCreateAPIView.as_view(), name="smartlists-list-create"),

    # View / delete / update specific smartlist
    path("smartlists/<int:pk>/", SmartListDetailAPIView.as_view(), name="smartlists-detail"),

    # Add, update, remove items
    path("smartlists/<int:pk>/add_item/", SmartListAddItemAPIView.as_view(), name="smartlists-add-item"),
    path("smartlists/<int:pk>/update_item/", SmartListUpdateItemAPIView.as_view(), name="smartlists-update-item"),
    path("smartlists/<int:pk>/remove_item/", SmartListRemoveItemAPIView.as_view(), name="smartlists-remove-item"),

    # Order all items in the smartlist
    path("smartlists/<int:pk>/order_all/", SmartListOrderAllAPIView.as_view(), name="smartlists-order-all"),

    # -------------------------------
    # 🧾 REGULAR ORDER ROUTES (router)
    # -------------------------------
    path("user-orders/", include(router.urls)),
    path('support/messages/', support_message, name='support_message'),
    path("notifications/", NotificationListView.as_view(), name="notifications"),
    path("notifications/<int:pk>/mark_read/", mark_notification_read, name="mark_notification_read"),

]
print("SMARTLIST URLS LOADED")
