#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""is_login_wall 纯函数单测（spec 2026-10-19 §4.4）"""
import unittest
from check_login import is_login_wall


class TestLoginWall(unittest.TestCase):
    def test_console_url_ok(self):
        self.assertFalse(is_login_wall(
            "https://ufuwu.1688.com/page/fuwu_work_isv_container.htm?appkey=2839818", False))

    def test_taobao_login_redirect(self):
        self.assertTrue(is_login_wall(
            "https://login.taobao.com/member/login.jhtml?redirect=ufuwu", False))

    def test_1688_login_redirect(self):
        self.assertTrue(is_login_wall("https://login.1688.com/member/signin.htm", False))

    def test_password_input_on_page(self):
        self.assertTrue(is_login_wall("https://ufuwu.1688.com/page/fuwu_work_isv_container.htm", True))

    def test_empty_url_no_input(self):
        self.assertFalse(is_login_wall("", False))


if __name__ == "__main__":
    unittest.main()
