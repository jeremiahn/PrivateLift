from django.contrib.auth.models import User
from .models import WorkoutSession, WorkoutSet, LifterProfile
from django.test import TestCase, Client
from django.urls import reverse
from datetime import date, timedelta
from django.core.files.uploadedfile import SimpleUploadedFile

class BoundaryLimitTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='limit_user', password='password123')
        
        # Create a session to attach sets to
        self.session = WorkoutSession.objects.create(user=self.user, date=date.today())

    def test_log_set_extreme_weight(self):
        """Boundary: User tries to log a 100,000 lb squat."""
        self.client.login(username='limit_user', password='password123')
        url = reverse('log_set')
        
        extreme_data = {
            'exercise': 'SQUAT',
            'weight': '100000', # 100k lbs
            'reps': '5',
            'set_type': 'working'
        }
        
        # You have to decide your business logic here. 
        # Does your app allow 100,000 lbs? If you added a limit in your view 
        # (e.g., if weight > 2000: return 400), this test ensures that logic works.
        response = self.client.post(url, data=extreme_data)
        
        # If you WANT to block it, expect a 400 status. 
        # If your app allows it, expect a 200 status. 
        # self.assertEqual(response.status_code, 400) 
        pass

    def test_log_set_decimals_in_integer_field(self):
        """Boundary: User tries to submit a fraction when the DB expects an integer."""
        self.client.login(username='limit_user', password='password123')
        url = reverse('log_set')
        
        decimal_data = {
            'exercise': 'BENCH',
            'weight': '225.5', # Invalid for IntegerField
            'reps': '5',
            'set_type': 'working'
        }
        
        response = self.client.post(url, data=decimal_data)
        
        # Your try/except ValueError block should catch '225.5' if casting with int()
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
        
        response = self.client.post(url, data=negative_data)
        
        # Again, if you added logic to block negative numbers, assert a 400.
        # self.assertEqual(response.status_code, 400)
        pass

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
        # NOTE: You will need to adjust the string below to match exactly what 
        # your WorkoutSet.__str__() method returns in models.py!
        expected_string = "SQUAT: 315x5 @ RPE None" 
        self.assertEqual(str(self.workout_set), expected_string)

    def test_workout_session_string_representation(self):
        """Happy Path: Verifies the WorkoutSession __str__ method."""
        # Adjust to match your actual session string output
        expected_string = f"{self.user.username} - {date.today()}"
        self.assertEqual(str(self.session), expected_string)

    def test_get_tonnage_property(self):
        """Math Check: If you have a custom tonnage method on the model, test it here."""
        # If your WorkoutSet model has a method like `def get_tonnage(self):`
        # self.assertEqual(self.workout_set.get_tonnage(), 1575)
        pass # Remove 'pass' if you implement the custom method above

class ProfileSettingsViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='profile_user', password='password123')
        
        # Assuming you have a UserProfile model linked one-to-one with the Django User.
        # (If your 1RM fields are directly on a custom User model, you can just use self.user)
        self.profile, created = LifterProfile.objects.get_or_create(user=self.user)
        
        # Base URL name (adjust 'profile_settings' if your urls.py uses a different name)
        self.url_name = 'profile_settings'

    def test_profile_settings_update_success(self):
        """Happy Path: User updates their 1RMs successfully and is redirected."""
        self.client.login(username='profile_user', password='password123')
        
        url = reverse(self.url_name)
        
        # Adjust these dictionary keys to match your actual HTML form input names!
        valid_data = {
            'squat': '405',
            'bench': '315',
            'deadlift': '500'
        }
        
        response = self.client.post(url, data=valid_data)
        
        # A successful form submission should redirect (302) the user to the dashboard
        self.assertEqual(response.status_code, 302)
        
        # Refresh the profile object from the test database to get the newly saved values
        self.profile.refresh_from_db()
        
        # Verify the math and database updates worked perfectly
        self.assertEqual(self.profile.squat_1rm, 405)
        self.assertEqual(self.profile.bench_1rm, 315)
        self.assertEqual(self.profile.deadlift_1rm, 500)

    def test_profile_settings_invalid_data(self):
        """Sad Path: User bypasses the HTML form and submits text instead of numbers."""
        self.client.login(username='profile_user', password='password123')
        
        url = reverse(self.url_name)
        
        invalid_data = {
            'squat_1rm': 'heavy', # Invalid text!
            'bench_1rm': '315',
            'deadlift_1rm': '500'
        }
        
        response = self.client.post(url, data=invalid_data)
        
        # The try/except block in your view should catch the ValueError and return a 400
        self.assertEqual(response.status_code, 400)
        
        # Double-check that the bad data didn't accidentally overwrite the database
        self.profile.refresh_from_db()
        self.assertNotEqual(self.profile.squat_1rm, 'heavy')

    def test_profile_settings_unauthenticated(self):
        """Security: An anonymous user tries to view or edit settings."""
        url = reverse(self.url_name)
        
        # Test GET request
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))
        
        # Test POST request
        post_response = self.client.post(url, data={'squat_1rm': '405'})
        self.assertEqual(post_response.status_code, 302)
        self.assertTrue(post_response.url.startswith('/accounts/login/'))

class ExportDataViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # User A (The user we will test with)
        self.user_a = User.objects.create_user(username='exporter_a', password='password123')
        self.session_a = WorkoutSession.objects.create(user=self.user_a, date=date.today())
        self.set_a = WorkoutSet.objects.create(
            session=self.session_a, exercise='SQUAT', weight=315, reps=5, set_type='working'
        )
        
        # User B (To ensure their data doesn't leak into User A's export)
        self.user_b = User.objects.create_user(username='exporter_b', password='password123')
        self.session_b = WorkoutSession.objects.create(user=self.user_b, date=date.today())
        self.set_b = WorkoutSet.objects.create(
            session=self.session_b, exercise='BENCH', weight=225, reps=5, set_type='working'
        )

        # Base URL name
        self.url_name = 'export_data'

    def test_export_data_headers(self):
        """Happy Path: Verifies the response tells the browser to download a CSV."""
        self.client.login(username='exporter_a', password='password123')
        
        url = reverse(self.url_name)
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Verify the content type is explicitly set to CSV
        self.assertEqual(response['Content-Type'], 'text/csv')
        
        # Verify it triggers an attachment download rather than rendering in the browser
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('.csv', response['Content-Disposition'])

    def test_export_data_content_and_isolation(self):
        """Security & Data: Ensures accurate data and prevents cross-user leakage."""
        self.client.login(username='exporter_a', password='password123')
        
        url = reverse(self.url_name)
        response = self.client.get(url)
        
        # Decode the raw byte response into a readable string
        content = response.content.decode('utf-8')
        
        # Verify User A's data is actually present in the CSV output
        self.assertIn('SQUAT', content)
        self.assertIn('315', content)
        
        # Verify User B's data is strictly excluded from the CSV
        self.assertNotIn('BENCH', content)
        self.assertNotIn('225', content)

    def test_export_data_unauthenticated(self):
        """Security: An anonymous user tries to download the database."""
        url = reverse(self.url_name)
        response = self.client.get(url)
        
        # Verify they are bounced back to the login page
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))

class ImportDataViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='importer_a', password='password123')
        self.url = reverse('import_data')

    def test_import_csv_happy_path(self):
        self.client.login(username='importer_a', password='password123')
        
        csv_content = (
            "Date,Training Week Start,Exercise,Weight (lbs),Reps,Set Tonnage (lbs),Estimated 1RM,Set Type\n"
            "2026-05-25,2026-05-25,Squat,315,5,1575,367,Working\n"
            "2026-05-26,2026-05-25,Bench Press,225,5,1125,262,Working\n"
        )
        
        csv_file = SimpleUploadedFile("lifting_data.csv", csv_content.encode('utf-8'), content_type="text/csv")
        
        response = self.client.post(self.url, {'csv_file': csv_file})
        self.assertEqual(response.status_code, 302)
        
        sessions = WorkoutSession.objects.filter(user=self.user)
        self.assertEqual(sessions.count(), 2)
        
        sets = WorkoutSet.objects.filter(session__user=self.user)
        self.assertEqual(sets.count(), 2)
        
        squat_set = sets.get(exercise='SQUAT')
        self.assertEqual(squat_set.weight, 315)
        self.assertEqual(squat_set.reps, 5)
        self.assertEqual(squat_set.e1rm, 368) # 315 * (1 + 5/30) = 367.5 -> rounded to 368
        self.assertEqual(squat_set.session.date.strftime('%Y-%m-%d'), '2026-05-25')

    def test_import_csv_unauthenticated(self):
        csv_file = SimpleUploadedFile("lifting_data.csv", b"dummy content", content_type="text/csv")
        response = self.client.post(self.url, {'csv_file': csv_file})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))

    def test_import_csv_missing_file(self):
        self.client.login(username='importer_a', password='password123')
        response = self.client.post(self.url)
        # Missing file should redirect to history
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith(reverse('history')))

    def test_import_csv_invalid_extension(self):
        self.client.login(username='importer_a', password='password123')
        csv_file = SimpleUploadedFile("lifting_data.txt", b"dummy content", content_type="text/plain")
        response = self.client.post(self.url, {'csv_file': csv_file})
        # Invalid extension should return 400 Bad Request
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode(), "Please upload a valid CSV file.")

    def test_import_csv_empty_file(self):
        self.client.login(username='importer_a', password='password123')
        csv_file = SimpleUploadedFile("lifting_data.csv", b"", content_type="text/csv")
        response = self.client.post(self.url, {'csv_file': csv_file})
        # Empty file should return 400 Bad Request
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode(), "CSV file is empty.")

    def test_import_csv_malformed_rows_skipped(self):
        self.client.login(username='importer_a', password='password123')
        csv_content = (
            "Date,Training Week Start,Exercise,Weight (lbs),Reps,Set Tonnage (lbs),Estimated 1RM,Set Type\n"
            "invalid-date,2026-05-25,Squat,315,5,1575,367,Working\n" # Invalid date
            "2026-05-25,2026-05-25,Squat,invalid-weight,5,1575,367,Working\n" # Invalid weight
            "2026-05-25,2026-05-25,Squat,315,5,1575,367,Working\n" # Valid row
        )
        csv_file = SimpleUploadedFile("lifting_data.csv", csv_content.encode('utf-8'), content_type="text/csv")
        response = self.client.post(self.url, {'csv_file': csv_file})
        
        self.assertEqual(response.status_code, 302)
        # Only the valid row should have been imported
        sets = WorkoutSet.objects.filter(session__user=self.user)
        self.assertEqual(sets.count(), 1)
        self.assertEqual(sets.first().weight, 315)

    def test_import_csv_rpe_and_set_type(self):
        self.client.login(username='importer_a', password='password123')
        csv_content = (
            "Date,Training Week Start,Exercise,Weight (lbs),Reps,Set Tonnage (lbs),Estimated 1RM,Set Type,RPE\n"
            "2026-05-25,2026-05-25,Squat,315,5,1575,367,Warmup,8.5\n"
            "2026-05-26,2026-05-25,Bench Press,225,5,1125,262,Failure,9\n"
        )
        csv_file = SimpleUploadedFile("lifting_data.csv", csv_content.encode('utf-8'), content_type="text/csv")
        response = self.client.post(self.url, {'csv_file': csv_file})
        self.assertEqual(response.status_code, 302)
        
        sets = WorkoutSet.objects.filter(session__user=self.user)
        self.assertEqual(sets.count(), 2)
        
        squat_set = sets.get(exercise='SQUAT')
        self.assertEqual(squat_set.set_type, 'warmup')
        self.assertEqual(squat_set.rpe, 8.5)
        
        bench_set = sets.get(exercise='BENCH')
        self.assertEqual(bench_set.set_type, 'failure')
        self.assertEqual(bench_set.rpe, 9.0)

class DashboardViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='dash_user', password='password123')
        
        # Base URL name (adjust 'dashboard' if your urls.py uses a different name, like 'home' or 'index')
        self.url_name = 'dashboard'

    def test_dashboard_success_default(self):
        """Happy Path: Authenticated user loads the dashboard normally."""
        self.client.login(username='dash_user', password='password123')
        
        url = reverse(self.url_name)
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Verify the correct main template is used
        self.assertTemplateUsed(response, 'lifting/dashboard.html')
        
        # Verify the default intensity percentage (85%) is set in the context
        self.assertIn('current_p', response.context)
        self.assertEqual(response.context['current_p'], 85)

    def test_dashboard_custom_percentage(self):
        """Parameter Check: User passes a custom intensity percentage via the URL."""
        self.client.login(username='dash_user', password='password123')
        
        url = reverse(self.url_name)
        # Simulate hitting /dashboard/?p=75
        response = self.client.get(url, {'p': '75'})
        
        self.assertEqual(response.status_code, 200)
        
        # Verify the view correctly parsed the 75 and passed it to the template
        self.assertEqual(response.context['current_p'], 75)

    def test_dashboard_invalid_percentage_fallback(self):
        """Sad Path: User types garbage text into the percentage URL parameter."""
        self.client.login(username='dash_user', password='password123')
        
        url = reverse(self.url_name)
        # Simulate hitting /dashboard/?p=abc
        response = self.client.get(url, {'p': 'abc'})
        
        self.assertEqual(response.status_code, 200)
        
        # Verify the try/except block caught the ValueError and safely defaulted to 85
        self.assertEqual(response.context['current_p'], 85)

    def test_dashboard_unauthenticated(self):
        """Security: An anonymous user tries to view the dashboard."""
        url = reverse(self.url_name)
        response = self.client.get(url)
        
        # Verify they are bounced back to the login page
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))

class AnalyticsViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='stats_user', password='password123')
        self.url_name = 'analytics'  # Adjust if your urls.py uses a different name

    def test_analytics_math_and_warmup_exclusion(self):
        """Happy Path: Verifies tonnage and rep math, and ensures warmups are ignored."""
        self.client.login(username='stats_user', password='password123')
        
        # Create a session
        session = WorkoutSession.objects.create(user=self.user, date=date.today())

        # 1. Add Working Sets (Should be counted)
        # Squat: 2 sets of 5 reps @ 315 lbs = 3,150 lbs tonnage, 10 reps
        WorkoutSet.objects.create(session=session, exercise='SQUAT', weight=315, reps=5, set_type='working')
        WorkoutSet.objects.create(session=session, exercise='SQUAT', weight=315, reps=5, set_type='working')
        
        # Bench: 1 set of 5 reps @ 225 lbs = 1,125 lbs tonnage, 5 reps
        WorkoutSet.objects.create(session=session, exercise='BENCH', weight=225, reps=5, set_type='working')

        # 2. Add Warmup Sets (Should NOT be counted)
        WorkoutSet.objects.create(session=session, exercise='SQUAT', weight=135, reps=10, set_type='warmup')
        WorkoutSet.objects.create(session=session, exercise='DEADLIFT', weight=135, reps=5, set_type='warmup')

        url = reverse(self.url_name)
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        
        # Extract the context variables passed to the template
        tonnage = response.context['tonnage']
        total_reps = response.context['total_reps']

        # Verify Squat totals
        self.assertEqual(tonnage.get('SQUAT', 0), 3150)
        self.assertEqual(total_reps.get('SQUAT', 0), 10)

        # Verify Bench totals
        self.assertEqual(tonnage.get('BENCH', 0), 1125)
        self.assertEqual(total_reps.get('BENCH', 0), 5)

        # Verify Deadlift totals (Only had a warmup, so working totals should be 0)
        self.assertEqual(tonnage.get('DEADLIFT', 0), 0)
        self.assertEqual(total_reps.get('DEADLIFT', 0), 0)

    def test_analytics_empty_state(self):
        """Sad Path: A brand new user with zero sets loads the page without crashing."""
        self.client.login(username='stats_user', password='password123')
        
        url = reverse(self.url_name)
        response = self.client.get(url)
        
        # Verify the page loads successfully (No NoneType or division by zero errors)
        self.assertEqual(response.status_code, 200)
        
        tonnage = response.context['tonnage']
        total_reps = response.context['total_reps']
        weekly_breakdown = response.context['weekly_breakdown']

        # Everything should gracefully default to 0 or empty dictionaries
        self.assertEqual(tonnage.get('SQUAT', 0), 0)
        self.assertEqual(total_reps.get('BENCH', 0), 0)
        self.assertEqual(len(weekly_breakdown), 0)

    def test_analytics_unauthenticated(self):
        """Security: An anonymous user tries to view analytics."""
        url = reverse(self.url_name)
        response = self.client.get(url)
        
        # Verify they are bounced back to the login page
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))

