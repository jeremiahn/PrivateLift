from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from lifting.models import LifterProfile

class ProfileSettingsViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='profile_user', password='password123')
        self.profile, created = LifterProfile.objects.get_or_create(user=self.user)
        self.url_name = 'profile_settings'

    def test_profile_settings_update_success(self):
        """Happy Path: User updates their 1RMs successfully and is redirected."""
        self.client.login(username='profile_user', password='password123')
        
        url = reverse(self.url_name)
        valid_data = {
            'squat': '405',
            'bench': '315',
            'deadlift': '500'
        }
        
        response = self.client.post(url, data=valid_data)
        self.assertEqual(response.status_code, 302)
        
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.squat_1rm, 405)
        self.assertEqual(self.profile.bench_1rm, 315)
        self.assertEqual(self.profile.deadlift_1rm, 500)

    def test_profile_settings_toggle_rest_timer(self):
        """Happy Path: User toggles the automated rest timer setting on and off."""
        self.client.login(username='profile_user', password='password123')
        url = reverse(self.url_name)
        
        # 1. Test turning it off (unchecked / not passed in POST)
        response = self.client.post(url, data={
            'squat': '405',
            'bench': '315',
            'deadlift': '500'
        })
        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.show_rest_timer)
        
        # 2. Test turning it on (checked / passed as 'on')
        response = self.client.post(url, data={
            'squat': '405',
            'bench': '315',
            'deadlift': '500',
            'show_rest_timer': 'on'
        })
        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.show_rest_timer)

    def test_profile_settings_invalid_data(self):
        """Sad Path: User bypasses the HTML form and submits text instead of numbers."""
        self.client.login(username='profile_user', password='password123')
        url = reverse(self.url_name)
        
        invalid_data = {
            'squat_1rm': 'heavy',
            'bench_1rm': '315',
            'deadlift_1rm': '500'
        }
        
        response = self.client.post(url, data=invalid_data)
        self.assertEqual(response.status_code, 400)
        
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
