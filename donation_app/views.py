from django.core.paginator import Paginator
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Sum
from django.db import models
from .models import Donation, DonationCategory, Membership, UserProfile
from .forms import DonationForm

def leaderboard(request):
    # Get ranking type from URL parameters
    ranking_type = request.GET.get('type', 'overall')
    
    if ranking_type == 'overall':
        # For overall ranking, we want to aggregate donations by user
        donations_by_user = {}
        all_donations = Donation.objects.all()
        
        for donation in all_donations:
            # Use name as identifier if no user is associated
            identifier = donation.user.username if donation.user else donation.name
            if identifier in donations_by_user:
                donations_by_user[identifier]['amount'] += donation.amount
            else:
                donations_by_user[identifier] = {
                    'name': donation.user.get_full_name() if donation.user else donation.name,
                    'amount': donation.amount
                }
        
        # Convert to list and sort by amount
        aggregated_donations = [
            {'name': data['name'], 'amount': data['amount']} 
            for identifier, data in donations_by_user.items()
        ]
        aggregated_donations.sort(key=lambda x: x['amount'], reverse=True)
        
        # Paginate the aggregated results
        page_number = request.GET.get('page', 1)
        paginator = Paginator(aggregated_donations, 10)  # Show 10 entries per page
        page_obj = paginator.get_page(page_number)
    
    else:
        # Filter by category for specific ranking types
        category_mapping = {
            'food': 'Food for Life',
            'prasadam': 'Prasadam Donation',
            'sudama': 'Sudama Seva',
            'ekadashi': 'Ekadashi Donation',
            'shravan': 'Shravan Kumar Seva',
            'gita': 'Bhagavad Gita'
        }
        
        category_name = category_mapping.get(ranking_type)
        if category_name:
            try:
                category = DonationCategory.objects.get(name=category_name)
                # Aggregate donations by user for this category
                donations_by_user = {}
                category_donations = Donation.objects.filter(category=category)
                
                for donation in category_donations:
                    identifier = donation.user.username if donation.user else donation.name
                    if identifier in donations_by_user:
                        donations_by_user[identifier]['amount'] += donation.amount
                    else:
                        donations_by_user[identifier] = {
                            'name': donation.user.get_full_name() if donation.user else donation.name,
                            'amount': donation.amount
                        }
                
                # Convert to list and sort by amount
                aggregated_donations = [
                    {'name': data['name'], 'amount': data['amount']} 
                    for identifier, data in donations_by_user.items()
                ]
                aggregated_donations.sort(key=lambda x: x['amount'], reverse=True)
                
                # Paginate the aggregated results
                page_number = request.GET.get('page', 1)
                paginator = Paginator(aggregated_donations, 10)  # Show 10 entries per page
                page_obj = paginator.get_page(page_number)
            except DonationCategory.DoesNotExist:
                # Fallback to overall if category doesn't exist
                return redirect('leaderboard')
        else:
            # Fallback to overall if invalid ranking type
            return redirect('leaderboard')

    return render(request, 'leaderboard.html', {
        'page_obj': page_obj,
        'ranking_type': ranking_type
    })


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
                    pass
            
            donation.save()
            
            # For AJAX requests, return a JSON response
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success', 'message': 'Donation received successfully'})
            
            return redirect('thank_you')  # Redirect to thank you page after donation
    else:
        form = DonationForm()
    
    # Get statistics for the donation page
    total_donations = Donation.objects.count()
    total_amount = Donation.objects.all().aggregate(total=models.Sum('amount'))['total'] or 0
    
    # Get donation categories
    categories = DonationCategory.objects.all()
    
    context = {
        'form': form,
        'total_donations': total_donations,
        'total_amount': total_amount,
        'categories': categories,
    }
    
    return render(request, 'donate.html', context)


def thank_you(request):
    """View to show a thank you page after successful donation."""
    return render(request, 'thank_you.html')


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

