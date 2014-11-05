from unittest import main
from qiita_pet.test.tornado_test_base import TestHandlerBase


class TestAuthCreateHandler(TestHandlerBase):
    database = True

    def test_get(self):
        response = self.get('/auth/create/')
        self.assertEqual(response.code, 200)

    def test_post(self):
        post_args = {
            'username': 'newuser@foo.bar',
            'pass': 'password',
        }
        response = self.post('/auth/create/', post_args)
        # Make sure page response loaded sucessfully
        self.assertEqual(response.code, 200)


class TestAuthVerifyHandler(TestHandlerBase):
    def test_get(self):
        response = self.get('/auth/verify/SOMETHINGHERE?email=test%40foo.bar')
        self.assertEqual(response.code, 200)


class TestAuthLoginHandler(TestHandlerBase):
    def test_get(self):
        response = self.get('/auth/login/')
        self.assertEqual(response.code, 200)
        # make sure redirect happened properly
        port = self.get_http_port()
        self.assertEqual(response.effective_url, 'http://localhost:%d/' % port)

    def test_post(self):
        post_args = {
            'username': 'test@foo.bar',
            'passwd': 'password',
        }
        response = self.post('/auth/login/', post_args)
        self.assertEqual(response.code, 200)

    def test_set_current_user(self):
        # TODO: add proper test for this once figure out how. Issue 567
        pass


class TestAuthLogoutHandler(TestHandlerBase):
    def test_get(self):
        response = self.get('/auth/login/')
        self.assertEqual(response.code, 200)
        # make sure redirect happened properly
        port = self.get_http_port()
        self.assertEqual(response.effective_url, 'http://localhost:%d/' % port)


if __name__ == "__main__":
    main()
