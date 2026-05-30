
# Create your models here.

from datetime import date
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class LifterProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    squat_1rm = models.IntegerField(default=0, help_text="Current Squat Max")
    bench_1rm = models.IntegerField(default=0, help_text="Current Bench Max")
    deadlift_1rm = models.IntegerField(default=0, help_text="Current Deadlift Max")
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
    e1rm = models.IntegerField(blank=True, null=True, help_text="Estimated 1RM calculated via Epley formula") # <-- New Field
    completed = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    set_type = models.CharField(max_length=10, choices=SET_TYPES, default='working')

    def save(self, *args, **kwargs):
        # Automatically calculate the e1RM before saving to the database
        if self.weight and self.reps:
            # Epley Formula
            calculated_max = self.weight * (1 + (self.reps / 30.0))
            self.e1rm = int(round(calculated_max))
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.exercise}: {self.weight}x{self.reps} @ RPE {self.rpe}"
