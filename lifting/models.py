
# Create your models here.

from datetime import date
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class LifterProfile(models.Model):
    FORMULA_CHOICES = [
        ('epley', 'Epley'),
        ('brzycki', 'Brzycki'),
        ('lander', 'Lander'),
    ]
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    squat_1rm = models.IntegerField(default=0, help_text="Current Squat Max")
    bench_1rm = models.IntegerField(default=0, help_text="Current Bench Max")
    deadlift_1rm = models.IntegerField(default=0, help_text="Current Deadlift Max")
    body_weight = models.DecimalField(max_digits=5, decimal_places=1, default=180.0, help_text="Current body weight in lbs")
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='male', help_text="Gender for relative strength scaling")
    formula_preference = models.CharField(max_length=15, choices=FORMULA_CHOICES, default='epley', help_text="Formula used to calculate estimated 1RM")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    def get_weekly_program(self, percentage):
        """
        Securely calculates working weight rounded to the nearest 5 lbs/kgs.
        Accepts percentage as a float (e.g., 0.85 for 85%).
        """
        if not (0 < percentage <= 1.20): # Basic validation input check
            raise ValueError("Percentage must be a realistic training value.")
            
        return {
            'squat': round((self.squat_1rm * percentage) / 5) * 5,
            'bench': round((self.bench_1rm * percentage) / 5) * 5,
            'deadlift': round((self.deadlift_1rm * percentage) / 5) * 5,
        }

    def get_dots_score(self):
        """
        Calculates the DOTS score (dynamic coefficient for relative strength).
        Converts inputs to metric for standards validation.
        """
        bw_kg = float(self.body_weight) * 0.45359237
        if bw_kg <= 0:
            return 0.0
            
        total_lbs = self.squat_1rm + self.bench_1rm + self.deadlift_1rm
        total_kg = total_lbs * 0.45359237
        
        if self.gender == 'female':
            a, b, c, d, e, f = -0.0000010706, 0.0005158568, -0.1126651949, 13.6175032917, -579.2435372556, 11924.4568600108
        else: # male
            a, b, c, d, e, f = -0.0000010930, 0.0007395750, -0.1918759221, 27.0160078105, -1047.8830338318, 16618.3314375043
            
        denom = a*(bw_kg**5) + b*(bw_kg**4) + c*(bw_kg**3) + d*(bw_kg**2) + e*bw_kg + f
        if denom == 0:
            return 0.0
        coeff = 500.0 / denom
        return round(total_kg * coeff, 2)

    def get_wilks_score(self):
        """
        Calculates the standard Wilks score (classic relative strength scaling).
        """
        bw_kg = float(self.body_weight) * 0.45359237
        if bw_kg <= 0:
            return 0.0
            
        total_lbs = self.squat_1rm + self.bench_1rm + self.deadlift_1rm
        total_kg = total_lbs * 0.45359237
        
        if self.gender == 'female':
            a, b, c, d, e, f = 594.3174777, -27.23842536, 0.8211222687, -0.00930733913, 0.00004731582, -0.00000009054
        else: # male
            a, b, c, d, e, f = -216.0475144, 16.2606339, -0.002388645, -0.00113732, 0.00000701863, -0.00000001291
            
        denom = a + b*bw_kg + c*(bw_kg**2) + d*(bw_kg**3) + e*(bw_kg**4) + f*(bw_kg**5)
        if denom == 0:
            return 0.0
        coeff = 500.0 / denom
        return round(total_kg * coeff, 2)

# --- UX Automation: Automatically create/manage profile when a user is saved ---
@receiver(post_save, sender=User)
def save_or_create_user_profile(sender, instance, created, **kwargs):
    if created:
        LifterProfile.objects.create(user=instance)
    else:
        try:
            instance.lifterprofile.save()
        except LifterProfile.DoesNotExist:
            LifterProfile.objects.create(user=instance)

class WorkoutSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(default=date.today)
    notes = models.TextField(blank=True, null=True, help_text="General session notes (e.g., 'Felt sluggish', 'Slept poor')")

    def __str__(self):
        return f"{self.user.username} - {self.date}"

class WorkoutSet(models.Model):
    EXERCISE_CHOICES = [
        ('SQUAT', 'Squat'),
        ('BENCH', 'Bench Press'),
        ('DEADLIFT', 'Deadlift'),
    ]
    SET_TYPES = (
        ('warmup', 'Warm Up'),
        ('working', 'Working'),
        ('failure', 'Failure'),
    )

    session = models.ForeignKey(WorkoutSession, on_delete=models.CASCADE, related_name='sets')
    exercise = models.CharField(max_length=20, choices=EXERCISE_CHOICES)
    weight = models.IntegerField(help_text="Weight in lbs")
    reps = models.IntegerField()
    rpe = models.DecimalField(max_digits=3, decimal_places=1, blank=True, null=True, help_text="Rate of Perceived Exertion (1-10)")
    e1rm = models.IntegerField(blank=True, null=True, help_text="Estimated 1RM calculated via preferred formula")
    completed = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    set_type = models.CharField(max_length=10, choices=SET_TYPES, default='working')

    def save(self, *args, **kwargs):
        # Automatically calculate the e1RM before saving using the user's formula preference
        if self.weight and self.reps:
            profile = getattr(self.session.user, 'lifterprofile', None)
            formula = profile.formula_preference if profile else 'epley'
            
            if formula == 'brzycki':
                if self.reps == 1:
                    calculated_max = self.weight
                else:
                    calculated_max = self.weight / (1.0278 - (0.0278 * self.reps))
            elif formula == 'lander':
                calculated_max = (100 * self.weight) / (101.3 - (2.6712 * self.reps))
            else: # epley standard
                calculated_max = self.weight * (1 + (self.reps / 30.0))
                
            self.e1rm = int(round(calculated_max))
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.exercise}: {self.weight}x{self.reps} @ RPE {self.rpe}"

class WorkoutTemplate(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100, help_text="Routine Name (e.g. 'Push Day A')")
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.user.username})"

class WorkoutTemplateExercise(models.Model):
    template = models.ForeignKey(WorkoutTemplate, on_delete=models.CASCADE, related_name='exercises')
    exercise = models.CharField(max_length=20, choices=WorkoutSet.EXERCISE_CHOICES)
    weight = models.IntegerField(help_text="Target weight in lbs")
    reps = models.IntegerField()
    set_type = models.CharField(max_length=10, choices=WorkoutSet.SET_TYPES, default='working')
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.template.name} - {self.exercise}: {self.weight}x{self.reps} ({self.set_type})"

