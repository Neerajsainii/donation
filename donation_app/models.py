from django.db import models
from django.contrib.auth.models import User

class DonationCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    
    def __str__(self):
        return self.name

class Donation(models.Model):
    DONATION_FREQUENCY = [
        ('one-time', 'One-time'),
        ('monthly', 'Monthly'),
        ('weekly', 'Weekly'),
        ('yearly', 'Yearly'),
    ]
    
    PAYMENT_METHODS = [
        ('razorpay', 'Razorpay'),
        ('upi', 'UPI'),
        ('netbanking', 'Net Banking'),
        ('card', 'Credit/Debit Card'),
        ('cash', 'Cash'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(null=True, blank=True)
    contact = models.CharField(max_length=20, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    frequency = models.CharField(max_length=20, choices=DONATION_FREQUENCY, default='one-time')
    category = models.ForeignKey(DonationCategory, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    transaction_id = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=20, default='completed')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='razorpay')
    message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} - {self.amount}"
    
    class Meta:
        ordering = ['-amount']

class Membership(models.Model):
    MEMBERSHIP_TYPES = [
        ('bronze', 'Bronze'),
        ('silver', 'Silver'),
        ('gold', 'Gold'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    membership_type = models.CharField(max_length=20, choices=MEMBERSHIP_TYPES)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    transaction_id = models.CharField(max_length=100, null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.get_membership_type_display()}"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    contact = models.CharField(max_length=20, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    profile_pic = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return self.user.username
    
    def total_donations(self):
        donations = Donation.objects.filter(user=self.user)
        return sum(donation.amount for donation in donations)
    
    def donation_count(self):
        return Donation.objects.filter(user=self.user).count()
    
    def get_category_donations(self, category_name):
        category = DonationCategory.objects.get(name=category_name)
        donations = Donation.objects.filter(user=self.user, category=category)
        return sum(donation.amount for donation in donations)
