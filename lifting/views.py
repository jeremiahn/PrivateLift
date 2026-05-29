import csv
from django.shortcuts import render, redirect, get_object_or_404 
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from datetime import date
from .models import LifterProfile, WorkoutSession, WorkoutSet
from django.db.models import Sum, F
from django.db.models.functions import TruncWeek
from django.views.decorators.http import require_POST

@login_required
def dashboard(request):
    profile = request.user.lifterprofile
    try:
        p_val = float(request.GET.get('p', 85))
        percentage = p_val / 100.0
    except ValueError:
        percentage = 0.85
        p_val = 85
    working_weights = profile.get_weekly_program(percentage)

    # Fetch today's sets and order them newest-first to match your HTMX layout
    todays_sets = WorkoutSet.objects.filter(
        session__user=request.user, 
        session__date=date.today()
    ).order_by('-id')

    context = {
        'profile': profile, 
        'weights': working_weights, 
        'current_p': int(p_val),
        'todays_sets': todays_sets
    }
    return render(request, 'lifting/dashboard.html', context)

@login_required
def log_set(request):
    if request.method == "POST":
        exercise = request.POST.get("exercise")
        try:
            weight = int(request.POST.get("weight"))
            reps = int(request.POST.get("reps"))
            set_type = request.POST.get('set_type', 'working')
            if weight < 0 or reps <= 0 or reps > 100:
                return HttpResponse("Invalid numbers.", status=400)
        except (TypeError, ValueError):
            return HttpResponse("Invalid numbers.", status=400)
        session, created = WorkoutSession.objects.get_or_create(user=request.user, date=date.today())
        new_set = WorkoutSet.objects.create(session=session, exercise=exercise, weight=weight, reps=reps, completed=True, set_type=set_type)
        response = render(request, 'lifting/partials/set_row.html', {'set': new_set})
        response['HX-Trigger'] = 'setLogged'
        return response
    return HttpResponse("Invalid request", status=400)

@login_required
def profile_settings(request):
    profile = request.user.lifterprofile
    if request.method == "POST":
        try:
            profile.squat_1rm = int(request.POST.get("squat"))
            profile.bench_1rm = int(request.POST.get("bench"))
            profile.deadlift_1rm = int(request.POST.get("deadlift"))
            profile.save()
            return redirect('dashboard')
        except (TypeError, ValueError):
            return HttpResponse("Invalid numbers provided.", status=400)
    return render(request, 'lifting/profile.html', {'profile': profile})

@login_required
def export_data(request):
    response = HttpResponse(
        content_type='text/csv',
        headers={'Content-Disposition': 'attachment; filename="my_lifting_history.csv"'},
    )
    writer = csv.writer(response)
    
    # 1. Added columns for 'Set Tonnage' and 'Training Week Start'
    writer.writerow(['Date', 'Training Week Start', 'Exercise', 'Weight (lbs)', 'Reps', 'Set Tonnage (lbs)', 'Estimated 1RM', 'Set Type'])

    user_sets = WorkoutSet.objects.filter(session__user=request.user).order_by('-session__date')

    for s in user_sets:
        # Calculate single-set tonnage math for this specific row
        set_tonnage = s.weight * s.reps if s.weight and s.reps else 0
        
        # Calculate what calendar week this specific date fell into (Monday start)
        # .isocalendar() returns (year, week_number, weekday)
        year, week_num, _ = s.session.date.isocalendar()
        # Turn it back into the actual calendar date of that week's Monday
        week_start_date = date.fromisocalendar(year, week_num, 1)

        writer.writerow([
            s.session.date,
            week_start_date,            # Training Week Start Column
            s.exercise,
            s.weight,
            s.reps,
            set_tonnage,                # Set Tonnage Calculation Column
            s.e1rm,
            s.get_set_type_display()
        ])
    return response

@login_required
def history(request):
    sessions = WorkoutSession.objects.filter(user=request.user).prefetch_related('sets').order_by('-date')
    return render(request, 'lifting/history.html', {'sessions': sessions})

@login_required
def analytics(request):
    # 1. Grab all sets excluding warmups
    user_sets = WorkoutSet.objects.filter(session__user=request.user).exclude(set_type='warmup')

    # 2. Group by BOTH week and exercise, then sum BOTH tonnage and reps
    weekly_raw = user_sets.annotate(week=TruncWeek('session__date')) \
        .values('week', 'exercise') \
        .annotate(
            total_tonnage=Sum(F('weight') * F('reps')),
            total_reps=Sum('reps')  # <-- Added rep summation here!
        ) \
        .order_by('-week')

    # 3. Restructure the weekly data into a clean dictionary for the template
    weekly_breakdown = {}
    for entry in weekly_raw:
        week_date = entry['week']
        ex_key = entry['exercise'].upper()
        if 'BENCH' in ex_key:
            ex_key = 'BENCH'

        if week_date not in weekly_breakdown:
            weekly_breakdown[week_date] = {
                'SQUAT': {'tonnage': 0, 'reps': 0},
                'BENCH': {'tonnage': 0, 'reps': 0},
                'DEADLIFT': {'tonnage': 0, 'reps': 0}
            }
            
        if ex_key in weekly_breakdown[week_date]:
            weekly_breakdown[week_date][ex_key]['tonnage'] = entry['total_tonnage']
            weekly_breakdown[week_date][ex_key]['reps'] = entry['total_reps'] # <-- Storing reps

    # 4. Lifetime Totals logic remains exactly the same
    exercises = ['SQUAT', 'BENCH', 'DEADLIFT']
    tonnage = {ex: 0 for ex in exercises}
    lifetime_reps = {ex: 0 for ex in exercises}
    
    for workout_set in user_sets:
        exercise_key = workout_set.exercise.upper()
        if 'BENCH' in exercise_key:
            exercise_key = 'BENCH'
        if exercise_key in tonnage:
            tonnage[exercise_key] += (workout_set.weight * workout_set.reps)
            lifetime_reps[exercise_key] += workout_set.reps
            
    context = {
        'tonnage': tonnage, 
        'total_reps': lifetime_reps,
        'weekly_breakdown': weekly_breakdown,
    }
    return render(request, 'lifting/analytics.html', context)

@login_required
@require_POST
def delete_set(request, set_id):
    # Securely find the WorkoutSet by traversing through the session to verify the user
    workout_set = get_object_or_404(WorkoutSet, id=set_id, session__user=request.user)
    
    # Delete it
    workout_set.delete()
    
    # Return the empty response to trigger the HTMX removal
    return HttpResponse("")
