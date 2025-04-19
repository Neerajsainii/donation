from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.db.models import Sum, Q
from django.db import models
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import razorpay
import json
from .models import Donation, DonationCategory, Membership, UserProfile
from .forms import DonationForm, UserRegisterForm, UserLoginForm, ProfileUpdateForm, UserUpdateForm, MembershipForm
from django.contrib import messages

def leaderboard(request):
    """View to display the donation leaderboard."""
    # Get filter parameter from request
    donation_type = request.GET.get('type', None)
    
    # Base query - only include verified donations
    donations = Donation.objects.filter(status='completed')
    
    # Apply filter if provided
    if donation_type:
        donations = donations.filter(category__name=donation_type)
    
    # Group donations by user and sum the amounts
    user_donations = {}
    
    for donation in donations:
        key = donation.user.username if donation.user else donation.name
        if key in user_donations:
            user_donations[key] += donation.amount
        else:
            user_donations[key] = donation.amount
    
    # Sort by amount (descending)
    sorted_donations = sorted(user_donations.items(), key=lambda x: x[1], reverse=True)
    
    # Prepare data for template with ranks
    ranked_donations = []
    for i, (name, amount) in enumerate(sorted_donations, 1):
        ranked_donations.append({
            'rank': i,
            'name': name,
            'amount': amount
        })
    
    # Get categories for filter dropdown
    categories = DonationCategory.objects.all()
    
    context = {
        'donations': ranked_donations,
        'categories': categories,
        'current_filter': donation_type
    }
    
    return render(request, 'leaderboard.html', context)