class LogSetViewTests(TestCase):
    def setUp(self):
        # Initialize the test client
        self.client = Client()

        # Create a test user
        self.user = User.objects.create_user(username='lifter1', password='password123')
        
        # Create a daily session for the sets to attach to
        self.session = WorkoutSession.objects.create(user=self.user, date=date.today())

        # Base URL name (adjust 'log_set' if your urls.py uses a different name)
        # Note: If your URL requires an argument like session ID, add it to args=[]
        self.url_name = 'log_set' 

    def test_log_set_success(self):
        """Happy Path: A user logs a valid set via POST and gets an HTMX response."""
        self.client.login(username='lifter1', password='password123')
        
        url = reverse(self.url_name)
        
        # Simulate the form data sent by the frontend
        valid_data = {
            'exercise': 'SQUAT',
            'weight': '315',
            'reps': '5',
            'set_type': 'working'
        }
        
        response = self.client.post(url, data=valid_data)
        
        # Verify the response is successful
        self.assertEqual(response.status_code, 200)
        
        # Verify HTMX headers are present (Crucial for your dynamic frontend!)
        self.assertIn('HX-Trigger', response.headers)
        self.assertEqual(response.headers['HX-Trigger'], 'setLogged')
        
        # Verify the exact template was used for the partial swap
        self.assertTemplateUsed(response, 'lifting/partials/set_row.html')
        
        # Verify the database actually created the set
        self.assertEqual(WorkoutSet.objects.count(), 1)
        new_set = WorkoutSet.objects.first()
        self.assertEqual(new_set.weight, 315)
        self.assertEqual(new_set.reps, 5)

    def test_log_set_invalid_method(self):
        """Method Check: The view must reject GET requests."""
        self.client.login(username='lifter1', password='password123')
        
        url = reverse(self.url_name)
        response = self.client.get(url)
        
        # Should return 405 Method Not Allowed or 400 Bad Request depending on implementation
        # Assuming you used @require_POST:
        self.assertEqual(response.status_code, 400)
        
        # Verify nothing was saved to the database
        self.assertEqual(WorkoutSet.objects.count(), 0)

    def test_log_set_invalid_data_strings(self):
        """Sad Path: A user bypasses HTML5 validation and sends text for numbers."""
        self.client.login(username='lifter1', password='password123')
        
        url = reverse(self.url_name)
        
        invalid_data = {
            'exercise': 'SQUAT',
            'weight': 'heavy', # Invalid!
            'reps': 'five',    # Invalid!
            'set_type': 'working'
        }
        
        response = self.client.post(url, data=invalid_data)
        
        # The try/except ValueError block should catch this and return a 400
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
        
        # Depending on your exact view logic, this should return 400
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
        
        # @login_required should intercept and redirect (302) to the login page
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/'))
        self.assertEqual(WorkoutSet.objects.count(), 0)

