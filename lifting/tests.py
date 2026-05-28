from django.test import TestCase
from django.contrib.auth.models import User
from .models import WorkoutSession, WorkoutSet

class WorkoutSetTests(TestCase):
    def setUp(self):
        # 1. Create a dummy user for authentication
        self.user = User.objects.create_user(username='testlifter', password='password123')
        
        # 2. Build a fake workout session tied to that user
        self.session = WorkoutSession.objects.create(user=self.user)
        
        # 3. Log a dummy set inside that session
        self.workout_set = WorkoutSet.objects.create(
            session=self.session, 
            exercise='SQUAT', 
            weight=225, 
            reps=5,
            set_type='working'
        )

    def test_secure_delete_workout_set(self):
        # Log the dummy user into the test client browser
        self.client.login(username='testlifter', password='password123')
        
        # Send a secure POST request to your view to delete the set
        response = self.client.post(f'/delete-set/{self.workout_set.id}/')
        
        # Verify the backend returns a successful empty response to HTMX
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "")
        
        # CONFIRMATION: Check the database to ensure the record is actually gone
        self.assertFalse(WorkoutSet.objects.filter(id=self.workout_set.id).exists())
