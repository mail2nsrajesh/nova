#    Copyright 2013 Rackspace Hosting.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import mock

from nova import context
from nova import exception
from nova.objects import quotas as quotas_obj
from nova import quota
from nova import test
from nova.tests.unit import fake_instance
from nova.tests.unit.objects import test_objects


QUOTAS = quota.QUOTAS


class TestQuotasModule(test.NoDBTestCase):
    def setUp(self):
        super(TestQuotasModule, self).setUp()
        self.context = context.RequestContext('fake_user1', 'fake_proj1')
        self.instance = fake_instance.fake_db_instance(
                project_id='fake_proj2', user_id='fake_user2')

    def test_ids_from_instance_non_admin(self):
        project_id, user_id = quotas_obj.ids_from_instance(
                self.context, self.instance)
        self.assertEqual('fake_user2', user_id)
        self.assertEqual('fake_proj1', project_id)

    def test_ids_from_instance_admin(self):
        project_id, user_id = quotas_obj.ids_from_instance(
                self.context.elevated(), self.instance)
        self.assertEqual('fake_user2', user_id)
        self.assertEqual('fake_proj2', project_id)


class _TestQuotasObject(object):
    def setUp(self):
        super(_TestQuotasObject, self).setUp()
        self.context = context.RequestContext('fake_user1', 'fake_proj1')
        self.instance = fake_instance.fake_db_instance(
                project_id='fake_proj2', user_id='fake_user2')

    def test_from_reservations(self):
        fake_reservations = ['1', '2']
        quotas = quotas_obj.Quotas.from_reservations(
                self.context, fake_reservations)
        self.assertEqual(self.context, quotas._context)
        self.assertEqual(fake_reservations, quotas.reservations)
        self.assertIsNone(quotas.project_id)
        self.assertIsNone(quotas.user_id)

    def test_from_reservations_bogus(self):
        fake_reservations = [_TestQuotasObject, _TestQuotasObject]
        self.assertRaises(ValueError,
                          quotas_obj.Quotas.from_reservations,
                          self.context, fake_reservations)

    def test_from_reservations_instance(self):
        fake_reservations = ['1', '2']
        quotas = quotas_obj.Quotas.from_reservations(
                self.context, fake_reservations,
                instance=self.instance)
        self.assertEqual(self.context, quotas._context)
        self.assertEqual(fake_reservations, quotas.reservations)
        self.assertEqual('fake_proj1', quotas.project_id)
        self.assertEqual('fake_user2', quotas.user_id)

    def test_from_reservations_instance_admin(self):
        fake_reservations = ['1', '2']
        elevated = self.context.elevated()
        quotas = quotas_obj.Quotas.from_reservations(
                elevated, fake_reservations,
                instance=self.instance)
        self.assertEqual(elevated, quotas._context)
        self.assertEqual(fake_reservations, quotas.reservations)
        self.assertEqual('fake_proj2', quotas.project_id)
        self.assertEqual('fake_user2', quotas.user_id)

    @mock.patch.object(QUOTAS, 'reserve')
    def test_reserve(self, reserve_mock):
        fake_reservations = ['1', '2']
        quotas = quotas_obj.Quotas(context=self.context)

        reserve_mock.return_value = fake_reservations

        quotas.reserve(expire='expire',
                       project_id='project_id', user_id='user_id',
                       moo='cow')
        self.assertEqual(self.context, quotas._context)
        self.assertEqual(fake_reservations, quotas.reservations)
        self.assertEqual('project_id', quotas.project_id)
        self.assertEqual('user_id', quotas.user_id)
        reserve_mock.assert_called_once_with(
            self.context, expire='expire', project_id='project_id',
            user_id='user_id', moo='cow')

    @mock.patch.object(QUOTAS, 'commit')
    def test_commit(self, commit_mock):
        fake_reservations = ['1', '2']
        quotas = quotas_obj.Quotas.from_reservations(
                self.context, fake_reservations)
        quotas.commit()
        self.assertIsNone(quotas.reservations)
        commit_mock.assert_called_once_with(
            self.context, fake_reservations, project_id=None, user_id=None)

    @mock.patch.object(QUOTAS, 'commit')
    def test_commit_none_reservations(self, commit_mock):
        quotas = quotas_obj.Quotas.from_reservations(self.context, None)
        quotas.commit()
        self.assertFalse(commit_mock.called)

    @mock.patch.object(QUOTAS, 'rollback')
    def test_rollback(self, rollback_mock):
        fake_reservations = ['1', '2']
        quotas = quotas_obj.Quotas.from_reservations(
                self.context, fake_reservations)

        quotas.rollback()
        self.assertIsNone(quotas.reservations)
        rollback_mock.assert_called_once_with(
            self.context, fake_reservations, project_id=None, user_id=None)

    @mock.patch.object(QUOTAS, 'rollback')
    def test_rollback_none_reservations(self, rollback_mock):
        quotas = quotas_obj.Quotas.from_reservations(self.context, None)
        quotas.rollback()
        self.assertFalse(rollback_mock.called)

    @mock.patch('nova.db.quota_create')
    def test_create_limit(self, mock_create):
        quotas_obj.Quotas.create_limit(self.context, 'fake-project',
                                       'foo', 10, user_id='user')
        mock_create.assert_called_once_with(self.context, 'fake-project',
                                            'foo', 10, user_id='user')

    @mock.patch('nova.db.quota_update')
    def test_update_limit(self, mock_update):
        quotas_obj.Quotas.update_limit(self.context, 'fake-project',
                                       'foo', 10, user_id='user')
        mock_update.assert_called_once_with(self.context, 'fake-project',
                                            'foo', 10, user_id='user')

    @mock.patch.object(QUOTAS, 'count_as_dict')
    def test_count(self, mock_count):
        # key_pairs can't actually be counted across a project, this is just
        # for testing.
        mock_count.return_value = {'project': {'key_pairs': 5},
                                   'user': {'key_pairs': 4}}
        count = quotas_obj.Quotas.count(self.context, 'key_pairs', 'a-user')
        self.assertEqual(4, count)

        # key_pairs can't actually be counted across a project, this is just
        # for testing.
        mock_count.return_value = {'project': {'key_pairs': 5}}
        count = quotas_obj.Quotas.count(self.context, 'key_pairs', 'a-user')
        self.assertEqual(5, count)

        mock_count.return_value = {'user': {'key_pairs': 3}}
        count = quotas_obj.Quotas.count(self.context, 'key_pairs', 'a-user')
        self.assertEqual(3, count)

    @mock.patch('nova.objects.Quotas.count_as_dict')
    def test_check_deltas(self, mock_count):
        self.flags(key_pairs=3, group='quota')
        self.flags(server_group_members=3, group='quota')

        def fake_count(context, resource):
            if resource in ('key_pairs', 'server_group_members'):
                return {'project': {'key_pairs': 2, 'server_group_members': 2},
                        'user': {'key_pairs': 1, 'server_group_members': 2}}
            else:
                return {'user': {resource: 2}}

        mock_count.side_effect = fake_count
        deltas = {'key_pairs': 1,
                  'server_group_members': 1,
                  'security_group_rules': 1}
        project_id = 'fake-other-project'
        user_id = 'fake-other-user'
        quotas_obj.Quotas.check_deltas(self.context, deltas,
                                       check_project_id=project_id,
                                       check_user_id=user_id)
        # Should be called twice: once for key_pairs/server_group_members,
        # once for security_group_rules.
        self.assertEqual(2, mock_count.call_count)
        call1 = mock.call(self.context, 'key_pairs')
        call2 = mock.call(self.context, 'server_group_members')
        call3 = mock.call(self.context, 'security_group_rules')
        self.assertTrue(call1 in mock_count.mock_calls or
                        call2 in mock_count.mock_calls)
        self.assertIn(call3, mock_count.mock_calls)

    @mock.patch('nova.objects.Quotas.count_as_dict')
    def test_check_deltas_zero(self, mock_count):
        # This will test that we will raise OverQuota if given a zero delta if
        # an object creation has put us over the allowed quota.
        # This is for the scenario where we recheck quota and delete an object
        # if we have gone over quota during a race.
        self.flags(key_pairs=3, group='quota')
        self.flags(server_group_members=3, group='quota')

        def fake_count(context, resource):
            return {'user': {resource: 4}}

        mock_count.side_effect = fake_count
        deltas = {'key_pairs': 0, 'server_group_members': 0}
        project_id = 'fake-other-project'
        user_id = 'fake-other-user'
        self.assertRaises(exception.OverQuota, quotas_obj.Quotas.check_deltas,
                          self.context, deltas,
                          check_project_id=project_id,
                          check_user_id=user_id)
        # Should be called twice, once for key_pairs, once for
        # server_group_members
        self.assertEqual(2, mock_count.call_count)
        call1 = mock.call(self.context, 'key_pairs')
        call2 = mock.call(self.context, 'server_group_members')
        mock_count.assert_has_calls([call1, call2], any_order=True)

    @mock.patch('nova.objects.Quotas.count_as_dict')
    def test_check_deltas_negative(self, mock_count):
        """Test check_deltas with a negative delta.

        Negative deltas probably won't be used going forward for countable
        resources because there are no usage records to decrement and there
        won't be quota operations done when deleting resources. When resources
        are deleted, they will no longer be reflected in the count.
        """
        self.flags(key_pairs=3, group='quota')
        mock_count.return_value = {'user': {'key_pairs': 4}}
        deltas = {'key_pairs': -1}
        # Should pass because the delta makes 3 key_pairs
        quotas_obj.Quotas.check_deltas(self.context, deltas, 'a-user',
                                       something='something')
        # args for the count function should get passed along
        mock_count.assert_called_once_with(self.context, 'key_pairs', 'a-user',
                                           something='something')

    @mock.patch('nova.objects.Quotas.count_as_dict')
    @mock.patch('nova.objects.Quotas.limit_check_project_and_user')
    def test_check_deltas_limit_check_scoping(self, mock_check, mock_count):
        # check_project_id and check_user_id kwargs should get passed along to
        # limit_check_project_and_user()
        mock_count.return_value = {'project': {'foo': 5}, 'user': {'foo': 1}}
        deltas = {'foo': 1}

        quotas_obj.Quotas.check_deltas(self.context, deltas, 'a-project')
        mock_check.assert_called_once_with(self.context,
                                           project_values={'foo': 6},
                                           user_values={'foo': 2})

        mock_check.reset_mock()
        quotas_obj.Quotas.check_deltas(self.context, deltas, 'a-project',
                                       check_project_id='a-project')
        mock_check.assert_called_once_with(self.context,
                                           project_values={'foo': 6},
                                           user_values={'foo': 2},
                                           project_id='a-project')

        mock_check.reset_mock()
        quotas_obj.Quotas.check_deltas(self.context, deltas, 'a-project',
                                       check_user_id='a-user')
        mock_check.assert_called_once_with(self.context,
                                           project_values={'foo': 6},
                                           user_values={'foo': 2},
                                           user_id='a-user')


class TestQuotasObject(_TestQuotasObject, test_objects._LocalTest):
    pass


class TestRemoteQuotasObject(_TestQuotasObject, test_objects._RemoteTest):
    pass
