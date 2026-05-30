from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from datetime import date
from django.core.files.uploadedfile import SimpleUploadedFile
from lifting.models import WorkoutSession, WorkoutSet

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

        self.url_name = 'export_data'

    def test_export_data_headers(self):
        """Happy Path: Verifies the response tells the browser to download a CSV."""
        self.client.login(username='exporter_a', password='password123')
        
        url = reverse(self.url_name)
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('.csv', response['Content-Disposition'])

    def test_export_data_content_and_isolation(self):
        """Security & Data: Ensures accurate data and prevents cross-user leakage."""
        self.client.login(username='exporter_a', password='password123')
        
        url = reverse(self.url_name)
        response = self.client.get(url)
        content = response.content.decode('utf-8')
        
        self.assertIn('SQUAT', content)
        self.assertIn('315', content)
        self.assertNotIn('BENCH', content)
        self.assertNotIn('225', content)

    def test_export_data_unauthenticated(self):
        """Security: An anonymous user tries to download the database."""
        url = reverse(self.url_name)
        response = self.client.get(url)
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
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith(reverse('history')))

    def test_import_csv_invalid_extension(self):
        self.client.login(username='importer_a', password='password123')
        csv_file = SimpleUploadedFile("lifting_data.txt", b"dummy content", content_type="text/plain")
        response = self.client.post(self.url, {'csv_file': csv_file})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode(), "Please upload a valid CSV file.")

    def test_import_csv_empty_file(self):
        self.client.login(username='importer_a', password='password123')
        csv_file = SimpleUploadedFile("lifting_data.csv", b"", content_type="text/csv")
        response = self.client.post(self.url, {'csv_file': csv_file})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode(), "CSV file is empty.")

    def test_import_csv_malformed_rows_skipped(self):
        self.client.login(username='importer_a', password='password123')
        csv_content = (
            "Date,Training Week Start,Exercise,Weight (lbs),Reps,Set Tonnage (lbs),Estimated 1RM,Set Type\n"
            "invalid-date,2026-05-25,Squat,315,5,1575,367,Working\n"
            "2026-05-25,2026-05-25,Squat,invalid-weight,5,1575,367,Working\n"
            "2026-05-25,2026-05-25,Squat,315,5,1575,367,Working\n"
        )
        csv_file = SimpleUploadedFile("lifting_data.csv", csv_content.encode('utf-8'), content_type="text/csv")
        response = self.client.post(self.url, {'csv_file': csv_file})
        
        self.assertEqual(response.status_code, 302)
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
