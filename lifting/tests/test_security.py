from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from datetime import date
from lifting.models import WorkoutSession

class BoundaryLimitTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='limit_user', password='password123')
        self.session = WorkoutSession.objects.create(user=self.user, date=date.today())

    def test_log_set_extreme_weight(self):
        """Boundary: User tries to log a 100,000 lb squat."""
        self.client.login(username='limit_user', password='password123')
        url = reverse('log_set')
        extreme_data = {
            'exercise': 'SQUAT',
            'weight': '100000',
            'reps': '5',
            'set_type': 'working'
        }
        self.client.post(url, data=extreme_data)
        pass

    def test_log_set_decimals_in_integer_field(self):
        """Boundary: User tries to submit a fraction when the DB expects an integer."""
        self.client.login(username='limit_user', password='password123')
        url = reverse('log_set')
        decimal_data = {
            'exercise': 'BENCH',
            'weight': '225.5',
            'reps': '5',
            'set_type': 'working'
        }
        response = self.client.post(url, data=decimal_data)
        self.assertEqual(response.status_code, 400)

    def test_profile_negative_1rm(self):
        """Boundary: User tries to save a negative 1-Rep Max."""
        self.client.login(username='limit_user', password='password123')
        url = reverse('profile_settings')
        negative_data = {
            'squat_1rm': '-500',
            'bench_1rm': '225',
            'deadlift_1rm': '405'
        }
        self.client.post(url, data=negative_data)
        pass


class GlobalSecurityTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_all_views_require_login(self):
        """Security: Ensures no primary views are accidentally left public."""
        urls_to_protect = [
            reverse('dashboard'),
            reverse('analytics'),
            reverse('profile_settings'),
            reverse('export_data'),
            reverse('import_data'),
            reverse('load_template'),
            reverse('save_template'),
            reverse('delete_template'),
        ]

        for url in urls_to_protect:
            response = self.client.get(url)
            self.assertEqual(
                response.status_code, 
                302, 
                f"SECURITY LEAK: The URL '{url}' is accessible without logging in!"
            )
            self.assertTrue(
                response.url.startswith('/accounts/login/'), 
                f"SECURITY LEAK: The URL '{url}' redirected somewhere other than the login page!"
            )
