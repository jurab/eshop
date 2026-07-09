from django.contrib import admin

from .models import Address, Coupon, Order, OrderItem, Payment


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'label', 'street', 'city', 'country')


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_type', 'value', 'is_active',
                    'valid_from', 'valid_to')
    list_filter = ('discount_type', 'is_active')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'product_name', 'price', 'quantity')
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'full_name', 'email', 'status', 'total', 'created_at')
    list_filter = ('status',)
    search_fields = ('email', 'full_name', 'id')
    readonly_fields = ('id', 'subtotal', 'discount_amount', 'total',
                       'created_at', 'updated_at')
    inlines = [OrderItemInline]
    actions = ['mark_shipped']

    @admin.action(description='Mark selected orders as shipped')
    def mark_shipped(self, request, queryset):
        updated = queryset.filter(status=Order.Status.PAID).update(
            status=Order.Status.SHIPPED)
        self.message_user(request, f'{updated} order(s) marked as shipped.')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('order', 'provider', 'transaction_id', 'amount', 'created_at')
    readonly_fields = ('order', 'provider', 'transaction_id', 'amount')