class DeleteSetViewTests(TestCase):
    def setUp(self):
        # Initialize the test client
        self.client = Client()

        # Create User A (The primary test user)
        self.user_a = User.objects.create_user(username='user_a', password='password123')
        self.session_a = WorkoutSession.objects.create(user=self.user_a, date=date.today())
        self.set_a = WorkoutSet.objects.create(
            session=self.session_a, 
            exercise='SQUAT', 
            weight=315, 
            reps=5, 
            set_type='working'
        )

        # Create User B (The malicious/other user for security testing)
        self.user_b = User.objects.create_user(username='user_b', password='password123')
        self.session_b = WorkoutSession.objects.create(user=self.user_b, date=date.today())
        self.set_b = WorkoutSet.objects.create(
            session=self.session_b, 
            exercise='BENCH', 
            weight=225, 
            reps=5, 
            set_type='working'
        )

        # Base URL name (ensure this matches your urls.py name, e.g., name='delete_set')
        self.url_name = 'delete_set'

    def test_delete_set_success(self):
        """Happy Path: A user successfully deletes their own set via POST."""
        self.client.login(username='user_a', password='password123')
        
        # Verify the set exists before deletion
        self.assertTrue(WorkoutSet.objects.filter(id=self.set_a.id).exists())
        
        url = reverse(self.url_name, args=[self.set_a.id])
        response = self.client.post(url)
        
        # HTMX expects an empty response (200 OK with no content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")
        
        # Verify the set is actually gone from the database
        self.assertFalse(WorkoutSet.objects.filter(id=self.set_a.id).exists())

    def test_delete_set_wrong_method(self):
        """Method Check: The view must reject GET requests because of @require_POST."""
        self.client.login(username='user_a', password='password123')
        url = reverse(self.url_name, args=[self.set_a.id])
        
        response = self.client.get(url)
        
        # @require_POST returns a 405 Method Not Allowed response
        self.assertEqual(response.status_code, 405)
        # Verify the set was NOT deleted
        self.assertTrue(WorkoutSet.objects.filter(id=self.set_a.id).exists())

    def test_delete_set_cross_user_isolation(self):
        """Security: User A tries to delete User B's set."""
        self.client.login(username='user_a', password='password123')
        
        # User A sends a POST to User B's set ID
        url = reverse(self.url_name, args=[self.set_b.id])
        response = self.client.post(url)
        
        # Because of `session__user=request.user`, it should return 404
        self.assertEqual(response.status_code, 404)
        
        # Verify User B's set remains completely safe and untouched
        self.assertTrue(WorkoutSet.objects.filter(id=self.set_b.id).exists())

    def test_delete_set_not_found(self):
        """Sad Path: A user tries to delete a set ID that doesn't exist."""
        self.client.login(username='user_a', password='password123')
        
        # ID 999 does not exist
        url = reverse(self.url_name, args=[999])
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 404)

    def test_delete_set_unauthenticated(self):
        """Security: An anonymous user tries to delete a set."""
        url = reverse(self.url_name, args=[self.set_a.id])
        response = self.client.post(url)
        
        # @login_required should redirect (302) to the login page
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/accounts/login/')) # Adjust '/login/' if your settings.LOGIN_URL differs
        
        # Verify the set is untouched
        self.assertTrue(WorkoutSet.objects.filter(id=self.set_a.id).exists())


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

class GlobalSecurityTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_all_views_require_login(self):
        """Security: Ensures no primary views are accidentally left public."""
        
        # A list of every URL in your app that should be protected
        urls_to_protect = [
            reverse('dashboard'),
            reverse('analytics'),
            reverse('profile_settings'),
            reverse('export_data'),
            reverse('import_data'),
        ]

        for url in urls_to_protect:
            response = self.client.get(url)
            
            # Ensure the view bounces the anonymous user (302 Redirect)
            self.assertEqual(
                response.status_code, 
                302, 
                f"SECURITY LEAK: The URL '{url}' is accessible without logging in!"
            )
            
            # Ensure they are specifically bounced to the login screen
            self.assertTrue(
                response.url.startswith('/accounts/login/'), 
                f"SECURITY LEAK: The URL '{url}' redirected somewhere other than the login page!"
            )


class UpdateSetTypeTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create User A
        self.user_a = User.objects.create_user(username='user_a', password='password123')
        self.session_a = WorkoutSession.objects.create(user=self.user_a, date=date.today())
        self.set_a = WorkoutSet.objects.create(
            session=self.session_a, 
            exercise='SQUAT', 
            weight=315, 
            reps=5, 
            set_type='working'
        )

        # Create User B
        self.user_b = User.objects.create_user(username='user_b', password='password123')
        self.session_b = WorkoutSession.objects.create(user=self.user_b, date=date.today())
        self.set_b = WorkoutSet.objects.create(
            session=self.session_b, 
            exercise='BENCH', 
            weight=225, 
            reps=5, 
            set_type='working'
        )

        self.url_name = 'update_set_type'

    def test_update_set_type_success(self):
        """Happy Path: A user successfully updates their own set type via POST."""
        self.client.login(username='user_a', password='password123')
        url = reverse(self.url_name, args=[self.set_a.id])
        
        # Update type to warmup
        response = self.client.post(url, data={'set_type': 'warmup'})
        
        self.assertEqual(response.status_code, 200)
        self.set_a.refresh_from_db()
        self.assertEqual(self.set_a.set_type, 'warmup')

        # Update type to failure
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
        self.assertEqual(self.set_a.set_type, 'working') # remains working

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