def initialize_razorpay_payment(request):
    if request.method == 'POST':
        try:
            # Initialize Razorpay client with your API keys
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            
            # Get payment details from POST data
            amount = int(float(request.POST.get('amount', '0')) * 100)  # Amount in paise
            currency = request.POST.get('currency', 'INR')
            name = request.POST.get('name', '')
            email = request.POST.get('email', '')
            contact = request.POST.get('contact', '')
            donation_type = request.POST.get('donationType', '')
            
            # Create order
            payment_data = {
                'amount': amount,
                'currency': currency,
                'receipt': f'donation-{donation_type}-{email}',
                'notes': {
                    'name': name,
                    'email': email,
                    'contact': contact,
                    'donation_type': donation_type
                }
            }
            
            # Create Razorpay Order
            order = client.order.create(data=payment_data)
            
            # Return order details to client
            return JsonResponse({
                'id': order['id'],
                'amount': amount,
                'currency': currency,
                'key': settings.RAZORPAY_KEY_ID
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


@csrf_exempt
def payment_callback(request):
    if request.method == 'POST':
        try:
            # Get payment details from POST
            payment_id = request.POST.get('razorpay_payment_id', '')
            order_id = request.POST.get('razorpay_order_id', '')
            signature = request.POST.get('razorpay_signature', '')
            
            # Initialize Razorpay client
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            
            # Verify signature
            params_dict = {
                'razorpay_payment_id': payment_id,
                'razorpay_order_id': order_id,
                'razorpay_signature': signature
            }
            
            # Verify the payment signature
            client.utility.verify_payment_signature(params_dict)
            
            # Get payment details from Razorpay
            payment = client.payment.fetch(payment_id)
            
            # Create donation record
            name = payment['notes'].get('name', '')
            email = payment['notes'].get('email', '')
            contact = payment['notes'].get('contact', '')
            donation_type = payment['notes'].get('donation_type', '')
            amount = float(payment['amount']) / 100  # Convert paise to rupees
            
            # Try to find the user by email
            user = None
            if email:
                try:
                    user = User.objects.get(email=email)
                except User.DoesNotExist:
                    pass
            
            # Try to find donation category
            category = None
            if donation_type:
                try:
                    category = DonationCategory.objects.get(name=donation_type)
                except DonationCategory.DoesNotExist:
                    # Create the category if it doesn't exist
                    category = DonationCategory.objects.create(
                        name=donation_type,
                        description=f"Donations for {donation_type}"
                    )
            
            # Create donation
            donation = Donation.objects.create(
                user=user,
                name=name,
                email=email,
                contact=contact,
                amount=amount,
                category=category,
                payment_method='razorpay',
                transaction_id=payment_id,
                status='completed'  # Automatically mark as completed since verified by Razorpay
            )
            
            # Store payment method in session for thank you page
            request.session['payment_method'] = 'razorpay'
            request.session['donation_id'] = donation.id
            
            return JsonResponse({'status': 'success', 'redirect_url': '/thank-you/'})
            
        except Exception as e:
            return JsonResponse({'status': 'failed', 'error': str(e)}, status=400)
    
    return JsonResponse({'status': 'failed', 'error': 'Invalid request'}, status=400)


def donate(request):
    if request.method == 'POST':
        form = DonationForm(request.POST)
        if form.is_valid():
            donation = form.save(commit=False)
            
            # If user is logged in, associate donation with user
            if request.user.is_authenticated:
                donation.user = request.user
            
            # Try to find donation category
            donation_type = request.POST.get('donationType')
            if donation_type:
                try:
                    category = DonationCategory.objects.get(name=donation_type)
                    donation.category = category
                except DonationCategory.DoesNotExist:
                    # Create the category if it doesn't exist
                    category = DonationCategory.objects.create(
                        name=donation_type,
                        description=f"Donations for {donation_type}"
                    )
                    donation.category = category
            
            # Set payment method
            payment_method = request.POST.get('payment_method', 'razorpay')
            donation.payment_method = payment_method
            
            # Mark all donations as pending for admin verification
            donation.status = 'pending'
            messages.success(
                request, 
                "Thank you for your donation! Your contribution has been received and will be verified by our administrators."
            )
            
            # Save transaction ID if present
            transaction_id = request.POST.get('transaction_id')
            if transaction_id:
                donation.transaction_id = transaction_id
                
            donation.save()
            
            # For AJAX requests, return a JSON response
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success', 'message': 'Donation received successfully'})
            
            # Store payment method in session for thank you page
            request.session['payment_method'] = payment_method
            
            return redirect('thank_you')  # Redirect to thank you page after donation
    else:
        form = DonationForm()
    
    # Get statistics for the donation page - Handle with try/except for initial setup
    try:
        total_donations = Donation.objects.count()
        total_amount = Donation.objects.all().aggregate(total=models.Sum('amount'))['total'] or 0
        categories = DonationCategory.objects.all()
    except Exception as e:
        # During initial setup, tables might not exist yet
        total_donations = 0
        total_amount = 0
        categories = []
    
    # Add Razorpay key to context
    razorpay_key = settings.RAZORPAY_KEY_ID
    
    context = {
        'form': form,
        'total_donations': total_donations,
        'total_amount': total_amount,
        'categories': categories,
        'razorpay_key': razorpay_key,
    }
    
    return render(request, 'donate.html', context)


def thank_you(request):
    """View to show a thank you page after successful donation."""
    # Create context with payment method if available
    context = {}
    
    # Get payment method from session if set
    if 'payment_method' in request.session:
        context['payment_method'] = request.session['payment_method']
        # Clear session data after using it
        del request.session['payment_method']
    
    return render(request, 'thank_you.html', context)


def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Try to find user by email
        try:
            user = User.objects.get(email=email)
            username = user.username
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                login(request, user)
                return redirect('dashboard')
            else:
                error_message = "Invalid credentials. Please try again."
        except User.DoesNotExist:
            error_message = "No account found with this email. Please register first."
        
        return render(request, 'login.html', {'error_message': error_message})
    
    return render(request, 'login.html')


def register_view(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        # Validate password match
        if password != confirm_password:
            return render(request, 'login.html', {'register_error': 'Passwords do not match.'})
        
        # Check if email already exists
        if User.objects.filter(email=email).exists():
            return render(request, 'login.html', {'register_error': 'Email already registered.'})
        
        # Create user account
        username = email.split('@')[0]  # Use part of email as username
        base_username = username
        counter = 1
        
        # Ensure username is unique
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
            
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        
        # Create user profile
        profile = UserProfile.objects.create(
            user=user,
            contact=phone
        )
        
        # Log the user in
        authenticated_user = authenticate(request, username=username, password=password)
        if authenticated_user is not None:
            login(request, authenticated_user)
            return redirect('dashboard')
            
    return redirect('login')


def logout_view(request):
    logout(request)
    return redirect('home')


@login_required
def dashboard(request):
    # Get user's donations
    user_donations = Donation.objects.filter(user=request.user).order_by('-date')
    
    # Get total donation amount
    total_amount = user_donations.aggregate(total=models.Sum('amount'))['total'] or 0
    donation_count = user_donations.count()
    
    # Get category-specific donations
    category_donations = {}
    categories = DonationCategory.objects.all()
    
    for category in categories:
        category_total = Donation.objects.filter(
            user=request.user, 
            category=category
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        category_donations[category.name] = category_total
    
    # Get user's rank in leaderboard
    # First, aggregate all donations by user
    user_totals = {}
    all_donations = Donation.objects.all()
    
    for donation in all_donations:
        if donation.user:
            if donation.user.id in user_totals:
                user_totals[donation.user.id] += donation.amount
            else:
                user_totals[donation.user.id] = donation.amount
    
    # Sort users by total donation amount
    sorted_users = sorted(user_totals.items(), key=lambda x: x[1], reverse=True)
    
    # Find current user's rank
    user_rank = 0
    for i, (user_id, amount) in enumerate(sorted_users):
        if user_id == request.user.id:
            user_rank = i + 1
            break
    
    # Check if user has a membership
    try:
        membership = Membership.objects.get(user=request.user)
    except Membership.DoesNotExist:
        membership = None
    
    context = {
        'user_donations': user_donations[:5],  # Show only the most recent 5 donations
        'total_amount': total_amount,
        'donation_count': donation_count,
        'category_donations': category_donations,
        'user_rank': user_rank,
        'membership': membership,
    }
    
    return render(request, 'dashboard.html', context)


@login_required
def profile(request):
    try:
        profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)
    
    if request.method == 'POST':
        # Update user profile
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        
        # Update user
        user = request.user
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.save()
        
        # Update profile
        profile.contact = phone
        profile.address = address
        
        # Handle profile picture upload
        if 'profile_pic' in request.FILES:
            profile.profile_pic = request.FILES['profile_pic']
        
        profile.save()
        
        return redirect('dashboard')
    
    return render(request, 'profile.html', {'profile': profile})


def life_member(request):
    return render(request, 'life_member.html')


def process_membership(request):
    if request.method == 'POST' and request.user.is_authenticated:
        membership_type = request.POST.get('membershipType')
        amount = request.POST.get('amount')
        
        # Create or update membership
        try:
            membership = Membership.objects.get(user=request.user)
            membership.membership_type = membership_type.lower()
            membership.amount_paid = amount
            membership.is_active = True
            membership.save()
        except Membership.DoesNotExist:
            membership = Membership.objects.create(
                user=request.user,
                membership_type=membership_type.lower(),
                amount_paid=amount,
                is_active=True
            )
        
        return redirect('thank_you')
    
    return redirect('life_member')


@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_dashboard(request):
    # Get total donations and amount
    total_donations = Donation.objects.filter(status='completed').count()
    total_amount = Donation.objects.filter(status='completed').aggregate(total=Sum('amount'))['total'] or 0
    
    # Get pending verifications
    pending_verifications = Donation.objects.filter(status='pending').count()
    
    # Get user statistics
    users_count = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    lifetime_members = Membership.objects.filter(membership_type='lifetime', is_active=True).count()
    
    # Get recent donations
    recent_donations = Donation.objects.select_related('category').order_by('-date')[:10]
    
    # Get life members
    life_members = Membership.objects.select_related('user', 'user__userprofile').filter(
        membership_type='lifetime', 
        is_active=True
    ).order_by('-start_date')[:10]
    
    # Get top donors
    top_donors = User.objects.annotate(
        total_donated=Sum('donation__amount', filter=Q(donation__status='completed'))
    ).exclude(total_donated=None).order_by('-total_donated')[:10]
    
    # Get recent users
    recent_users = User.objects.select_related('userprofile').order_by('-date_joined')[:10]
    
    context = {
        'total_donations': total_donations,
        'total_amount': total_amount,
        'pending_verifications': pending_verifications,
        'users_count': users_count,
        'active_users': active_users,
        'lifetime_members': lifetime_members,
        'recent_donations': recent_donations,
        'life_members': life_members,
        'top_donors': top_donors,
        'recent_users': recent_users,
    }
    
    return render(request, 'admin_dashboard.html', context)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def verify_donation(request, donation_id):
    donation = get_object_or_404(Donation, id=donation_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'verify':
            # Update amount if changed
            new_amount = request.POST.get('amount')
            if new_amount and float(new_amount) != donation.amount:
                donation.amount = float(new_amount)
            
            # Mark as completed
            donation.status = 'completed'
            donation.save()
            
            messages.success(request, 'Donation verified successfully!')
            return redirect('admin_dashboard')
            
        elif action == 'delete':
            donation.delete()
            messages.success(request, 'Donation deleted successfully!')
            return redirect('admin_dashboard')
    
    return redirect('admin_dashboard')

