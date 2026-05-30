from django.contrib.auth.models import User
from django.test import TestCase
from datetime import date
from lifting.models import WorkoutSession, WorkoutSet

class DatabaseModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='model_user', password='password123')
        self.session = WorkoutSession.objects.create(user=self.user, date=date.today())
        self.workout_set = WorkoutSet.objects.create(
            session=self.session, 
            exercise='SQUAT', 
            weight=315, 
            reps=5, 
            set_type='working'
        )

    def test_workout_set_string_representation(self):
        """Happy Path: Verifies the __str__ method returns a clean, readable string."""
        expected_string = "SQUAT: 315x5 @ RPE None" 
        self.assertEqual(str(self.workout_set), expected_string)

    def test_workout_session_string_representation(self):
        """Happy Path: Verifies the WorkoutSession __str__ method."""
        expected_string = f"{self.user.username} - {date.today()}"
        self.assertEqual(str(self.session), expected_string)

    def test_get_tonnage_property(self):
        """Math Check: If you have a custom tonnage method on the model, test it here."""
        pass


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
