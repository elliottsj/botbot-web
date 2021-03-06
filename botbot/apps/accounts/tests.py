# -*- coding: utf-8 -*-
"""
Account tests.
"""
import datetime
import pytz
from django.core.urlresolvers import reverse_lazy
from django.test import TestCase

from botbot.apps.accounts import models as account_models
from botbot.apps.logs import models as logs_models
from botbot.apps.bots import models as bot_models


class AccountMixin(object):
    """
    Mixin to create users/accounts.
    """
    def setUp(self):
        super(AccountMixin, self).setUp()
        self.member = account_models.User.objects.create_user(
            username="dupont éîïè",
            password="secret",
            email="dupont@botbot.local")
        self.member.is_superuser = True
        self.member.is_staff = True
        self.member.save()
        self.outsider = account_models.User.objects.create_user(
            username="Marie Thérèse",
            password="secret",
            email="m.therese@botbot.local")
        self.chatbot = bot_models.ChatBot.objects.create(
                server='testserver',
                nick='botbot',
                is_active=True)
        self.public_channel = bot_models.Channel.objects.create(
            chatbot=self.chatbot,
            name="#Test",
            slug="test",
            is_public=True)
        logs_models.Log.objects.create(
            channel=self.public_channel,
            command='PRIVMSG',
            timestamp=pytz.utc.localize(datetime.datetime.now()))
        self.private_channel = bot_models.Channel.objects.create(
            chatbot=self.chatbot,
            name="#test-internal",
            is_public=False)

        account_models.Membership.objects.create(
            user=self.member, channel=self.private_channel, is_owner=True,
            is_admin=True)


class DashboardTests(AccountMixin, TestCase):
    """
    Test the dashboard for anon & authenticated users.
    """
    url = reverse_lazy('settings_dashboard')

    def test_template_used(self):
        """
        Ensure anonymous users are served the correct template
        """
        response = self.client.get(self.url)
        self.assertEquals(response.status_code, 200)

        for var in ('admin_channels', 'private_channels'):
            self.assertTrue(var not in response.context.keys())

        self.assertTemplateUsed(response, 'accounts/anon_dashboard.html')

        self.client.login(username="dupont éîïè", password='secret')

        response = self.client.get(self.url)
        self.assertEquals(response.status_code, 200)

        for var in ('admin_channels', 'private_channels'):
            self.assertIn(var, response.context.keys())

        self.assertTemplateUsed(response, 'accounts/user_dashboard.html')


class ChannelsTests(AccountMixin, TestCase):
    """
    Test the dashboard for anon & authenticated users.
    """
    url = reverse_lazy('account_channels')

    def test_template_context_variables(self):
        """
        Ensure anonymous users are served the correct context vars.
        """
        response = self.client.get(self.url)
        self.assertEquals(response.status_code, 200)
        for var in ('admin_channels', 'private_channels'):
            self.assertTrue(var not in response.context.keys())
        self.assertNotContains(response, 'Private')

        self.client.login(username="dupont éîïè", password='secret')

        response = self.client.get(self.url)
        self.assertEquals(response.status_code, 200)

        for var in ('admin_channels', 'private_channels'):
            self.assertIn(var, response.context.keys())

        self.assertContains(response, 'Private')


class ManageAccountTests(AccountMixin, TestCase):
    """
    Test the manage account view.
    """
    url = reverse_lazy('settings_account')

    def test_logged_out(self):
        """
        A logged out user should be redirected.
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_update_account(self):
        """
        Ensure an account is updated.
        """
        self.client.login(username='Marie Thérèse', password='secret')

        response = self.client.get(self.url)
        instance = response.context['form'].instance

        self.assertEqual(self.outsider, instance)

        data = {
            'username': 'marie',
            'nick': 'marie',
            'timezone': self.outsider.timezone
        }

        response = self.client.post(self.url, data=data)
        self.assertEqual(response.status_code, 302)

        user = account_models.User.objects.get(pk=self.outsider.pk)
        self.assertEqual(user.username, 'marie')
        self.assertEqual(user.nick, 'marie')

    def test_change_password(self):
        """
        Ensure the users password can be changed.
        """
        original_password = self.outsider.password
        self.client.login(username='Marie Thérèse', password='secret')

        response = self.client.get(self.url)
        # password form should be in template context
        self.assertIn('password_form', response.context)

        data = {
            'username': 'marie',
            'nick': 'marie',
            'timezone': self.outsider.timezone,
            'change_password_toggle': 'yes',
            'password-form-new_password1': 'abc',
            'password-form-new_password2': '123'
        }
        response = self.client.post(self.url, data=data)
        self.assertEquals(response.status_code, 200)
        self.assertEquals(
            response.context['password_form'].errors,
            {'new_password2': [u"The two password fields didn't match."]})

        data.update({
            'password-form-new_password1': 'abc123',
            'password-form-new_password2': 'abc123',
        })

        response = self.client.post(self.url, data=data)
        self.assertEquals(response.status_code, 302)
        user = account_models.User.objects.get(pk=self.outsider.pk)

        self.assertNotEqual(user.password, original_password)


class SetTimezoneTests(AccountMixin, TestCase):
    """
    Test Setting timezone
    """
    url = reverse_lazy('_set_timezone')

    def test_get(self):
        """
        A GET request should 405
        """
        response = self.client.get(self.url)
        self.assertEquals(response.status_code, 405)

    def test_logged_out(self):
        """
        Ensure a logged out user's timezone is set.
        """
        data = {
            'timezone': 'abc123'
        }
        response = self.client.post(self.url, data=data)
        self.assertEqual(response.status_code, 400)

        data = {
            'timezone': 'UTC',
        }

        response = self.client.post(self.url, data=data)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(
            self.client.session.get('django_timezone'),
            'UTC')

    def test_logged_in(self):
        """
        A logged in user should be able to update timezone
        it should also be saved in the DB.
        """
        self.assertEqual(self.outsider.timezone, '')
        self.client.login(username='Marie Thérèse', password='secret')

        data = {
            'timezone': 'UTC',
        }

        response = self.client.post(self.url, data=data)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(
            self.client.session.get('django_timezone'),
            'UTC')

        self.assertEqual(
            account_models.User.objects.get(pk=self.outsider.pk).timezone,
            'UTC')

