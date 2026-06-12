from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

class UserAuthTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.register_url = reverse('register')
        self.login_url = reverse('login')
        self.logout_url = reverse('logout')
        
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword123'
        )

    def test_register_page_loads(self):
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/register.html')

    def test_login_page_loads(self):
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/login.html')

    def test_user_login(self):
        response = self.client.post(self.login_url, {
            'username': 'testuser',
            'password': 'testpassword123'
        })
        # Should redirect to home after successful login
        self.assertRedirects(response, reverse('home'))
        
        # Verify session is active
        self.assertTrue('_auth_user_id' in self.client.session)

    def test_user_logout(self):
        self.client.login(username='testuser', password='testpassword123')
        response = self.client.get(self.logout_url)
        # Should redirect to login after logout
        self.assertRedirects(response, self.login_url)
        self.assertFalse('_auth_user_id' in self.client.session)

    def test_invalid_login(self):
        response = self.client.post(self.login_url, {
            'username': 'wronguser',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid username or password.')
