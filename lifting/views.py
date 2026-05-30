import csv
from django.shortcuts import render, redirect, get_object_or_404 
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from datetime import date, datetime
from .models import LifterProfile, WorkoutSession, WorkoutSet, WorkoutTemplate, WorkoutTemplateExercise
from django.db.models import Sum, F, Max
from django.db.models.functions import TruncWeek
from django.views.decorators.http import require_POST
import json

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

    # Auto-seed standard templates if they don't exist yet
    # 1. Powerlifting Big Three
    if not WorkoutTemplate.objects.filter(user=request.user, name="Powerlifting Big Three").exists():
        t1 = WorkoutTemplate.objects.create(user=request.user, name="Powerlifting Big Three", description="Squat, Bench, and Deadlift target weights.")
        WorkoutTemplateExercise.objects.create(template=t1, exercise="SQUAT", weight=working_weights['squat'], reps=5, set_type="working", order=0)
        WorkoutTemplateExercise.objects.create(template=t1, exercise="BENCH", weight=working_weights['bench'], reps=5, set_type="working", order=1)
        WorkoutTemplateExercise.objects.create(template=t1, exercise="DEADLIFT", weight=working_weights['deadlift'], reps=5, set_type="working", order=2)
        
    # 2. Squat Focus (3x5)
    if not WorkoutTemplate.objects.filter(user=request.user, name="Squat Focus (3x5)").exists():
        t2 = WorkoutTemplate.objects.create(user=request.user, name="Squat Focus (3x5)", description="Triple working sets for leg development.")
        for i in range(3):
            WorkoutTemplateExercise.objects.create(template=t2, exercise="SQUAT", weight=working_weights['squat'], reps=5, set_type="working", order=i)
            
    # 3. Bench Press Volume (3x5)
    if not WorkoutTemplate.objects.filter(user=request.user, name="Bench Press Volume (3x5)").exists():
        t3 = WorkoutTemplate.objects.create(user=request.user, name="Bench Press Volume (3x5)", description="Triple working sets for upper body pushing power.")
        for i in range(3):
            WorkoutTemplateExercise.objects.create(template=t3, exercise="BENCH", weight=working_weights['bench'], reps=5, set_type="working", order=i)

    # 4. Wendler 5/3/1 (5s Week)
    if not WorkoutTemplate.objects.filter(user=request.user, name="Wendler 5/3/1 (5s Week)").exists():
        t4 = WorkoutTemplate.objects.create(user=request.user, name="Wendler 5/3/1 (5s Week)", description="Legendary long-term strength progression cycle at 65%, 75%, and 85%.")
        sq_1rm = profile.squat_1rm
        bp_1rm = profile.bench_1rm
        # Squat sets
        WorkoutTemplateExercise.objects.create(template=t4, exercise="SQUAT", weight=round((sq_1rm * 0.65) / 5) * 5, reps=5, set_type="working", order=0)
        WorkoutTemplateExercise.objects.create(template=t4, exercise="SQUAT", weight=round((sq_1rm * 0.75) / 5) * 5, reps=5, set_type="working", order=1)
        WorkoutTemplateExercise.objects.create(template=t4, exercise="SQUAT", weight=round((sq_1rm * 0.85) / 5) * 5, reps=5, set_type="working", order=2)
        # Bench sets
        WorkoutTemplateExercise.objects.create(template=t4, exercise="BENCH", weight=round((bp_1rm * 0.65) / 5) * 5, reps=5, set_type="working", order=3)
        WorkoutTemplateExercise.objects.create(template=t4, exercise="BENCH", weight=round((bp_1rm * 0.75) / 5) * 5, reps=5, set_type="working", order=4)
        WorkoutTemplateExercise.objects.create(template=t4, exercise="BENCH", weight=round((bp_1rm * 0.85) / 5) * 5, reps=5, set_type="working", order=5)

    # 5. Texas Method (Volume Day)
    if not WorkoutTemplate.objects.filter(user=request.user, name="Texas Method Volume Day").exists():
        t5 = WorkoutTemplate.objects.create(user=request.user, name="Texas Method Volume Day", description="Intermediate weekly progression volume: 5x5 Squat and Bench @ 75%.")
        sq_1rm = profile.squat_1rm
        bp_1rm = profile.bench_1rm
        w75_sq = round((sq_1rm * 0.75) / 5) * 5
        w75_bp = round((bp_1rm * 0.75) / 5) * 5
        for i in range(5):
            WorkoutTemplateExercise.objects.create(template=t5, exercise="SQUAT", weight=w75_sq, reps=5, set_type="working", order=i)
        for i in range(5):
            WorkoutTemplateExercise.objects.create(template=t5, exercise="BENCH", weight=w75_bp, reps=5, set_type="working", order=i + 5)

    # 6. Smolov Jr. (6x6 Squat)
    if not WorkoutTemplate.objects.filter(user=request.user, name="Smolov Jr. (6x6 Squat)").exists():
        t6 = WorkoutTemplate.objects.create(user=request.user, name="Smolov Jr. (6x6 Squat)", description="High-intensity, high-volume squat acclimation day: 6x6 @ 70% 1RM.")
        sq_1rm = profile.squat_1rm
        w70_sq = round((sq_1rm * 0.70) / 5) * 5
        for i in range(6):
            WorkoutTemplateExercise.objects.create(template=t6, exercise="SQUAT", weight=w70_sq, reps=6, set_type="working", order=i)

    # 7. Deload and Recovery
    if not WorkoutTemplate.objects.filter(user=request.user, name="Deload & Active Recovery").exists():
        t7 = WorkoutTemplate.objects.create(user=request.user, name="Deload & Active Recovery", description="Fatigue management cycle using light active recovery sets at 50% 1RM.")
        sq_1rm = profile.squat_1rm
        bp_1rm = profile.bench_1rm
        dl_1rm = profile.deadlift_1rm
        WorkoutTemplateExercise.objects.create(template=t7, exercise="SQUAT", weight=round((sq_1rm * 0.50) / 5) * 5, reps=5, set_type="working", order=0)
        WorkoutTemplateExercise.objects.create(template=t7, exercise="BENCH", weight=round((bp_1rm * 0.50) / 5) * 5, reps=5, set_type="working", order=1)
        WorkoutTemplateExercise.objects.create(template=t7, exercise="DEADLIFT", weight=round((dl_1rm * 0.50) / 5) * 5, reps=5, set_type="working", order=2)

    templates = WorkoutTemplate.objects.filter(user=request.user)

    # Fetch today's sets and order them newest-first to match your HTMX layout
    todays_sets = WorkoutSet.objects.filter(
        session__user=request.user, 
        session__date=date.today()
    ).order_by('-id')

    context = {
        'profile': profile, 
        'weights': working_weights, 
        'current_p': int(p_val),
        'todays_sets': todays_sets,
        'templates': templates,
        'today': date.today(),
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
            rpe_val = request.POST.get('rpe')
            rpe = float(rpe_val) if rpe_val else None
            if weight < 0 or reps <= 0 or reps > 100 or (rpe is not None and (rpe < 1.0 or rpe > 10.0)):
                return HttpResponse("Invalid numbers.", status=400)
        except (TypeError, ValueError):
            return HttpResponse("Invalid numbers.", status=400)
        session, created = WorkoutSession.objects.get_or_create(user=request.user, date=date.today())
        new_set = WorkoutSet.objects.create(session=session, exercise=exercise, weight=weight, reps=reps, completed=True, set_type=set_type, rpe=rpe)
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
            
            bw_val = request.POST.get("body_weight")
            if bw_val:
                profile.body_weight = float(bw_val)
                
            gender_val = request.POST.get("gender")
            if gender_val:
                profile.gender = gender_val
                
            formula_val = request.POST.get("formula_preference")
            if formula_val:
                profile.formula_preference = formula_val
                
            profile.show_rest_timer = request.POST.get("show_rest_timer") == "on"
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
@require_POST
def import_data(request):
    csv_file = request.FILES.get('csv_file')
    if not csv_file:
        return redirect('history')
        
    if not csv_file.name.endswith('.csv'):
        return HttpResponse("Please upload a valid CSV file.", status=400)
        
    decoded_file = csv_file.read().decode('utf-8').splitlines()
    reader = csv.reader(decoded_file)
    
    try:
        header = next(reader)
    except StopIteration:
        return HttpResponse("CSV file is empty.", status=400)
        
    header_lower = [h.strip().lower() for h in header]
    
    date_idx = -1
    exercise_idx = -1
    weight_idx = -1
    reps_idx = -1
    set_type_idx = -1
    rpe_idx = -1
    
    for i, col in enumerate(header_lower):
        if 'date' in col:
            date_idx = i
        elif 'exercise' in col:
            exercise_idx = i
        elif 'weight' in col:
            weight_idx = i
        elif 'rep' in col:
            reps_idx = i
        elif 'type' in col:
            set_type_idx = i
        elif 'rpe' in col:
            rpe_idx = i

    if date_idx == -1:
        date_idx = 0
    if exercise_idx == -1:
        exercise_idx = 2 if len(header_lower) > 2 and 'week' in header_lower[1] else 1
    if weight_idx == -1:
        weight_idx = 3 if len(header_lower) > 3 and 'week' in header_lower[1] else 2
    if reps_idx == -1:
        reps_idx = 4 if len(header_lower) > 4 and 'week' in header_lower[1] else 3
    if set_type_idx == -1:
        set_type_idx = 7 if len(header_lower) > 7 and 'week' in header_lower[1] else -1

    for row in reader:
        if not row or len(row) <= max(date_idx, exercise_idx, weight_idx, reps_idx):
            continue
            
        date_str = row[date_idx].strip()
        ex_str = row[exercise_idx].strip().upper()
        weight_str = row[weight_idx].strip()
        reps_str = row[reps_idx].strip()
        
        if not date_str or not ex_str or not weight_str or not reps_str:
            continue
            
        parsed_date = None
        for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d'):
            try:
                parsed_date = datetime.strptime(date_str, fmt).date()
                break
            except ValueError:
                continue
                
        if not parsed_date:
            continue
            
        exercise = None
        if 'SQUAT' in ex_str:
            exercise = 'SQUAT'
        elif 'BENCH' in ex_str:
            exercise = 'BENCH'
        elif 'DEADLIFT' in ex_str:
            exercise = 'DEADLIFT'
            
        if not exercise:
            continue
            
        try:
            weight = int(float(weight_str))
            reps = int(float(reps_str))
        except ValueError:
            continue
            
        set_type = 'working'
        if set_type_idx != -1 and set_type_idx < len(row):
            st_str = row[set_type_idx].strip().lower()
            if 'warm' in st_str:
                set_type = 'warmup'
            elif 'fail' in st_str:
                set_type = 'failure'
            else:
                set_type = 'working'
                
        rpe = None
        if rpe_idx != -1 and rpe_idx < len(row):
            rpe_str = row[rpe_idx].strip()
            if rpe_str:
                try:
                    rpe = float(rpe_str)
                except ValueError:
                    pass
                    
        session, created = WorkoutSession.objects.get_or_create(
            user=request.user,
            date=parsed_date
        )
        
        WorkoutSet.objects.create(
            session=session,
            exercise=exercise,
            weight=weight,
            reps=reps,
            set_type=set_type,
            rpe=rpe
        )
        
    return redirect('history')

@login_required
def history(request):
    sessions = WorkoutSession.objects.filter(user=request.user).prefetch_related('sets').order_by('-date')
    
    # e1RM Progression Chart Data
    user_sets = WorkoutSet.objects.filter(session__user=request.user).exclude(set_type='warmup')
    e1rm_raw = user_sets.filter(e1rm__isnull=False).values('session__date', 'exercise') \
                        .annotate(max_e1rm=Max('e1rm')) \
                        .order_by('session__date')

    dates_set = sorted(list(set(entry['session__date'] for entry in e1rm_raw if entry['session__date'])))
    dates_str = [d.strftime('%Y-%m-%d') for d in dates_set]

    squat_data = [None] * len(dates_set)
    bench_data = [None] * len(dates_set)
    deadlift_data = [None] * len(dates_set)

    date_to_idx = {d: i for i, d in enumerate(dates_set)}

    for entry in e1rm_raw:
        d = entry['session__date']
        if not d:
            continue
        idx = date_to_idx[d]
        ex_key = entry['exercise'].upper()
        if 'BENCH' in ex_key:
            ex_key = 'BENCH'
        
        val = entry['max_e1rm']
        if ex_key == 'SQUAT':
            squat_data[idx] = val
        elif ex_key == 'BENCH':
            bench_data[idx] = val
        elif ex_key == 'DEADLIFT':
            deadlift_data[idx] = val

    e1rm_chart_data = {
        'labels': dates_str,
        'squat': squat_data,
        'bench': bench_data,
        'deadlift': deadlift_data,
    }

    context = {
        'sessions': sessions,
        'e1rm_chart_data_json': json.dumps(e1rm_chart_data),
        'show_chart': len(dates_set) > 0,
    }
    return render(request, 'lifting/history.html', context)

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
        'profile': request.user.lifterprofile,
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

@login_required
@require_POST
def update_set_type(request, set_id):
    workout_set = get_object_or_404(WorkoutSet, id=set_id, session__user=request.user)
    new_type = request.POST.get('set_type')
    if new_type in ['working', 'warmup', 'failure']:
        workout_set.set_type = new_type
        workout_set.save()
    
    page = request.GET.get('page', 'dashboard')
    if page == 'history':
        return render(request, 'lifting/partials/history_set_row.html', {'set': workout_set})
    else:
        return render(request, 'lifting/partials/set_row.html', {'set': workout_set})

@login_required
@require_POST
def load_template(request):
    template_id = request.POST.get('template_id')
    if not template_id:
        return redirect('dashboard')
    try:
        template = WorkoutTemplate.objects.get(id=template_id, user=request.user)
    except WorkoutTemplate.DoesNotExist:
        return HttpResponse("Template not found", status=404)
    
    session, created = WorkoutSession.objects.get_or_create(user=request.user, date=date.today())
    for te in template.exercises.all():
        WorkoutSet.objects.create(
            session=session,
            exercise=te.exercise,
            weight=te.weight,
            reps=te.reps,
            set_type=te.set_type,
            completed=True
        )
    return redirect('dashboard')

@login_required
@require_POST
def save_template(request):
    template_name = request.POST.get('template_name', '').strip()
    if not template_name:
        template_name = f"Routine {date.today().strftime('%Y-%m-%d')}"
    
    todays_sets = WorkoutSet.objects.filter(
        session__user=request.user,
        session__date=date.today()
    ).order_by('id')
    
    if not todays_sets.exists():
        return HttpResponse("No sets to save.", status=400)
        
    template = WorkoutTemplate.objects.create(user=request.user, name=template_name)
    for i, s in enumerate(todays_sets):
        WorkoutTemplateExercise.objects.create(
            template=template,
            exercise=s.exercise,
            weight=s.weight,
            reps=s.reps,
            set_type=s.set_type,
            order=i
        )
    return redirect('dashboard')

@login_required
@require_POST
def delete_template(request):
    template_id = request.POST.get('template_id')
    try:
        template = WorkoutTemplate.objects.get(id=template_id, user=request.user)
        template.delete()
    except WorkoutTemplate.DoesNotExist:
        pass
    return redirect('dashboard')
