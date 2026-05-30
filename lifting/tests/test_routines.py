from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from datetime import date
from lifting.models import WorkoutSession, WorkoutSet, WorkoutTemplate

class RoutineTemplateTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='routine_user', password='password123')
        self.profile = self.user.lifterprofile
        self.profile.squat_1rm = 405
        self.profile.bench_1rm = 315
        self.profile.deadlift_1rm = 495
        self.profile.save()
        
    def test_auto_seeded_templates_on_dashboard(self):
        self.client.login(username='routine_user', password='password123')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        
        # Verify 7 templates are seeded automatically
        templates = WorkoutTemplate.objects.filter(user=self.user)
        self.assertEqual(templates.count(), 7)
        self.assertTrue(templates.filter(name="Powerlifting Big Three").exists())

    def test_load_template(self):
        self.client.login(username='routine_user', password='password123')
        self.client.get(reverse('dashboard'))
        
        template = WorkoutTemplate.objects.get(user=self.user, name="Powerlifting Big Three")
        url = reverse('load_template')
        
        response = self.client.post(url, {'template_id': template.id})
        self.assertEqual(response.status_code, 302)
        
        sets = WorkoutSet.objects.filter(session__user=self.user, session__date=date.today())
        self.assertEqual(sets.count(), 3)
        self.assertTrue(sets.filter(exercise='SQUAT').exists())
        
    def test_save_current_session_as_template(self):
        self.client.login(username='routine_user', password='password123')
        session = WorkoutSession.objects.create(user=self.user, date=date.today())
        WorkoutSet.objects.create(session=session, exercise='BENCH', weight=225, reps=5)
        
        url = reverse('save_template')
        response = self.client.post(url, {'template_name': 'My Custom Chest Day'})
        self.assertEqual(response.status_code, 302)
        
        templates = WorkoutTemplate.objects.filter(user=self.user, name='My Custom Chest Day')
        self.assertEqual(templates.count(), 1)
        self.assertEqual(templates.first().exercises.count(), 1)
        self.assertEqual(templates.first().exercises.first().exercise, 'BENCH')
