from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from datetime import date
from lifting.models import WorkoutSession, WorkoutSet

class DashboardViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='dash_user', password='password123')
        self.url_name = 'dashboard'

    def test_dashboard_success_default(self):
        """Happy Path: Authenticated user loads the dashboard normally."""
        self.client.login(username='dash_user', password='password123')
        url = reverse(self.url_name)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'lifting/dashboard.html')
        self.assertIn('current_p', response.context)
        self.assertEqual(response.context['current_p'], 85)

    def test_dashboard_custom_percentage(self):
        """Parameter Check: User passes a custom intensity percentage via the URL."""
        self.client.login(username='dash_user', password='password123')
        url = reverse(self.url_name)
        response = self.client.get(url, {'p': '75'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['current_p'], 75)

    def test_dashboard_invalid_percentage_fallback(self):
        """Sad Path: User types garbage text into the percentage URL parameter."""
        self.client.login(username='dash_user', password='password123')
        url = reverse(self.url_name)
        response = self.client.get(url, {'p': 'abc'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['current_p'], 85)

    def test_dashboard_unauthenticated(self):
        """Security: An anonymous user tries to view the dashboard."""
        url = reverse(self.url_name)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))


class AnalyticsViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='stats_user', password='password123')
        self.url_name = 'analytics'

    def test_analytics_math_and_warmup_exclusion(self):
        """Happy Path: Verifies tonnage and rep math, and ensures warmups are ignored."""
        self.client.login(username='stats_user', password='password123')
        session = WorkoutSession.objects.create(user=self.user, date=date.today())

        # 1. Add Working Sets
        WorkoutSet.objects.create(session=session, exercise='SQUAT', weight=315, reps=5, set_type='working')
        WorkoutSet.objects.create(session=session, exercise='SQUAT', weight=315, reps=5, set_type='working')
        WorkoutSet.objects.create(session=session, exercise='BENCH', weight=225, reps=5, set_type='working')

        # 2. Add Warmup Sets
        WorkoutSet.objects.create(session=session, exercise='SQUAT', weight=135, reps=10, set_type='warmup')
        WorkoutSet.objects.create(session=session, exercise='DEADLIFT', weight=135, reps=5, set_type='warmup')

        url = reverse(self.url_name)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        tonnage = response.context['tonnage']
        total_reps = response.context['total_reps']

        self.assertEqual(tonnage.get('SQUAT', 0), 3150)
        self.assertEqual(total_reps.get('SQUAT', 0), 10)
        self.assertEqual(tonnage.get('BENCH', 0), 1125)
        self.assertEqual(total_reps.get('BENCH', 0), 5)
        self.assertEqual(tonnage.get('DEADLIFT', 0), 0)
        self.assertEqual(total_reps.get('DEADLIFT', 0), 0)

    def test_analytics_empty_state(self):
        """Sad Path: A brand new user with zero sets loads the page without crashing."""
        self.client.login(username='stats_user', password='password123')
        
        url = reverse(self.url_name)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        tonnage = response.context['tonnage']
        total_reps = response.context['total_reps']
        weekly_breakdown = response.context['weekly_breakdown']

        self.assertEqual(tonnage.get('SQUAT', 0), 0)
        self.assertEqual(total_reps.get('BENCH', 0), 0)
        self.assertEqual(len(weekly_breakdown), 0)

    def test_analytics_unauthenticated(self):
        """Security: An anonymous user tries to view analytics."""
        url = reverse(self.url_name)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))


class LogSetViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='lifter1', password='password123')
        self.session = WorkoutSession.objects.create(user=self.user, date=date.today())
        self.url_name = 'log_set' 

    def test_log_set_success(self):
        """Happy Path: A user logs a valid set via POST and gets an HTMX response."""
        self.client.login(username='lifter1', password='password123')
        url = reverse(self.url_name)
        valid_data = {
            'exercise': 'SQUAT',
            'weight': '315',
            'reps': '5',
            'set_type': 'working'
        }
        
        response = self.client.post(url, data=valid_data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('HX-Trigger', response.headers)
        self.assertEqual(response.headers['HX-Trigger'], 'setLogged')
        self.assertTemplateUsed(response, 'lifting/partials/set_row.html')
        
        self.assertEqual(WorkoutSet.objects.count(), 1)
        new_set = WorkoutSet.objects.first()
        self.assertEqual(new_set.weight, 315)
        self.assertEqual(new_set.reps, 5)

    def test_log_set_invalid_method(self):
        """Method Check: The view must reject GET requests."""
        self.client.login(username='lifter1', password='password123')
        url = reverse(self.url_name)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(WorkoutSet.objects.count(), 0)

    def test_log_set_invalid_data_strings(self):
        """Sad Path: A user bypasses HTML5 validation and sends text for numbers."""
        self.client.login(username='lifter1', password='password123')
        url = reverse(self.url_name)
        invalid_data = {
            'exercise': 'SQUAT',
            'weight': 'heavy',
            'reps': 'five',
            'set_type': 'working'
        }
        response = self.client.post(url, data=invalid_data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(WorkoutSet.objects.count(), 0)

    def test_log_set_invalid_data_negative_numbers(self):
        """Sad Path: A user submits negative weight or reps."""
        self.client.login(username='lifter1', password='password123')
        url = reverse(self.url_name)
        negative_data = {
            'exercise': 'SQUAT',
            'weight': '-135',
            'reps': '-5',
            'set_type': 'working'
        }
        response = self.client.post(url, data=negative_data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(WorkoutSet.objects.count(), 0)

    def test_log_set_unauthenticated(self):
        """Security: An anonymous user tries to log a set."""
        url = reverse(self.url_name)
        valid_data = {
            'exercise': 'SQUAT',
            'weight': '315',
            'reps': '5',
            'set_type': 'working'
        }
        response = self.client.post(url, data=valid_data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))
        self.assertEqual(WorkoutSet.objects.count(), 0)


class DeleteSetViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user_a = User.objects.create_user(username='user_a', password='password123')
        self.session_a = WorkoutSession.objects.create(user=self.user_a, date=date.today())
        self.set_a = WorkoutSet.objects.create(
            session=self.session_a, exercise='SQUAT', weight=315, reps=5, set_type='working'
        )

        self.user_b = User.objects.create_user(username='user_b', password='password123')
        self.session_b = WorkoutSession.objects.create(user=self.user_b, date=date.today())
        self.set_b = WorkoutSet.objects.create(
            session=self.session_b, exercise='BENCH', weight=225, reps=5, set_type='working'
        )

        self.url_name = 'delete_set'

    def test_delete_set_success(self):
        """Happy Path: A user successfully deletes their own set via POST."""
        self.client.login(username='user_a', password='password123')
        self.assertTrue(WorkoutSet.objects.filter(id=self.set_a.id).exists())
        
        url = reverse(self.url_name, args=[self.set_a.id])
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")
        self.assertFalse(WorkoutSet.objects.filter(id=self.set_a.id).exists())

    def test_delete_set_wrong_method(self):
        """Method Check: The view must reject GET requests because of @require_POST."""
        self.client.login(username='user_a', password='password123')
        url = reverse(self.url_name, args=[self.set_a.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)
        self.assertTrue(WorkoutSet.objects.filter(id=self.set_a.id).exists())

    def test_delete_set_cross_user_isolation(self):
        """Security: User A tries to delete User B's set."""
        self.client.login(username='user_a', password='password123')
        url = reverse(self.url_name, args=[self.set_b.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(WorkoutSet.objects.filter(id=self.set_b.id).exists())

    def test_delete_set_not_found(self):
        """Sad Path: A user tries to delete a set ID that doesn't exist."""
        self.client.login(username='user_a', password='password123')
        url = reverse(self.url_name, args=[999])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    def test_delete_set_unauthenticated(self):
        """Security: An anonymous user tries to delete a set."""
        url = reverse(self.url_name, args=[self.set_a.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))
        self.assertTrue(WorkoutSet.objects.filter(id=self.set_a.id).exists())


class UpdateSetTypeTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user_a = User.objects.create_user(username='user_a', password='password123')
        self.session_a = WorkoutSession.objects.create(user=self.user_a, date=date.today())
        self.set_a = WorkoutSet.objects.create(
            session=self.session_a, exercise='SQUAT', weight=315, reps=5, set_type='working'
        )

        self.user_b = User.objects.create_user(username='user_b', password='password123')
        self.session_b = WorkoutSession.objects.create(user=self.user_b, date=date.today())
        self.set_b = WorkoutSet.objects.create(
            session=self.session_b, exercise='BENCH', weight=225, reps=5, set_type='working'
        )

        self.url_name = 'update_set_type'

    def test_update_set_type_success(self):
        """Happy Path: A user successfully updates their own set type via POST."""
        self.client.login(username='user_a', password='password123')
        url = reverse(self.url_name, args=[self.set_a.id])
        
        response = self.client.post(url, data={'set_type': 'warmup'})
        self.assertEqual(response.status_code, 200)
        self.set_a.refresh_from_db()
        self.assertEqual(self.set_a.set_type, 'warmup')

        response = self.client.post(url, data={'set_type': 'failure'})
        self.assertEqual(response.status_code, 200)
        self.set_a.refresh_from_db()
        self.assertEqual(self.set_a.set_type, 'failure')

    def test_update_set_type_wrong_method(self):
        """Method Check: The view must reject GET requests because of @require_POST."""
        self.client.login(username='user_a', password='password123')
        url = reverse(self.url_name, args=[self.set_a.id])
        response = self.client.get(url, data={'set_type': 'warmup'})
        self.assertEqual(response.status_code, 405)
        self.set_a.refresh_from_db()
        self.assertEqual(self.set_a.set_type, 'working')

    def test_update_set_type_cross_user_isolation(self):
        """Security: User A tries to update User B's set type."""
        self.client.login(username='user_a', password='password123')
        url = reverse(self.url_name, args=[self.set_b.id])
        response = self.client.post(url, data={'set_type': 'warmup'})
        self.assertEqual(response.status_code, 404)
        self.set_b.refresh_from_db()
        self.assertEqual(self.set_b.set_type, 'working')

    def test_update_set_type_invalid_value(self):
        """Sad Path: Trying to update set_type to an invalid value does not change it."""
        self.client.login(username='user_a', password='password123')
        url = reverse(self.url_name, args=[self.set_a.id])
        response = self.client.post(url, data={'set_type': 'invalid_type'})
        self.assertEqual(response.status_code, 200)
        self.set_a.refresh_from_db()
        self.assertEqual(self.set_a.set_type, 'working')

    def test_update_set_type_not_found(self):
        """Sad Path: A user tries to update a set ID that doesn't exist."""
        self.client.login(username='user_a', password='password123')
        url = reverse(self.url_name, args=[999])
        response = self.client.post(url, data={'set_type': 'warmup'})
        self.assertEqual(response.status_code, 404)

    def test_update_set_type_unauthenticated(self):
        """Security: An anonymous user tries to update a set type."""
        url = reverse(self.url_name, args=[self.set_a.id])
        response = self.client.post(url, data={'set_type': 'warmup'})
        self.assertEqual(response.status_code, 302)
        self.set_a.refresh_from_db()
        self.assertEqual(self.set_a.set_type, 'working')
