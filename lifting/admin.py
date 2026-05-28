from django.contrib import admin
from .models import LifterProfile, WorkoutSession, WorkoutSet

admin.site.register(LifterProfile)
admin.site.register(WorkoutSession)
admin.site.register(WorkoutSet)

# Register your models here.
