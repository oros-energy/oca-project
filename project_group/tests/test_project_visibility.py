from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import new_test_user

from odoo.addons.base.tests.common import BaseCommon
from odoo.addons.mail.tests.common import mail_new_test_user


class TestProjectVisibility(BaseCommon):
    # These tests run as superuser, not as the BaseCommon test user
    _test_user_groups = ()

    @classmethod
    def setUpClass(cls):
        """Set up the class with initial data for tests."""
        super().setUpClass()
        cls.ProjectObj = cls.env["project.project"]
        cls.GroupObj = cls.env["res.groups"]
        cls.project_group_user = mail_new_test_user(
            cls.env,
            login="projectgroupuser",
            name="Project Group User",
            email="projectgroupuser@example.com",
            company_id=cls.env.company.id,
            groups="base.group_user",
        )
        cls.group1 = cls.GroupObj.create({"name": "Test Group 1"})
        cls.group2 = cls.GroupObj.create({"name": "Test Group 2"})
        cls.project = cls.ProjectObj.create(
            {"name": "Test Project", "privacy_visibility": "portal"}
        )
        cls.restricted_project = cls.ProjectObj.create(
            {
                "name": "Restricted Project",
                "privacy_visibility": "followers",
                "group_ids": [Command.set([cls.group1.id])],
            }
        )

    def test_01_group_ids_visibility(self):
        """Test the visibility of group_ids based on project privacy settings."""
        self.assertFalse(
            self.project.group_ids,
            "group_ids should not be set when visibility is 'portal'",
        )
        self.assertEqual(
            self.project.privacy_visibility,
            "portal",
            "privacy_visibility should be 'portal' initially",
        )

        self.project.write(
            {
                "privacy_visibility": "followers",
                "group_ids": [Command.set([self.group1.id, self.group2.id])],
            }
        )
        self.assertEqual(
            self.project.privacy_visibility,
            "followers",
            "privacy_visibility should be 'followers' after update",
        )
        self.assertTrue(
            self.project.group_ids,
            "group_ids should be set when visibility is 'followers'",
        )
        self.assertEqual(
            len(self.project.group_ids), 2, "There should be two groups assigned"
        )

        self.project.write(
            {
                "privacy_visibility": "employees",
            }
        )
        self.assertEqual(
            self.project.privacy_visibility,
            "employees",
            "privacy_visibility should be 'employees' after update",
        )

    def test_02_access_rights(self):
        """Test the access rights of users based on group membership."""
        self.assertEqual(
            self.restricted_project.privacy_visibility,
            "followers",
            "privacy_visibility should be 'followers' initially",
        )

        self.project_group_user.write({"group_ids": [Command.set([self.group2.id])]})
        self.assertNotIn(
            self.project_group_user,
            self.restricted_project.sudo().group_ids.all_user_ids,
            "User should not have access",
        )

        self.project_group_user.write({"group_ids": [Command.set([self.group1.id])]})
        self.assertIn(
            self.project_group_user,
            self.restricted_project.sudo().group_ids.all_user_ids,
            "User should have access",
        )

        self.restricted_project.write(
            {
                "privacy_visibility": "employees",
            }
        )
        self.assertEqual(
            self.restricted_project.privacy_visibility,
            "employees",
            "privacy_visibility should be 'employees' after update",
        )

    def _project_user(self, login, groups):
        user = new_test_user(
            self.env,
            login=login,
            groups="base.group_user,project.group_project_user",
        )
        user.write({"group_ids": [Command.link(group.id) for group in groups]})
        return user

    def test_03_member_reads_and_writes_as_user(self):
        """A project user in one of the project's groups reads the project and
        its tasks and may change the tasks (core rule: project readable)."""
        task = self.env["project.task"].create(
            {"name": "Restricted Task", "project_id": self.restricted_project.id}
        )
        member = self._project_user("projectgroupmember", self.group1)
        project = self.restricted_project.with_user(member)
        self.assertTrue(project.has_access("read"))
        self.assertEqual(project.name, "Restricted Project")
        self.assertIn(
            self.restricted_project,
            self.ProjectObj.with_user(member).search([]),
        )
        task_as_member = task.with_user(member)
        self.assertTrue(task_as_member.has_access("read"))
        self.assertEqual(task_as_member.name, "Restricted Task")
        task_as_member.write({"name": "Changed by member"})
        self.assertEqual(task.name, "Changed by member")
        # the module only grants read access on the project itself
        with self.assertRaises(AccessError):
            project.write({"name": "Renamed by member"})

    def test_04_outsider_neither_reads_nor_writes_as_user(self):
        task = self.env["project.task"].create(
            {"name": "Restricted Task", "project_id": self.restricted_project.id}
        )
        outsider = self._project_user("projectgroupoutsider", self.group2)
        project = self.restricted_project.with_user(outsider)
        self.assertFalse(project.has_access("read"))
        self.assertNotIn(
            self.restricted_project,
            self.ProjectObj.with_user(outsider).search([]),
        )
        with self.assertRaises(AccessError):
            project.check_access("read")
        task_as_outsider = task.with_user(outsider)
        self.assertFalse(task_as_outsider.has_access("read"))
        with self.assertRaises(AccessError):
            task_as_outsider.write({"name": "Changed by outsider"})
