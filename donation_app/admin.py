from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.db.models import Sum, Count
from django.urls import reverse
from .models import Donation, DonationCategory, Membership, UserProfile

@admin.register(DonationCategory)
class DonationCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'total_donations', 'donation_count')
    search_fields = ('name',)
    
    def total_donations(self, obj):
        total = Donation.objects.filter(category=obj, status='completed').aggregate(Sum('amount'))['amount__sum']
        return f"₹{total or 0:,}"
    total_donations.short_description = "Total Amount"
    
    def donation_count(self, obj):
        return Donation.objects.filter(category=obj).count()
    donation_count.short_description = "Number of Donations"

@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ('name', 'formatted_amount', 'category', 'payment_method', 'status_badge', 'transaction_id', 'date', 'amount_modified_badge', 'admin_actions')
    list_filter = ('status', 'payment_method', 'category', 'date', 'is_amount_modified')
    search_fields = ('name', 'email', 'contact', 'transaction_id')
    readonly_fields = ('date', 'original_amount', 'is_amount_modified', 'verification_info')
    actions = ['verify_donations', 'mark_as_pending']
    fieldsets = (
        ('Donor Information', {
            'fields': ('user', 'name', 'email', 'contact')
        }),
        ('Donation Details', {
            'fields': ('amount', 'category', 'frequency', 'message', 'payment_method', 'transaction_id')
        }),
        ('Verification', {
            'fields': ('status', 'verification_info', 'original_amount', 'is_amount_modified')
        })
    )
    
    def formatted_amount(self, obj):
        if obj.is_amount_modified and obj.original_amount:
            return format_html(
                '<span style="text-decoration: line-through; color: #999;">₹{}</span> <strong>₹{}</strong>',
                obj.original_amount,
                obj.amount
            )
        return f"₹{obj.amount}"
    formatted_amount.short_description = "Amount"
    
    def amount_modified_badge(self, obj):
        if obj.is_amount_modified:
            return format_html('<span style="background-color: #ffc107; padding: 3px 8px; border-radius: 10px; color: #000;">Modified</span>')
        return ""
    amount_modified_badge.short_description = "Modified"
    
    def status_badge(self, obj):
        colors = {
            'completed': '#28a745',
            'pending': '#ffc107',
            'failed': '#dc3545',
            'refunded': '#6c757d'
        }
        return format_html(
            '<span style="background-color: {}; padding: 3px 8px; border-radius: 10px; color: white;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.get_status_display()
        )
    status_badge.short_description = "Status"
    
    def verification_info(self, obj):
        if obj.verified_by and obj.verification_date:
            return format_html(
                'Verified by: {} on {}',
                obj.verified_by.username,
                obj.verification_date.strftime('%Y-%m-%d %H:%M:%S')
            )
        return "Not verified yet"
    verification_info.short_description = "Verification Information"
    
    def admin_actions(self, obj):
        if obj.status == 'pending':
            return format_html(
                '<a class="button" href="{}?action=verify&id={}">Verify</a>',
                reverse('admin:index'),
                obj.id
            )
        elif obj.status == 'completed':
            return format_html(
                '<a class="button" href="{}?action=unverify&id={}">Mark Pending</a>',
                reverse('admin:index'),
                obj.id
            )
        return ""
    admin_actions.short_description = "Actions"
    
    def verify_donations(self, request, queryset):
        updated = queryset.update(
            status='completed',
            verified_by=request.user,
            verification_date=timezone.now()
        )
        self.message_user(request, f"{updated} donations were successfully verified.")
    verify_donations.short_description = "Mark selected donations as verified"
    
    def mark_as_pending(self, request, queryset):
        updated = queryset.update(
            status='pending',
            verified_by=None,
            verification_date=None
        )
        self.message_user(request, f"{updated} donations were marked as pending.")
    mark_as_pending.short_description = "Mark selected donations as pending"
    
    def save_model(self, request, obj, form, change):
        # If this is an existing donation and amount is changing
        if change and 'amount' in form.changed_data:
            # If this is the first change to amount, store original
            if obj.original_amount is None:
                # Get the original object before changes
                original_obj = self.model.objects.get(pk=obj.pk)
                obj.original_amount = original_obj.amount
                obj.is_amount_modified = True
        
        # If status is being changed to completed, set verification info
        if 'status' in form.changed_data and obj.status == 'completed':
            obj.verified_by = request.user
            obj.verification_date = timezone.now()
        
        super().save_model(request, obj, form, change)

@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'membership_type', 'amount_paid', 'start_date', 'expiry_date', 'is_active')
    list_filter = ('membership_type', 'is_active', 'start_date')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('start_date',)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'contact', 'total_donations', 'donation_count', 'is_life_member')
    search_fields = ('user__username', 'user__email', 'contact')
    list_filter = ('user__membership__is_active',)
    
    def total_donations(self, obj):
        total = obj.total_donations()
        return f"₹{total:,}" if total else "₹0"
    total_donations.short_description = "Total Donations (₹)"
    
    def donation_count(self, obj):
        return obj.donation_count()
    donation_count.short_description = "Number of Donations"
    
    def is_life_member(self, obj):
        return Membership.objects.filter(user=obj.user, is_active=True, membership_type='lifetime').exists()
    is_life_member.boolean = True
    is_life_member.short_description = "Life Member"

# Customize admin site
admin.site.site_header = "Donation Platform Administration"
admin.site.site_title = "Donation Admin Portal"
admin.site.index_title = "Welcome to Donation Platform Admin"
